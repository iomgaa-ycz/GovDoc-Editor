"""remove_checkpointdraft

Revision ID: 20260427_remove_checkpointdraft
Revises: b42e4f56c9a1
Create Date: 2026-04-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260427_remove_checkpointdraft"
down_revision = "b42e4f56c9a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO checkpointfinal (id, payload_json, approved_by, approved_at)
        SELECT d.id, d.payload_json, 'migration:checkpoint-draft', CURRENT_TIMESTAMP
        FROM checkpointdraft AS d
        WHERE d.status != 'promoted'
          AND NOT EXISTS (
            SELECT 1 FROM checkpointfinal AS f WHERE f.id = d.id
          )
        """
    )
    op.drop_table("checkpointdraft")


def downgrade() -> None:
    op.create_table(
        "checkpointdraft",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rule_source_id", sa.String(), nullable=True),
        sa.Column("payload_json", sa.String(), nullable=False),
        sa.Column("extract_run_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["rule_source_id"], ["rulesource.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        """
        INSERT INTO checkpointdraft
            (id, rule_source_id, payload_json, extract_run_id, status, created_at)
        SELECT id, NULL, payload_json, NULL, 'promoted', approved_at
        FROM checkpointfinal
        """
    )
