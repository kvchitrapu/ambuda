"""Model for logging Celery task executions."""

from sqlalchemy import Column, DateTime, Float, String, Text

from ambuda.models.base import Base, pk


class CeleryTaskLog(Base):
    __tablename__ = "celery_task_logs"

    id = pk()
    task_id = Column(String(255), unique=True, nullable=False, index=True)
    task_name = Column(String(255), nullable=False, index=True)
    args = Column(Text, nullable=True)
    kwargs = Column(Text, nullable=True)
    initiated_by = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="PENDING", index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_sec = Column(Float, nullable=True)
    error_type = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)
    traceback = Column(Text, nullable=True)
