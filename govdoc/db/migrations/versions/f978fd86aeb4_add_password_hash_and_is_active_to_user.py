"""add_password_hash_and_is_active_to_user

Revision ID: f978fd86aeb4
Revises: f7a00cce372b
Create Date: 2026-05-22 18:00:13.953861
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "f978fd86aeb4"
down_revision = "f7a00cce372b"
branch_labels = None
depends_on = None

# bcrypt hash of a random string — 合法但不可登录
_INACTIVE_PASSWORD_HASH = "$2b$12$WfIZHxXOkJd8QEuWzGzR2eCXVJl7zYOqlmEMBfO3LY6UiJPpIXRSy"


def upgrade() -> None:
    op.add_column('user', sa.Column('password_hash', sa.String(), nullable=True))
    op.add_column('user', sa.Column('is_active', sa.Boolean(), nullable=True))
    # 存量用户回填：合法 bcrypt hash（不可登录）+ is_active=True
    op.execute(
        f"UPDATE \"user\" SET password_hash = '{_INACTIVE_PASSWORD_HASH}', is_active = 1 "
        "WHERE password_hash IS NULL"
    )
    # SQLite 不支持 ALTER COLUMN，使用 batch_alter_table
    with op.batch_alter_table('user') as batch_op:
        batch_op.alter_column('password_hash', nullable=False)
        batch_op.alter_column('is_active', nullable=False)
    op.create_index(op.f('ix_user_username'), 'user', ['username'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_username'), table_name='user')
    op.drop_column('user', 'is_active')
    op.drop_column('user', 'password_hash')
