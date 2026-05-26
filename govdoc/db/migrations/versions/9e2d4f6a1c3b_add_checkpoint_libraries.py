"""add checkpoint libraries

Revision ID: 9e2d4f6a1c3b
Revises: d08dafa25255
Create Date: 2026-05-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "9e2d4f6a1c3b"
down_revision = "d08dafa25255"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkpointlibrary",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "checkpointlibraryitem",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("library_id", sa.String(), nullable=False),
        sa.Column("checkpoint_final_id", sa.String(), nullable=False),
        sa.Column("added_by", sa.String(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["library_id"], ["checkpointlibrary.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "library_id",
            "checkpoint_final_id",
            name="uq_checkpointlibraryitem_library_checkpoint",
        ),
    )
    op.add_column("auditrun", sa.Column("checkpoint_library_id", sa.String(), nullable=True))
    op.add_column(
        "auditrun",
        sa.Column("checkpoint_library_name_snapshot", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("auditrun", "checkpoint_library_name_snapshot")
    op.drop_column("auditrun", "checkpoint_library_id")
    op.drop_table("checkpointlibraryitem")
    op.drop_table("checkpointlibrary")
