"""Add summary column to text_reports

Revision ID: a2b3c4d5e6f7
Revises: c1a2b3d4e5f6
Create Date: 2026-02-22 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "a2b3c4d5e6f7"
down_revision = "f004ccb008da"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("text_reports", sa.Column("summary", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("text_reports", "summary")
