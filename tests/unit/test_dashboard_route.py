"""Dashboard 聚合统计接口测试。"""

import json
from unittest.mock import MagicMock

from govdoc.api.routes.dashboard import compute_dashboard_stats
from govdoc.db.models import AuditPointRun, AuditRun, Project


def _make_project(pid: str, name: str) -> Project:
    p = Project(name=name, created_by="test")
    p.id = pid
    return p


def _make_audit_run(rid: str, pid: str, status: str, total: int, processed: int) -> AuditRun:
    r = AuditRun(
        project_id=pid,
        tender_doc_id="td-1",
        checkpoint_final_ids="[]",
        status=status,
        total_count=total,
        processed_count=processed,
    )
    r.id = rid
    return r


def test_dashboard_stats_counts():
    """验证 compute_dashboard_stats 正确统计各维度数据。"""
    checkpoints = [MagicMock() for _ in range(5)]
    projects = [_make_project("p1", "项目A"), _make_project("p2", "项目B")]
    audit_runs = [
        _make_audit_run("r1", "p1", "draft_ready", 10, 10),
        _make_audit_run("r2", "p2", "running", 8, 3),
    ]
    findings_data = [
        {"verdict": {"verdict": "不合规"}},
        {"verdict": {"verdict": "合规"}},
        {"verdict": {"verdict": "不合规"}},
    ]
    point_runs = []
    for i, f in enumerate(findings_data):
        pr = AuditPointRun(audit_run_id="r1", checkpoint_final_id=f"cp-{i}")
        pr.finding_json = json.dumps(f, ensure_ascii=False)
        pr.status = "completed"
        point_runs.append(pr)

    stats = compute_dashboard_stats(
        checkpoints=checkpoints,
        projects=projects,
        audit_runs=audit_runs,
        point_runs_completed=point_runs,
        workpaper_count=2,
    )

    assert stats["checkpoint_count"] == 5
    assert stats["completed_audit_count"] == 1
    assert stats["finding_count"] == 2
    assert stats["workpaper_count"] == 2
    assert len(stats["recent_projects"]) == 2
