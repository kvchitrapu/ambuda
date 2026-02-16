"""add_text_section_order

Revision ID: 7c6dc61d91bd
Revises: d8e9f0a1b2c3
Create Date: 2026-02-16 10:31:22.641114

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "7c6dc61d91bd"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN, so add as NOT NULL with a
    # server default, backfill, then remove the default.
    op.add_column(
        "text_sections",
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
    )

    # Backfill: assign incrementing order per text_id, ordered by id.
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, text_id FROM text_sections ORDER BY text_id, id")
    ).fetchall()

    current_text_id = None
    order = 0
    for row_id, text_id in rows:
        if text_id != current_text_id:
            current_text_id = text_id
            order = 0
        conn.execute(
            sa.text('UPDATE text_sections SET "order" = :order WHERE id = :id'),
            {"order": order, "id": row_id},
        )
        order += 1

    # Drop the server default now that all rows have explicit values.
    with op.batch_alter_table("text_sections") as batch_op:
        batch_op.alter_column("order", server_default=None)


def downgrade() -> None:
    op.drop_column("text_sections", "order")
