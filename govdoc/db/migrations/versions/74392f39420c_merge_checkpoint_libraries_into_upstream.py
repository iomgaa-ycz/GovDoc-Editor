"""merge checkpoint_libraries into upstream

Revision ID: 74392f39420c
Revises: 20b48994c587, 9e2d4f6a1c3b
Create Date: 2026-05-28 10:17:38.509286
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "74392f39420c"
down_revision = ("20b48994c587", "9e2d4f6a1c3b")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

