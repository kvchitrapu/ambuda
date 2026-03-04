"""Celery signal handlers for logging task executions to the database."""

import json
import logging
import traceback as tb_module
from datetime import datetime, timezone

from celery.signals import (
    before_task_publish,
    task_prerun,
    task_postrun,
    task_failure,
)

from ambuda.models.celery_task_log import CeleryTaskLog
from ambuda.tasks.utils import get_db_session

logger = logging.getLogger(__name__)


def _get_app_env():
    import os

    return os.getenv("AMBUDA_ENVIRONMENT", "development")


def _now():
    return datetime.now(timezone.utc)


@before_task_publish.connect
def on_before_task_publish(sender=None, headers=None, body=None, **kwargs):
    """Create the CeleryTaskLog row when a task is published."""
    try:
        task_id = headers.get("id") if headers else None
        if not task_id:
            return

        task_name = sender or headers.get("task", "unknown")
        initiated_by = (headers.get("initiated_by") or None) if headers else None

        # body is (args, kwargs, embed) for v2 protocol
        args_val = None
        kwargs_val = None
        if body:
            if isinstance(body, (list, tuple)) and len(body) >= 2:
                args_val = json.dumps(body[0]) if body[0] else None
                kwargs_val = json.dumps(body[1]) if body[1] else None

        app_env = _get_app_env()
        with get_db_session(app_env) as (session, q, cfg):
            log = CeleryTaskLog(
                task_id=task_id,
                task_name=task_name,
                args=args_val,
                kwargs=kwargs_val,
                initiated_by=initiated_by,
                status="PENDING",
            )
            session.add(log)
            session.commit()
    except Exception:
        logger.exception("Failed to log task publish for %s", sender)


@task_prerun.connect
def on_task_prerun(sender=None, task_id=None, **kwargs):
    """Mark the task as STARTED and record started_at."""
    try:
        app_env = _get_app_env()
        with get_db_session(app_env) as (session, q, cfg):
            log = session.query(CeleryTaskLog).filter_by(task_id=task_id).first()
            if log:
                log.status = "STARTED"
                log.started_at = _now()
                session.commit()
    except Exception:
        logger.exception("Failed to log task prerun for %s", task_id)


@task_postrun.connect
def on_task_postrun(sender=None, task_id=None, state=None, **kwargs):
    """Mark the task as SUCCESS/FAILURE and record duration."""
    try:
        app_env = _get_app_env()
        with get_db_session(app_env) as (session, q, cfg):
            log = session.query(CeleryTaskLog).filter_by(task_id=task_id).first()
            if log:
                log.status = state or "UNKNOWN"
                log.completed_at = _now()
                if log.started_at:
                    started = log.started_at
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    delta = log.completed_at - started
                    log.duration_sec = delta.total_seconds()
                session.commit()
    except Exception:
        logger.exception("Failed to log task postrun for %s", task_id)


@task_failure.connect
def on_task_failure(
    sender=None, task_id=None, exception=None, traceback=None, **kwargs
):
    """Record error details on task failure."""
    try:
        app_env = _get_app_env()
        with get_db_session(app_env) as (session, q, cfg):
            log = session.query(CeleryTaskLog).filter_by(task_id=task_id).first()
            if log:
                log.error_type = type(exception).__name__ if exception else None
                log.error_message = str(exception) if exception else None
                if traceback:
                    log.traceback = "".join(tb_module.format_tb(traceback))
                session.commit()
    except Exception:
        logger.exception("Failed to log task failure for %s", task_id)
