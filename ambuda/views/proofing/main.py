"""Views for basic site pages."""

from collections import defaultdict
from datetime import datetime, timedelta, UTC
import uuid
from pathlib import Path

from xml.etree import ElementTree as ET

from math import ceil

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from flask_wtf import FlaskForm
from slugify import slugify
from sqlalchemy import func, orm, select
from wtforms import FileField, RadioField, StringField
from wtforms.validators import DataRequired, ValidationError
from wtforms.widgets import TextArea

from ambuda import consts
from ambuda import database as db
from ambuda import queries as q
from ambuda.enums import SitePageStatus
from ambuda.tasks import projects as project_tasks
from ambuda.utils.text_validation import try_parse_text_report
from ambuda.views.proofing.decorators import moderator_required, p2_required

bp = Blueprint("proofing", __name__)


def _is_allowed_document_file(filename: str) -> bool:
    """True iff we accept this type of document upload."""
    return Path(filename).suffix == ".pdf"


def _required_if_url(message: str):
    def fn(form, field):
        source = form.pdf_source.data
        if source == "url" and not field.data:
            raise ValidationError(message)

    return fn


def _required_if_gdrive(message: str):
    def fn(form, field):
        source = form.pdf_source.data
        if source == "gdrive" and not field.data:
            raise ValidationError(message)

    return fn


def _required_if_local(message: str):
    def fn(form, field):
        source = form.pdf_source.data
        if source == "local" and not field.data:
            raise ValidationError(message)

    return fn


class CreateProjectForm(FlaskForm):
    pdf_source = RadioField(
        "Source",
        choices=[
            ("url", "Upload from a URL"),
            ("local", "Upload from my computer"),
            # TODO: support this later, maybe too powerful for the average user.
            # ("gdrive", "Upload from a Google Drive folder"),
        ],
        validators=[DataRequired()],
    )
    pdf_url = StringField(
        "PDF URL",
        validators=[_required_if_url("Please provide a valid PDF URL.")],
    )
    # gdrive_folder_url = StringField(
    # "Google Drive folder URL",
    # validators=[
    # _required_if_gdrive("Please provide a valid Google Drive folder URL.")
    # ],
    # )
    local_file = FileField(
        "PDF file", validators=[_required_if_local("Please provide a PDF file.")]
    )
    display_title = StringField("Display title (optional)")


@bp.route("/dashboard")
def dashboard():
    """Show proofing dashboard with overview statistics."""
    from ambuda.models.proofing import ProjectStatus

    session = q.get_session()

    num_active_projects = session.scalar(
        select(func.count(db.Project.id)).filter(
            db.Project.status == ProjectStatus.ACTIVE
        )
    )
    num_pending_projects = session.scalar(
        select(func.count(db.Project.id)).filter(
            db.Project.status == ProjectStatus.PENDING
        )
    )
    num_texts = session.scalar(select(func.count(db.Text.id)))

    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    num_texts_published_30d = session.scalar(
        select(func.count(db.Text.id)).filter(db.Text.published_at >= thirty_days_ago)
    )
    num_texts_created_30d = session.scalar(
        select(func.count(db.Text.id)).filter(db.Text.created_at >= thirty_days_ago)
    )

    my_projects = []
    if current_user.is_authenticated:
        my_projects = q.user_recent_projects(current_user.id)

    return render_template(
        "proofing/dashboard.html",
        num_active_projects=num_active_projects,
        num_pending_projects=num_pending_projects,
        num_texts=num_texts,
        num_texts_published_30d=num_texts_published_30d,
        num_texts_created_30d=num_texts_created_30d,
        my_projects=my_projects,
    )


@bp.route("/")
def index():
    """List all available proofing projects."""
    from ambuda.models.proofing import ProjectStatus

    session = q.get_session()
    status_classes = {
        SitePageStatus.R2: "bg-green-200",
        SitePageStatus.R1: "bg-yellow-200",
        SitePageStatus.R0: "bg-red-300",
        SitePageStatus.SKIP: "bg-slate-100",
    }

    page = max(1, request.args.get("page", 1, type=int))
    per_page = 25
    search = request.args.get("q", "", type=str).strip()
    sort_field = request.args.get("sort", "title", type=str)
    sort_dir = request.args.get("sort_dir", "asc", type=str)
    genre_id = request.args.get("genre", None, type=int)
    tag_id = request.args.get("tag", None, type=int)

    is_p2 = current_user.is_authenticated and current_user.is_p2
    valid_statuses = (
        "all",
        "active",
        "pending",
        "closed-copy",
        "closed-duplicate",
        "closed-quality",
    )
    status_filter = (
        request.args.get("status", "active", type=str) if is_p2 else "active"
    )
    if status_filter not in valid_statuses:
        status_filter = "active"
    if sort_field not in ("title", "created"):
        sort_field = "title"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    projects, total = q.paginated_projects(
        status=status_filter,
        page=page,
        per_page=per_page,
        sort_field=sort_field,
        sort_dir=sort_dir,
        search=search,
        genre_id=genre_id,
        tag_id=tag_id,
    )
    total_pages = ceil(total / per_page) if total > 0 else 1

    active_project_ids = [p.id for p in projects]
    statuses_per_project = {}
    progress_per_project = {}
    pages_per_project = {}

    if active_project_ids:
        stmt = (
            select(
                db.Page.project_id,
                db.PageStatus.name,
                func.count(db.Page.id).label("count"),
            )
            .join(db.PageStatus)
            .filter(db.Page.project_id.in_(active_project_ids))
            .group_by(db.Page.project_id, db.PageStatus.name)
        )
        stats = session.execute(stmt).all()

        status_counts_by_project = defaultdict(lambda: defaultdict(int))
        for project_id, status_name, count in stats:
            status_counts_by_project[project_id][status_name] = count

        for proj in projects:
            counts = status_counts_by_project[proj.id]
            num_pages = sum(counts.values())

            if num_pages == 0:
                statuses_per_project[proj.id] = {}
                pages_per_project[proj.id] = 0
                continue

            project_counts = {}
            for enum_value, class_ in status_classes.items():
                count = counts.get(enum_value.value, 0)
                fraction = count / num_pages
                project_counts[class_] = fraction
                if enum_value == SitePageStatus.R0:
                    progress_per_project[proj.id] = 1 - fraction

            statuses_per_project[proj.id] = project_counts
            pages_per_project[proj.id] = num_pages

    genres = q.genres()
    tags = q.project_tags()

    # Count projects per tag for the tag cloud.
    from ambuda.models.proofing import project_tag_association

    tag_count_stmt = select(
        project_tag_association.c.tag_id,
        func.count().label("cnt"),
    ).group_by(project_tag_association.c.tag_id)
    tag_counts = {row[0]: row[1] for row in session.execute(tag_count_stmt).all()}

    template_vars = dict(
        projects=projects,
        statuses_per_project=statuses_per_project,
        progress_per_project=progress_per_project,
        pages_per_project=pages_per_project,
        genres=genres,
        tags=tags,
        tag_counts=tag_counts,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        sort_field=sort_field,
        sort_dir=sort_dir,
        genre_id=genre_id,
        tag_id=tag_id,
        status_filter=status_filter,
    )

    if request.args.get("partial"):
        from flask import jsonify

        html = render_template("proofing/index_projects.html", **template_vars)
        return jsonify(html=html, total=total)

    return render_template("proofing/index.html", **template_vars)


@bp.route("/help/complete-guide")
def complete_guide():
    """[deprecated] Display our complete proofing guidelines."""
    return render_template("proofing/complete-guide.html")


@bp.route("/help/proofing-guide")
def guidelines():
    """Display our complete proofing guidelines."""
    return render_template("proofing/guidelines.html")


@bp.route("/create-project", methods=["GET", "POST"])
@p2_required
def create_project():
    form = CreateProjectForm()
    if not form.validate_on_submit():
        return render_template("proofing/create-project.html", form=form)

    pdf_source = form.pdf_source.data

    # if pdf_source == "gdrive":
    #     gdrive_folder_url = form.gdrive_folder_url.data
    #     task = project_tasks.create_projects_from_gdrive_folder.delay(
    #         folder_url=gdrive_folder_url,
    #         app_environment=current_app.config["AMBUDA_ENVIRONMENT"],
    #         creator_id=current_user.id,
    #         upload_folder=current_app.config["UPLOAD_FOLDER"],
    #     )
    #     return render_template(
    #         "proofing/create-project-post.html",
    #         stauts=task.status,
    #         current=0,
    #         total=0,
    #         percent=0,
    #         task_id=task.id,
    #     )

    display_title = form.display_title.data or None

    if pdf_source == "url":
        pdf_url = form.pdf_url.data
        task = project_tasks.create_project_from_url.apply_async(
            kwargs=dict(
                pdf_url=pdf_url,
                display_title=display_title,
                creator_id=current_user.id,
                app_environment=current_app.config["AMBUDA_ENVIRONMENT"],
            ),
            headers={"initiated_by": current_user.username},
        )
    else:
        # We accept only PDFs, so validate that the user hasn't uploaded some
        # other kind of document format.
        filename = form.local_file.raw_data[0].filename
        if not _is_allowed_document_file(filename):
            flash("Please upload a PDF.")
            return render_template("proofing/create-project.html", form=form)

        file_data = form.local_file.data
        file_data.seek(0, 2)
        size = file_data.tell()
        file_data.seek(0)
        if size > 128 * 1024 * 1024:
            flash("PDF must be under 128 MB.")
            return render_template("proofing/create-project.html", form=form)

        # Create all directories for this project ahead of time.
        # FIXME(arun): push this further into the Celery task.
        upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "pdf-upload"
        upload_dir.mkdir(parents=True, exist_ok=True)

        temp_id = str(uuid.uuid4())
        pdf_path = upload_dir / f"{temp_id}.pdf"
        form.local_file.data.save(pdf_path)

        task = project_tasks.create_project_from_local_pdf.apply_async(
            kwargs=dict(
                pdf_path=str(pdf_path),
                display_title=display_title,
                creator_id=current_user.id,
                app_environment=current_app.config["AMBUDA_ENVIRONMENT"],
            ),
            headers={"initiated_by": current_user.username},
        )
    return render_template(
        "proofing/create-project-post.html",
        stauts=task.status,
        current=0,
        total=0,
        percent=0,
        task_id=task.id,
    )


@bp.route("/status/<task_id>")
def create_project_status(task_id):
    """AJAX summary of the task."""
    from ambuda.tasks import app as celery_app

    r = celery_app.AsyncResult(task_id)

    info = r.info or {}
    if isinstance(info, Exception):
        current = total = percent = 0
        slug = None
        upload_current = upload_total = upload_percent = 0
    else:
        current = info.get("current", 100)
        total = info.get("total", 100)
        slug = info.get("slug", None)
        percent = 100 * current / total
        upload_current = info.get("upload_current", 0)
        upload_total = info.get("upload_total", 0)
        upload_percent = 100 * upload_current / upload_total if upload_total else 0

    return render_template(
        "include/task-progress.html",
        status=r.status,
        current=current,
        total=total,
        percent=percent,
        slug=slug,
        upload_current=upload_current,
        upload_total=upload_total,
        upload_percent=upload_percent,
    )


def _revision_load_options():
    return (
        orm.defer(db.Revision.content),
        orm.selectinload(db.Revision.author).load_only(db.User.username),
        orm.selectinload(db.Revision.page).load_only(db.Page.slug),
        orm.selectinload(db.Revision.project).load_only(
            db.Project.slug, db.Project.display_title
        ),
        orm.selectinload(db.Revision.status).load_only(db.PageStatus.name),
    )


def _get_recent_activity(
    num_per_page: int,
    before: datetime | None = None,
    after: datetime | None = None,
):
    """Return (activity_list, has_more) for cursor-based pagination."""
    bot_user = q.user(consts.BOT_USERNAME)
    assert bot_user, "Bot user not defined"

    session = q.get_session()

    if after:
        time_filter = lambda col: col > after  # noqa: E731
        order = lambda col: col.asc()  # noqa: E731
    else:
        time_filter = (lambda col: col < before) if before else None  # noqa: E731
        order = lambda col: col.desc()  # noqa: E731

    individual_stmt = (
        select(db.Revision)
        .options(*_revision_load_options())
        .filter(db.Revision.author_id != bot_user.id)
        .filter(db.Revision.batch_id.is_(None))
        .order_by(order(db.Revision.created_at))
        .limit(num_per_page)
    )
    if time_filter:
        individual_stmt = individual_stmt.filter(time_filter(db.Revision.created_at))
    recent_activity = [
        ("revision", r.created, r) for r in session.scalars(individual_stmt)
    ]

    batch_stmt = (
        select(
            db.Revision.batch_id,
            func.count().label("revision_count"),
            func.max(db.Revision.created_at).label("latest_created_at"),
        )
        .filter(db.Revision.author_id != bot_user.id)
        .filter(db.Revision.batch_id.isnot(None))
        .group_by(db.Revision.batch_id)
        .order_by(order(func.max(db.Revision.created_at)))
        .limit(num_per_page)
    )
    if time_filter:
        batch_stmt = batch_stmt.having(time_filter(func.max(db.Revision.created_at)))
    batch_rows = session.execute(batch_stmt).all()
    if batch_rows:
        batch_counts = {row.batch_id: row.revision_count for row in batch_rows}
        latest_per_batch = (
            select(
                db.Revision.batch_id,
                func.max(db.Revision.id).label("max_id"),
            )
            .filter(db.Revision.batch_id.in_(list(batch_counts.keys())))
            .group_by(db.Revision.batch_id)
            .subquery()
        )
        rep_stmt = (
            select(db.Revision)
            .join(latest_per_batch, db.Revision.id == latest_per_batch.c.max_id)
            .options(*_revision_load_options())
        )
        for r in session.scalars(rep_stmt):
            recent_activity.append(("batch", r.created, r, batch_counts[r.batch_id]))

    project_stmt = (
        select(db.Project)
        .options(orm.selectinload(db.Project.creator).load_only(db.User.username))
        .order_by(order(db.Project.created_at))
        .limit(num_per_page)
    )
    if time_filter:
        project_stmt = project_stmt.filter(time_filter(db.Project.created_at))
    recent_activity += [
        ("project", p.created_at, p) for p in session.scalars(project_stmt)
    ]

    recent_activity.sort(key=lambda x: x[1], reverse=True)
    has_more = len(recent_activity) > num_per_page
    return recent_activity[:num_per_page], has_more


def _parse_cursor() -> tuple[datetime | None, datetime | None]:
    try:
        if before := request.args.get("before"):
            return datetime.fromisoformat(before), None
        if after := request.args.get("after"):
            return None, datetime.fromisoformat(after)
    except ValueError:
        pass
    return None, None


@bp.route("/recent-changes")
def recent_changes():
    """Show recent changes across all projects."""
    num_per_page = 100
    before, after = _parse_cursor()

    recent_activity, has_more = _get_recent_activity(
        num_per_page=num_per_page, before=before, after=after
    )

    next_cursor = prev_cursor = None
    if recent_activity:
        oldest_ts = recent_activity[-1][1].isoformat()
        newest_ts = recent_activity[0][1].isoformat()
        if after:
            next_cursor = oldest_ts
            prev_cursor = newest_ts if has_more else None
        else:
            next_cursor = oldest_ts if has_more else None
            prev_cursor = newest_ts if before else None

    return render_template(
        "proofing/recent-changes.html",
        recent_activity=recent_activity,
        next_cursor=next_cursor,
        prev_cursor=prev_cursor,
    )


@bp.route("/batch/<int:batch_id>")
def batch_detail(batch_id):
    """Show all revisions in a batch."""
    session = q.get_session()
    revisions = list(
        session.scalars(
            select(db.Revision)
            .options(*_revision_load_options())
            .filter(db.Revision.batch_id == batch_id)
            .order_by(db.Revision.created_at.desc())
        ).all()
    )
    if not revisions:
        abort(404)

    return render_template(
        "proofing/batch-detail.html",
        revisions=revisions,
        batch_id=batch_id,
    )


@bp.route("/talk")
def talk():
    """Show discussion across all projects."""
    projects = q.active_projects()

    all_threads = [(p, t) for p in projects for t in p.board.threads]
    all_threads.sort(key=lambda x: x[1].updated_at, reverse=True)

    return render_template("proofing/talk.html", all_threads=all_threads)


@bp.route("/texts")
def texts():
    """List all published texts."""

    session = q.get_session()

    # Fetch texts with their latest validation report in a single query.
    latest_report = (
        select(db.TextReport.id)
        .where(db.TextReport.text_id == db.Text.id)
        .order_by(db.TextReport.created_at.desc())
        .limit(1)
        .correlate(db.Text)
        .scalar_subquery()
    )
    stmt = (
        select(db.Text, db.TextReport)
        .outerjoin(db.TextReport, db.TextReport.id == latest_report)
        .options(
            orm.selectinload(db.Text.project).load_only(
                db.Project.slug, db.Project.display_title
            ),
            orm.selectinload(db.Text.author).load_only(db.Author.name),
        )
        .order_by(db.Text.created_at.desc())
    )
    rows = session.execute(stmt).all()

    # Build a flat list of (text, parsed_report) pairs.
    report_map = {}
    all_texts = []
    for t, tr in rows:
        all_texts.append(t)
        if tr:
            report_map[t.id] = try_parse_text_report(tr.payload)

    return render_template(
        "proofing/texts.html",
        all_texts=all_texts,
        report_map=report_map,
    )


@bp.route("/texts/<slug>/report")
def text_report(slug):
    """Show validation report for a text."""

    text = q.text(slug)
    if text is None:
        abort(404)
    assert text

    text_report_ = q.text_report(text.id)
    report = None
    updated_at = None
    if text_report_:
        report = try_parse_text_report(text_report_.payload)
        updated_at = text_report_.updated_at
    return render_template(
        "proofing/text-report.html",
        text=text,
        report=report,
        form=FlaskForm(),
        updated_at=updated_at,
    )


@bp.route("/texts/<slug>/report/rerun", methods=["POST"])
@p2_required
def rerun_text_report(slug):
    """Trigger a re-run of the validation report for a text."""
    from ambuda.tasks.text_validation import maybe_rerun_report

    text = q.text(slug)
    if text is None:
        abort(404)

    if maybe_rerun_report(text.id, current_app.config["AMBUDA_ENVIRONMENT"]):
        flash("Report re-run started. Refresh in a moment to see updated results.")
    else:
        flash("A report re-run is already in progress.")
    return redirect(url_for("proofing.text_report", slug=slug))


@bp.route("/admin/dashboard/")
@moderator_required
def admin_dashboard():
    now = datetime.now(UTC).replace(tzinfo=None)
    days_ago_30d = now - timedelta(days=30)
    days_ago_7d = now - timedelta(days=7)
    days_ago_1d = now - timedelta(days=1)

    session = q.get_session()
    stmt = select(db.User).filter_by(username=consts.BOT_USERNAME)
    bot = session.scalars(stmt).one()
    bot_id = bot.id

    stmt = (
        select(db.Revision)
        .filter(
            (db.Revision.created_at >= days_ago_30d) & (db.Revision.author_id != bot_id)
        )
        .options(orm.load_only(db.Revision.created_at, db.Revision.author_id))
        .order_by(db.Revision.created_at)
    )
    revisions_30d = list(session.scalars(stmt).all())
    revisions_7d = [x for x in revisions_30d if x.created >= days_ago_7d]
    revisions_1d = [x for x in revisions_7d if x.created >= days_ago_1d]
    num_revisions_30d = len(revisions_30d)
    num_revisions_7d = len(revisions_7d)
    num_revisions_1d = len(revisions_1d)

    num_contributors_30d = len({x.author_id for x in revisions_30d})
    num_contributors_7d = len({x.author_id for x in revisions_7d})
    num_contributors_1d = len({x.author_id for x in revisions_1d})

    return render_template(
        "proofing/dashboard.html",
        num_revisions_30d=num_revisions_30d,
        num_revisions_7d=num_revisions_7d,
        num_revisions_1d=num_revisions_1d,
        num_contributors_30d=num_contributors_30d,
        num_contributors_7d=num_contributors_7d,
        num_contributors_1d=num_contributors_1d,
    )
