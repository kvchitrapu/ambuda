"""Views related to texts: title pages, sections, verses, etc."""

import json
import os

from flask import (
    Blueprint,
    abort,
    current_app,
    render_template,
    session,
    url_for,
    send_file,
)
from vidyut.lipi import transliterate, Scheme

import ambuda.database as db
import ambuda.queries as q
from ambuda.consts import SINGLE_SECTION_SLUG
from ambuda.models.texts import TextConfig
from ambuda.utils import text_utils
from ambuda.utils import xml
from ambuda.utils.json_serde import AmbudaJSONEncoder
from ambuda.utils.text_validation import safe_parse_report
from ambuda.tasks.text_validation import maybe_rerun_report
from ambuda.views.reader.schema import Block, Section
from ambuda.utils.s3 import S3Path
from sqlalchemy import exists, orm, select

bp = Blueprint("texts", __name__)


def _prev_cur_next(sections: list[db.TextSection], slug: str):
    """Get the previous, current, and next sections.

    :param sections: all of the sections in this text.
    :param slug: the slug for the current section.
    """
    found = False
    i = 0
    for i, s in enumerate(sections):
        if s.slug == slug:
            found = True
            break

    if not found:
        raise ValueError(f"Unknown slug {slug}")

    prev = sections[i - 1] if i > 0 else None
    cur = sections[i]
    next = sections[i + 1] if i < len(sections) - 1 else None
    return prev, cur, next


def _make_section_url(text: db.Text, section: db.TextSection | None) -> str | None:
    if section:
        return url_for("texts.section", text_slug=text.slug, section_slug=section.slug)
    return None


def _page_url(page) -> str | None:
    if page:
        return url_for(
            "proofing.page.edit",
            project_slug=page.project.slug,
            page_slug=page.slug,
        )
    return None


def _build_section_data(text_: db.Text, section_slug: str) -> Section:
    try:
        prev, cur, next_ = _prev_cur_next(text_.sections, section_slug)
    except ValueError:
        abort(404)

    db_session = q.get_session()

    block_load = orm.selectinload(db.TextSection.blocks)
    page_load = block_load.selectinload(db.TextBlock.page).selectinload(db.Page.project)
    parent_load = (
        block_load.selectinload(db.TextBlock.parents)
        .selectinload(db.TextBlock.page)
        .selectinload(db.Page.project)
    )
    stmt = (
        select(db.TextSection)
        .filter_by(text_id=text_.id, slug=section_slug)
        .options(block_load, page_load, parent_load)
    )
    cur = db_session.scalars(stmt).first()

    blocks = []
    for block in cur.blocks:
        # HACK: skip these for now.
        if block.xml.startswith("<title") or block.xml.startswith("<subtitle"):
            continue

        parent_blocks = None
        if text_.parent_id and block.parents:
            parent_blocks = [
                Block(
                    slug=pb.slug,
                    mula=xml.transform_text_block(pb.xml),
                    page_url=_page_url(pb.page),
                )
                for pb in block.parents
            ]

        blocks.append(
            Block(
                slug=block.slug,
                mula=xml.transform_text_block(block.xml),
                page_url=_page_url(block.page),
                parent_blocks=parent_blocks,
            )
        )

    scheme = _get_user_scheme()
    if scheme != Scheme.Devanagari:
        for block in blocks:
            block.mula = xml.transliterate_html(block.mula, Scheme.Devanagari, scheme)
            if block.parent_blocks:
                for pb in block.parent_blocks:
                    pb.mula = xml.transliterate_html(pb.mula, Scheme.Devanagari, scheme)

    return Section(
        text_title=transliterate(text_.title, Scheme.HarvardKyoto, scheme),
        section_title=_transliterate_slug(cur.title, scheme),
        section_slug=section_slug,
        blocks=blocks,
        prev_url=_make_section_url(text_, prev),
        next_url=_make_section_url(text_, next_),
    )


def _transliterate_slug(s: str, scheme: Scheme) -> str:
    return transliterate(s, Scheme.HarvardKyoto, scheme).replace("\u0964", ".")


def _get_user_scheme() -> Scheme:
    script_name = session.get("script", "Devanagari")
    try:
        return Scheme.from_string(script_name)
    except ValueError:
        return Scheme.Devanagari


def _export_key(x: db.TextExport) -> tuple:
    for i, ext in enumerate(("txt", "xml", "pdf", "csv")):
        if x.slug.endswith(ext):
            return (i, x.slug)
    return (4, x.slug)


@bp.route("/")
def index():
    """Show all texts."""
    grouped_entries = text_utils.create_grouped_text_entries()
    return render_template("texts/index.html", grouped_entries=grouped_entries)


@bp.route("/<slug>/")
def text(slug):
    """Show a text's title page and contents."""
    text_ = q.text(slug)
    if text_ is None:
        abort(404)
    assert text_

    if not text_.sections:
        abort(404)

    first_section_slug = text_.sections[0].slug
    return section(slug, first_section_slug)


@bp.route("/<slug>/about")
def text_about(slug):
    """Show a text's metadata."""
    text = q.text(slug)
    if text is None:
        abort(404)
    assert text

    header_data = xml.parse_tei_header(text.header)
    return render_template(
        "texts/text-about.html",
        text=text,
        header=header_data,
    )


@bp.route("/<slug>/resources")
def text_resources(slug):
    """Show a text's downloadable resources."""
    text = q.text(slug)
    if text is None:
        abort(404)
    assert text

    exports = sorted(text.exports, key=_export_key)
    return render_template("texts/text-resources.html", text=text, exports=exports)


@bp.route("/downloads/")
def downloads():
    """Show all available downloads."""
    with q.get_session() as session:
        stmt = select(db.TextExport).order_by(db.TextExport.slug)
        exports = list(session.execute(stmt).scalars())

    return render_template("texts/downloads.html", exports=exports)


@bp.route("/downloads/<filename>")
def download_file(filename):
    text_export = q.text_export(filename)
    if not text_export:
        abort(404)
    assert text_export

    export_config = text_export.export_config
    if export_config is None:
        abort(404)
    assert export_config

    # Check cache first
    cache = current_app.cache
    cache_key = f"text_export:{filename}"
    cached_path = cache.get(cache_key)

    if cached_path and os.path.exists(cached_path):
        file_path = cached_path
    else:
        s3_path = S3Path.from_path(text_export.s3_path)
        cache_dir = current_app.config.get("CACHE_DIR", "/tmp/ambuda-cache")
        os.makedirs(cache_dir, exist_ok=True)

        file_path = os.path.join(cache_dir, filename)
        s3_path.download_file(file_path)
        cache.set(cache_key, file_path, timeout=0)

    return send_file(
        file_path,
        download_name=filename,
        mimetype=export_config.mime_type,
    )


@bp.route("/<text_slug>/<section_slug>")
def section(text_slug, section_slug):
    """Show a specific section of a text."""
    text_ = q.text(text_slug)
    if text_ is None:
        abort(404)
    assert text_

    try:
        prev, cur, next_ = _prev_cur_next(text_.sections, section_slug)
    except ValueError:
        abort(404)

    is_single_section_text = not prev and not next_
    if is_single_section_text:
        # Single-section texts have exactly one section whose slug should be
        # `SINGLE_SECTION_SLUG`. If the slug is anything else, abort.
        if section_slug != SINGLE_SECTION_SLUG:
            abort(404)

    db_session = q.get_session()
    has_no_parse = not db_session.scalar(
        select(exists().where(db.BlockParse.text_id == text_.id))
    )

    data = _build_section_data(text_, section_slug)
    json_payload = json.dumps(data, cls=AmbudaJSONEncoder)

    try:
        if isinstance(text_.config, str):
            config = TextConfig.model_validate_json(text_.config)
        elif isinstance(text_.config, dict):
            config = TextConfig.model_validate(text_.config)
        else:
            config = TextConfig()
    except Exception:
        config = TextConfig()

    prefix_titles = config.titles.fixed
    section_groups = {}
    for s in text_.sections:
        key, _, _ = s.slug.rpartition(".")
        if key not in section_groups:
            section_groups[key] = []
        name = s.slug
        if s.slug.count(".") == 1:
            x, y = s.slug.split(".")
            pattern = config.titles.patterns.get("x.y")
            if pattern:
                name = pattern.format(x=x, y=y)
        section_groups[key].append((s.slug, name))

    header_data = xml.parse_tei_header(text_.header)
    exports = sorted(text_.exports, key=_export_key)

    # Collect translations and commentaries from child texts.
    # A child whose language differs from the source is a translation;
    # one that shares the same language is a commentary.
    if text_.parent_id:
        siblings = [c for c in text_.parent.children if c.id != text_.id]
        source_lang = text_.parent.language
    else:
        siblings = list(text_.children)
        source_lang = text_.language

    translations = [c for c in siblings if c.language != source_lang]
    commentaries = [c for c in siblings if c.language == source_lang]

    validation_report = None
    text_report = q.text_report(text_.id)
    if text_report:
        validation_report = safe_parse_report(text_report.payload)
        if validation_report is None:
            maybe_rerun_report(text_.id, current_app.config["AMBUDA_ENVIRONMENT"])

    return render_template(
        "texts/reader.html",
        text=text_,
        prev=prev,
        section=cur,
        next=next_,
        json_payload=json_payload,
        html_blocks=data.blocks,
        has_no_parse=has_no_parse,
        is_single_section_text=is_single_section_text,
        section_groups=section_groups,
        prefix_titles=prefix_titles,
        text_about=header_data,
        raw_header=text_.header,
        exports=exports,
        translations=translations,
        commentaries=commentaries,
        validation_report=validation_report,
    )
