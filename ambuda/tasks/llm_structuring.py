"""Background tasks for structuring proofing pages with LLMs."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ambuda import consts
from ambuda import database as db
from ambuda.tasks import app
from ambuda.tasks.utils import CeleryTaskStatus, TaskStatus, get_db_session
from ambuda.utils import llm_structuring
from ambuda.utils.revisions import add_revision


def _run_structuring_for_page_inner(
    app_env: str,
    project_slug: str,
    page_slug: str,
    prompt_template: str = llm_structuring.DEFAULT_STRUCTURING_PROMPT,
) -> int:
    with get_db_session(app_env) as (session, query, config_obj):
        bot_user = query.user(consts.BOT_USERNAME)
        if not bot_user:
            raise ValueError(f'User "{consts.BOT_USERNAME}" is not defined.')

        project = query.project(project_slug)
        page = query.page(project.id, page_slug)

        latest_revision = (
            session.query(db.Revision)
            .filter(db.Revision.page_id == page.id)
            .order_by(db.Revision.created_at.desc())
            .first()
        )

        api_key = config_obj.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        if not latest_revision or not latest_revision.content:
            raise ValueError(f"No content found for page {project_slug}/{page_slug}")
        current_content = latest_revision.content

        structured_content = llm_structuring.run(
            current_content, api_key, prompt_template
        )

        summary = "Apply LLM structuring"
        try:
            return add_revision(
                page=page,
                summary=summary,
                content=structured_content,
                version=page.version,
                author_id=bot_user.id,
                # keep the same status as before
                status_id=page.status_id,
            )
        except Exception as e:
            raise ValueError(
                f'Structuring failed for page "{project.slug}/{page.slug}".'
            ) from e


@app.task(bind=True)
def run_structuring_for_page(
    self,
    *,
    app_env: str,
    project_slug: str,
    page_slug: str,
    prompt_template: str = llm_structuring.DEFAULT_STRUCTURING_PROMPT,
):
    _run_structuring_for_page_inner(
        app_env,
        project_slug,
        page_slug,
        prompt_template,
    )


def run_structuring_for_project_inner(
    *,
    app_env: str,
    project_slug: str,
    task_status: TaskStatus,
    prompt_template: str = llm_structuring.DEFAULT_STRUCTURING_PROMPT,
    max_workers: int = 4,
):
    """Run LLM structuring on all edited pages using threads.

    :param app_env: the app environment.
    :param project_slug: the project slug.
    :param task_status: tracks progress on the task.
    :param prompt_template: the prompt template for structuring.
    :param max_workers: max concurrent threads.
    """
    with get_db_session(app_env) as (session, query, cfg):
        project_ = query.project(project_slug)
        if not project_:
            raise ValueError(f"Unknown project {project_slug}")
        page_slugs = [p.slug for p in project_.pages if p.version > 0]

    if not page_slugs:
        task_status.success(0, project_slug)
        return

    total = len(page_slugs)
    completed = [0]
    task_status.progress(0, total)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_slug = {}
        for slug in page_slugs:
            fut = executor.submit(
                _run_structuring_for_page_inner,
                app_env,
                project_slug,
                slug,
                prompt_template,
            )
            future_to_slug[fut] = slug

        for fut in as_completed(future_to_slug):
            slug = future_to_slug[fut]
            try:
                fut.result()
            except Exception:
                logging.exception(f"Structuring failed for page {project_slug}/{slug}")
            completed[0] += 1
            task_status.progress(completed[0], total)

    task_status.success(total, project_slug)


@app.task(bind=True)
def run_structuring_for_project(
    self,
    *,
    app_env: str,
    project_slug: str,
    prompt_template: str = llm_structuring.DEFAULT_STRUCTURING_PROMPT,
):
    """Run LLM structuring on all edited pages in a project.

    Uses threads within a single Celery task instead of dispatching
    one task per page, reducing worker memory pressure.
    """
    task_status = CeleryTaskStatus(self)
    run_structuring_for_project_inner(
        app_env=app_env,
        project_slug=project_slug,
        task_status=task_status,
        prompt_template=prompt_template,
    )
