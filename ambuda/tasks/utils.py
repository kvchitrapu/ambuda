import logging
from contextlib import contextmanager

from celery import states
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config
from ambuda import queries


class TaskStatus:
    """Helper class to track progress on a task.

    - For Celery tasks, use CeleryTaskStatus.
    - For local usage (unit tests, CLI, ...), use a LocalTaskStatus instead.
    """

    def progress(self, current: int, total: int, **extra):
        """Update the task's progress.

        :param current: progress numerator
        :param total: progress denominator
        :param extra: additional progress fields (e.g. upload_current, upload_total)
        """
        raise NotImplementedError

    def success(self, num_pages: int, slug: str, **extra):
        """Mark the task as a success.

        # FIXME(arun): make this API more generic.
        """
        raise NotImplementedError

    def failure(self, message: str):
        """Mark the task as failed."""
        raise NotImplementedError


class CeleryTaskStatus(TaskStatus):
    """Helper class to track progress on a Celery task."""

    def __init__(self, task):
        self.task = task

    def progress(self, current: int, total: int, **extra):
        """Update the task's progress.

        :param current: progress numerator
        :param total: progress denominator
        :param extra: additional progress fields (e.g. upload_current, upload_total)
        """
        # Celery doesn't have a "PROGRESS" state, so just use a hard-coded string.
        meta = {"current": current, "total": total}
        meta.update(extra)
        self.task.update_state(state="PROGRESS", meta=meta)

    def success(self, num_pages: int, slug: str, **extra):
        """Mark the task as a success."""
        meta = {"current": num_pages, "total": num_pages, "slug": slug}
        meta.update(extra)
        self.task.update_state(state=states.SUCCESS, meta=meta)

    def failure(self, message: str):
        """Mark the task as failed."""
        self.task.update_state(state=states.FAILURE, meta={"message": message})


class LocalTaskStatus(TaskStatus):
    """Helper class to track progress on a task running locally."""

    def progress(self, current: int, total: int, **extra):
        logging.info(f"{current} / {total} complete")
        if extra.get("upload_current") is not None:
            logging.info(
                f"  uploads: {extra['upload_current']} / {extra.get('upload_total', '?')}"
            )

    def success(self, num_pages: int, slug: str, **extra):
        logging.info(f"Succeeded. Project is at {slug}.")
        if extra.get("failed_pages"):
            logging.warning(f"  failed pages: {extra['failed_pages']}")

    def failure(self, message: str):
        logging.info(f"Failed. ({message})")


def apply_async_as(task, args=None, kwargs=None, user=None, **options):
    """Call task.apply_async with initiated_by header set to the user's username."""
    headers = options.pop("headers", {}) or {}
    if user:
        headers["initiated_by"] = user.username
    return task.apply_async(args=args, kwargs=kwargs, headers=headers, **options)


def delay_as(task, user, *args, **kwargs):
    """Convenience wrapper: task.delay(...) with initiated_by set."""
    headers = {}
    if user:
        headers["initiated_by"] = user.username
    return task.apply_async(args=args, kwargs=kwargs, headers=headers)


@contextmanager
def get_db_session(app_env: str, engine=None):
    """Get a database session for the given app environment.

    `engine` is for dependency injection.
    """
    cfg = config.load_config_object(app_env)

    if engine is None:
        engine = create_engine(cfg.SQLALCHEMY_DATABASE_URI)
        should_dispose = True
    else:
        should_dispose = False

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    q = queries.Query(session)

    try:
        yield session, q, cfg
    finally:
        session.close()
        if should_dispose:
            engine.dispose()
