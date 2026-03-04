from flask import Blueprint, abort, render_template
from vidyut.lipi import transliterate, Scheme

import ambuda.queries as q

bp = Blueprint("authors", __name__)


@bp.route("/")
def index():
    all_authors = q.authors()
    authors_with_texts = []
    for a in sorted(
        all_authors,
        key=lambda a: transliterate(a.name, Scheme.HarvardKyoto, Scheme.Devanagari),
    ):
        texts = sorted(
            [t for t in a.texts if t.parent_id is None],
            key=lambda t: transliterate(
                t.title, Scheme.HarvardKyoto, Scheme.Devanagari
            ),
        )
        if texts:
            authors_with_texts.append((a, texts))
    return render_template("authors/index.html", authors_with_texts=authors_with_texts)


@bp.route("/<slug>")
def author(slug):
    author = q.author(slug)
    if author is None:
        abort(404)

    texts = sorted(
        [t for t in author.texts if t.parent_id is None],
        key=lambda t: transliterate(t.title, Scheme.HarvardKyoto, Scheme.Devanagari),
    )
    return render_template("authors/author.html", author=author, texts=texts)
