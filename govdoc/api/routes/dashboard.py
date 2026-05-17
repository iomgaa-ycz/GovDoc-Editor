"""Dashboard routes — 首页聚合统计。"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter
from sqlmodel import func, select

from govdoc.api.deps import get_db_session
from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    CheckpointFinal,
    Project,
    WorkpaperDraft,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)

_COMPLETED_STATUSES = {"draft_ready", "partial_ready", "finalized"}


def _is_non_compliant(pr: AuditPointRun) -> bool:
    """判断单个 point_run 的 finding 是否为「不合规」。"""
    if not pr.finding_json:
        return False
    try:
        data = json.loads(pr.finding_json)
        verdict = data.get("verdict", {})
        return isinstance(verdict, dict) and verdict.get("verdict") == "不合规"
    except (json.JSONDecodeError, AttributeError):
        return False


def _build_project_map(projects: list[Project]) -> dict[str, dict[str, Any]]:
    """初始化项目摘要映射。"""
    return {
        p.id: {
            "project_id": p.id,
            "name": p.name,
            "audit_status": "idle",
            "point_count": 0,
            "issue_count": 0,
            "last_active": str(p.created_at),
        }
        for p in projects
    }


def _apply_audit_runs(project_map: dict[str, dict[str, Any]], audit_runs: list[AuditRun]) -> None:
    """将 audit_run 状态合入项目摘要。"""
    for r in audit_runs:
        entry = project_map.get(r.project_id)
        if entry is None:
            continue
        entry["point_count"] = max(entry["point_count"], r.total_count)
        entry["last_active"] = str(r.created_at)
        if r.status == "running":
            entry["audit_status"] = "running"
        elif r.status in _COMPLETED_STATUSES and entry["audit_status"] != "running":
            entry["audit_status"] = "completed"


def _apply_issue_counts(
    project_map: dict[str, dict[str, Any]],
    point_runs: list[AuditPointRun],
    audit_runs: list[AuditRun],
) -> None:
    """统计每个项目的不合规数量。"""
    run_to_project = {r.id: r.project_id for r in audit_runs}
    for pr in point_runs:
        if not _is_non_compliant(pr):
            continue
        pid = run_to_project.get(pr.audit_run_id)
        if pid and pid in project_map:
            project_map[pid]["issue_count"] += 1


def compute_dashboard_stats(
    *,
    checkpoints: list[Any],
    projects: list[Project],
    audit_runs: list[AuditRun],
    point_runs_completed: list[AuditPointRun],
    workpaper_count: int,
) -> dict[str, Any]:
    """纯函数：从查询结果计算仪表盘统计数据。"""
    project_map = _build_project_map(projects)
    _apply_audit_runs(project_map, audit_runs)
    _apply_issue_counts(project_map, point_runs_completed, audit_runs)

    recent = sorted(project_map.values(), key=lambda x: x["last_active"], reverse=True)[:10]

    return {
        "checkpoint_count": len(checkpoints),
        "completed_audit_count": sum(1 for r in audit_runs if r.status in _COMPLETED_STATUSES),
        "finding_count": sum(1 for pr in point_runs_completed if _is_non_compliant(pr)),
        "workpaper_count": workpaper_count,
        "recent_projects": recent,
    }


@router.get("/stats")
async def get_dashboard_stats() -> dict[str, Any]:
    """返回首页仪表盘聚合统计。"""
    with get_db_session() as session:
        checkpoints = session.exec(select(CheckpointFinal)).all()
        projects = session.exec(select(Project).order_by(Project.created_at.desc())).all()
        audit_runs = session.exec(select(AuditRun)).all()
        point_runs_completed = session.exec(
            select(AuditPointRun).where(AuditPointRun.status == "completed")
        ).all()
        workpaper_count = session.exec(select(func.count()).select_from(WorkpaperDraft)).one()

        return compute_dashboard_stats(
            checkpoints=checkpoints,
            projects=projects,
            audit_runs=audit_runs,
            point_runs_completed=point_runs_completed,
            workpaper_count=workpaper_count,
        )
