"""add publish_configs table

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-02-28 00:00:00.000000

"""

import json
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def _table_exists(conn, name):
    result = conn.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": name},
    ).fetchone()
    return result is not None


def _column_exists(conn, table, column):
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in rows)


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create publish_configs table (may already exist via create_all)
    if not _table_exists(conn, "publish_configs"):
        op.create_table(
            "publish_configs",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column(
                "project_id",
                sa.Integer,
                sa.ForeignKey("proof_projects.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "text_id",
                sa.Integer,
                sa.ForeignKey("texts.id"),
                nullable=True,
                index=True,
            ),
            sa.Column("order", sa.Integer, nullable=False),
            sa.Column("slug", sa.String, nullable=False),
            sa.Column("title", sa.String, nullable=False),
            sa.Column("target", sa.String, nullable=True),
            sa.Column("author", sa.String, nullable=True),
            sa.Column("genre", sa.String, nullable=True),
            sa.Column("language", sa.String, nullable=False, server_default="sa"),
            sa.Column("parent_slug", sa.String, nullable=True),
        )

    # 2. Migrate data from Project.config JSON to publish_configs rows
    if _column_exists(conn, "proof_projects", "config"):
        # Only migrate if the table is empty (avoid double-insert on re-run)
        existing = conn.execute(
            sa.text("SELECT COUNT(*) FROM publish_configs")
        ).scalar()
        if existing == 0:
            projects = conn.execute(
                sa.text(
                    "SELECT id, config FROM proof_projects WHERE config IS NOT NULL"
                )
            ).fetchall()

            for project_id, config_json in projects:
                if not config_json:
                    continue
                try:
                    config = config_json
                    # The column may be double-encoded (JSON string stored as
                    # JSON text), so unwrap until we get a dict.
                    while isinstance(config, str):
                        config = json.loads(config)
                    if not isinstance(config, dict):
                        continue
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue

                publish_list = config.get("publish", [])
                for order, pc in enumerate(publish_list):
                    slug = pc.get("slug", "")
                    if not slug:
                        continue

                    # Look up matching Text by slug to set text_id
                    text_row = conn.execute(
                        sa.text("SELECT id FROM texts WHERE slug = :slug"),
                        {"slug": slug},
                    ).fetchone()
                    text_id = text_row[0] if text_row else None

                    conn.execute(
                        sa.text(
                            "INSERT INTO publish_configs "
                            '(project_id, text_id, "order", slug, title, target, author, genre, language, parent_slug) '
                            "VALUES (:project_id, :text_id, :order, :slug, :title, :target, :author, :genre, :language, :parent_slug)"
                        ),
                        {
                            "project_id": project_id,
                            "text_id": text_id,
                            "order": order,
                            "slug": slug,
                            "title": pc.get("title", ""),
                            "target": pc.get("target"),
                            "author": pc.get("author"),
                            "genre": pc.get("genre"),
                            "language": pc.get("language", "sa"),
                            "parent_slug": pc.get("parent_slug"),
                        },
                    )

        # 3. Drop the config column from proof_projects
        with op.batch_alter_table("proof_projects") as batch_op:
            batch_op.drop_column("config")


def downgrade() -> None:
    conn = op.get_bind()

    # Re-add config column
    if not _column_exists(conn, "proof_projects", "config"):
        with op.batch_alter_table("proof_projects") as batch_op:
            batch_op.add_column(sa.Column("config", sa.JSON, nullable=True))

    # Migrate data back from publish_configs to JSON
    if _table_exists(conn, "publish_configs"):
        rows = conn.execute(
            sa.text(
                "SELECT project_id, slug, title, target, author, genre, language, parent_slug "
                'FROM publish_configs ORDER BY project_id, "order"'
            )
        ).fetchall()

        from collections import defaultdict

        by_project: dict[int, list] = defaultdict(list)
        for row in rows:
            pc = {
                "slug": row[1],
                "title": row[2],
            }
            if row[3]:
                pc["target"] = row[3]
            if row[4]:
                pc["author"] = row[4]
            if row[5]:
                pc["genre"] = row[5]
            if row[6] and row[6] != "sa":
                pc["language"] = row[6]
            if row[7]:
                pc["parent_slug"] = row[7]
            by_project[row[0]].append(pc)

        for project_id, configs in by_project.items():
            config_json = json.dumps({"publish": configs, "pages": []})
            conn.execute(
                sa.text("UPDATE proof_projects SET config = :config WHERE id = :id"),
                {"config": config_json, "id": project_id},
            )

        op.drop_table("publish_configs")
