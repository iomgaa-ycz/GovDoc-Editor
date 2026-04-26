"""add_supplementary_doc_ids_to_auditrun

Revision ID: b42e4f56c9a1
Revises: fd7c32702049
Create Date: 2026-04-26 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b42e4f56c9a1"
down_revision = "fd7c32702049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auditrun", sa.Column("supplementary_doc_ids", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("auditrun", "supplementary_doc_ids")
