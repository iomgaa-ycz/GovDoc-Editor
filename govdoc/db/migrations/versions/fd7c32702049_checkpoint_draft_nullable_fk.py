"""checkpoint_draft_nullable_fk

Revision ID: fd7c32702049
Revises: 0001_initial
Create Date: 2026-04-19 09:16:59.648991

SQLite 不支持 ALTER COLUMN，使用 batch_alter_table 做表重建。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "fd7c32702049"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite 不支持 ALTER COLUMN，需要用 batch_alter_table（表重建）
    with op.batch_alter_table("checkpointdraft") as batch_op:
        batch_op.alter_column(
            "rule_source_id",
            existing_type=sa.VARCHAR(),
            nullable=True,
        )
        batch_op.alter_column(
            "extract_run_id",
            existing_type=sa.VARCHAR(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("checkpointdraft") as batch_op:
        batch_op.alter_column(
            "extract_run_id",
            existing_type=sa.VARCHAR(),
            nullable=False,
        )
        batch_op.alter_column(
            "rule_source_id",
            existing_type=sa.VARCHAR(),
            nullable=False,
        )
