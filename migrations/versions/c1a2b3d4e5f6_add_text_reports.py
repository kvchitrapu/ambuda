"""Add text_reports table

Revision ID: c1a2b3d4e5f6
Revises: b0128aaa942b
Create Date: 2026-02-19 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c1a2b3d4e5f6"
down_revision = "b0128aaa942b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "text_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("text_id", sa.Integer(), sa.ForeignKey("texts.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("text_reports")
