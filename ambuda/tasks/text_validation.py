import logging
from datetime import UTC, datetime

from ambuda import database as db
from ambuda.tasks import app
from ambuda.tasks.utils import get_db_session, get_redis
from ambuda.utils.text_validation import validate_text, ValidationReport

REPORT_LOCK_TTL = 300  # seconds


def maybe_rerun_report(text_id: int, app_environment: str, redis_client=None) -> bool:
    """Trigger a report re-run if no other re-run is in progress for this text."""
    r = redis_client or get_redis()
    lock_key = db.TextReport.rerun_lock_key(text_id)

    if r.set(lock_key, "1", nx=True, ex=REPORT_LOCK_TTL):
        run_report.apply_async(args=(text_id, app_environment))
        return True
    return False


def run_report_inner(
    text_id: int, app_environment: str, engine=None, redis_client=None
) -> None:
    """Compute and store a validation report for the given text.

    ``engine`` is exposed for testing.
    """
    with get_db_session(app_environment, engine=engine) as (session, q, config):
        text = session.get(db.Text, text_id)
        if not text:
            raise ValueError(f"Text with id {text_id} not found")

        logging.info(f"Running validation report for {text.slug}")
        report = validate_text(text)
        payload = report.model_dump()
        summary = report.summary.model_dump()

        # Upsert: update existing report or create new one.
        existing = (
            session.query(db.TextReport)
            .filter_by(text_id=text_id)
            .order_by(db.TextReport.created_at.desc())
            .first()
        )

        now = datetime.now(UTC)
        if existing:
            existing.payload = payload
            existing.summary = summary
            existing.updated_at = now
            logging.info(f"Updated existing TextReport for text {text.slug}")
        else:
            text_report = db.TextReport(
                text_id=text_id,
                payload=payload,
                summary=summary,
                created_at=now,
                updated_at=now,
            )
            session.add(text_report)
            logging.info(f"Created new TextReport for text {text.slug}")

        session.commit()

        r = redis_client or get_redis()
        r.delete(db.TextReport.rerun_lock_key(text_id))


@app.task(bind=True)
def run_report(self, text_id: int, app_environment: str):
    run_report_inner(text_id, app_environment)
