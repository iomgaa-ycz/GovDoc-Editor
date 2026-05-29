"""add status to checkpointfinal

Revision ID: 5af3263fae83
Revises: 74392f39420c
Create Date: 2026-05-29 00:21:58.431104
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "5af3263fae83"
down_revision = "74392f39420c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite 需用 batch 模式加列；server_default 保证存量行回填 active
    with op.batch_alter_table("checkpointfinal") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(), nullable=False, server_default="active")
        )


def downgrade() -> None:
    with op.batch_alter_table("checkpointfinal") as batch_op:
        batch_op.drop_column("status")
