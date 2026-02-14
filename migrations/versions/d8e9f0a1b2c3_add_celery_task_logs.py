"""Add celery_task_logs table

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-02-14 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "celery_task_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(255), nullable=False),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("args", sa.Text(), nullable=True),
        sa.Column("kwargs", sa.Text(), nullable=True),
        sa.Column("initiated_by", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("error_type", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_celery_task_logs_task_id"),
        "celery_task_logs",
        ["task_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_celery_task_logs_task_name"),
        "celery_task_logs",
        ["task_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_celery_task_logs_status"),
        "celery_task_logs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_celery_task_logs_status"), table_name="celery_task_logs")
    op.drop_index(op.f("ix_celery_task_logs_task_name"), table_name="celery_task_logs")
    op.drop_index(op.f("ix_celery_task_logs_task_id"), table_name="celery_task_logs")
    op.drop_table("celery_task_logs")
