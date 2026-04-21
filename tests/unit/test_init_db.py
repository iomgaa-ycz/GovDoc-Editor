"""验证 init_db 通过 alembic 管理 schema。"""

from unittest.mock import MagicMock, patch


def test_init_db_calls_alembic_upgrade():
    """init_db 必须调用 alembic.command.upgrade(cfg, 'head')。"""
    with patch("govdoc.db.session.alembic_command") as mock_cmd:
        from govdoc.db.session import init_db

        init_db()

        mock_cmd.upgrade.assert_called_once()
        args = mock_cmd.upgrade.call_args
        assert args[0][1] == "head"
