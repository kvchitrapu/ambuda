"""Add project source_url

Revision ID: b4c5d6e7f8a9
Revises: a3b1c4d5e6f7
Create Date: 2026-02-11 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "b4c5d6e7f8a9"
down_revision = "a3b1c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proof_projects", sa.Column("source_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("proof_projects", "source_url")
