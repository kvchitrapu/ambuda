"""Background tasks for proofing projects."""

import logging

from celery import group
from celery.result import GroupResult

from ambuda import consts
from ambuda import database as db
from ambuda.enums import SitePageStatus
from ambuda.tasks import app
from ambuda.tasks.utils import get_db_session
from ambuda.utils import google_ocr
from ambuda.utils.revisions import add_revision


def _run_ocr_for_page_inner(
    app_env: str,
    project_slug: str,
    page_slug: str,
):
    """Run OCR for a single page without Flask dependency."""

    with get_db_session(app_env) as (session, query, cfg):
        logging.info(f"Running OCR for page {project_slug}/{page_slug}")
        bot_user = query.user(consts.BOT_USERNAME)
        if bot_user is None:
            raise ValueError(f'User "{consts.BOT_USERNAME}" is not defined.')

        project_ = query.project(project_slug)
        if not project_:
            raise ValueError(f"Unknown project {project_slug}")
        page_ = query.page(project_.id, page_slug)
        if not page_:
            raise ValueError(f"Unknown page {project_slug}/{page_slug}")

        # The actual API call.
        ocr_response = google_ocr.run(page_, cfg.S3_BUCKET, cfg.CLOUDFRONT_BASE_URL)

        project = query.project(project_slug)
        page = query.page(project.id, page_slug)

        page.ocr_bounding_boxes = google_ocr.serialize_bounding_boxes(
            ocr_response.bounding_boxes
        )
        session.add(page)
        session.commit()

        summary = "Run OCR"
        try:
            _ = add_revision(
                page=page,
                summary=summary,
                content=ocr_response.text_content,
                version=0,
                author_id=bot_user.id,
                status=SitePageStatus.R0,
                session=session,
                query=query,
            )
            logging.info(f"Created new revision for page {project_slug}/{page_slug}")
        except Exception as e:
            logging.info(f"OCR failed for page {project_slug}/{page_slug}: {e}")
            raise ValueError(
                f'OCR failed for page "{project.slug}/{page.slug}".'
            ) from e


@app.task(bind=True)
def run_ocr_for_page(
    self,
    *,
    app_env: str,
    project_slug: str,
    page_slug: str,
):
    _run_ocr_for_page_inner(
        app_env,
        project_slug,
        page_slug,
    )


def _replace_ocr_bounding_boxes_for_page_inner(
    app_env: str,
    project_slug: str,
    page_slug: str,
):
    """Re-run OCR for a single page and update only its bounding box data."""

    with get_db_session(app_env) as (session, query, cfg):
        logging.info(
            f"Replacing OCR bounding boxes for page {project_slug}/{page_slug}"
        )

        project_ = query.project(project_slug)
        if not project_:
            raise ValueError(f"Unknown project {project_slug}")
        page_ = query.page(project_.id, page_slug)
        if not page_:
            raise ValueError(f"Unknown page {project_slug}/{page_slug}")

        ocr_response = google_ocr.run(page_, cfg.S3_BUCKET, cfg.CLOUDFRONT_BASE_URL)

        page_.ocr_bounding_boxes = google_ocr.serialize_bounding_boxes(
            ocr_response.bounding_boxes
        )
        session.add(page_)
        session.commit()
        logging.info(f"Updated bounding boxes for page {project_slug}/{page_slug}")


@app.task(bind=True)
def replace_ocr_bounding_boxes_for_page(
    self,
    *,
    app_env: str,
    project_slug: str,
    page_slug: str,
):
    _replace_ocr_bounding_boxes_for_page_inner(
        app_env,
        project_slug,
        page_slug,
    )


def replace_ocr_bounding_boxes(
    app_env: str,
    project: db.Project,
) -> GroupResult | None:
    """Create a `group` task to replace OCR bounding boxes for all pages.

    This re-runs OCR on every page and updates only the bounding box data,
    without creating new revisions or modifying page content.

    :return: the Celery result, or ``None`` if no pages exist.
    """
    pages = list(project.pages)

    if pages:
        tasks = group(
            replace_ocr_bounding_boxes_for_page.s(
                app_env=app_env,
                project_slug=project.slug,
                page_slug=p.slug,
            )
            for p in pages
        )
        ret = tasks.apply_async()
        ret.save()
        return ret
    else:
        return None


@app.task(bind=True)
def replace_ocr_bounding_boxes_for_project(
    self,
    *,
    app_env: str,
    project_slug: str,
):
    """Celery task that replaces OCR bounding boxes for all pages in a project.

    Loads the project from the database and dispatches per-page tasks as a group.
    Can be chained after other tasks (e.g. PDF replacement).
    """
    with get_db_session(app_env) as (session, query, cfg):
        project_ = query.project(project_slug)
        if not project_:
            raise ValueError(f"Unknown project {project_slug}")

        pages = list(project_.pages)
        if not pages:
            return

        tasks = group(
            replace_ocr_bounding_boxes_for_page.s(
                app_env=app_env,
                project_slug=project_slug,
                page_slug=p.slug,
            )
            for p in pages
        )
        ret = tasks.apply_async()
        ret.save()


def run_ocr_for_project(
    app_env: str,
    project: db.Project,
) -> GroupResult | None:
    """Create a `group` task to run OCR on a project.

    Usage:

    >>> r = run_ocr_for_project(...)
    >>> progress = r.completed_count() / len(r.results)

    :return: the Celery result, or ``None`` if no tasks were run.
    """
    unedited_pages = [p for p in project.pages if p.version == 0]

    if unedited_pages:
        tasks = group(
            run_ocr_for_page.s(
                app_env=app_env,
                project_slug=project.slug,
                page_slug=p.slug,
            )
            for p in unedited_pages
        )
        ret = tasks.apply_async()
        # Save the result so that we can poll for it later. If we don't do
        # this, the result won't be available at all.
        ret.save()
        return ret
    else:
        return None
