"""add index on proof_revisions.created_at

Revision ID: f004ccb008da
Revises: 33d178be9f41
Create Date: 2026-02-20 22:54:30.943529

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "f004ccb008da"
down_revision = "c1a2b3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("proof_revisions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_proof_revisions_created_at"), ["created_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("proof_revisions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_proof_revisions_created_at"))
