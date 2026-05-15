"""AuditRun heartbeat helper tests."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from govdoc.pipelines.audit_tender import _update_heartbeat


class TestUpdateHeartbeat:
    def test_updates_heartbeat_and_commits(self):
        audit_run = SimpleNamespace(heartbeat_at=None)
        session = MagicMock()

        _update_heartbeat(audit_run, session)

        assert isinstance(audit_run.heartbeat_at, datetime)
        session.add.assert_called_once_with(audit_run)
        session.commit.assert_called_once_with()
