"""P0 拆分 golden 采集：对 audit_case_01 fixture 采集 DB 字段快照 + 文件树 hash。

用途：在拆分前跑一次作为 baseline，拆分后再跑一次对比。
排除不稳定字段（时间戳 / UUID / 路径前缀）。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    WorkpaperDraft,
)


# 不稳定字段（每次跑都会变），diff 时排除
UNSTABLE_FIELDS = {
    # 主键 / 时间戳
    "id",
    "created_at",
    "updated_at",
    "completed_at",
    "heartbeat_at",
    # 绝对/相对路径字段（每次 tmp_path 不同）
    "workspace_archive_path",
    "workspace_failed_path",
    "docx_path",
    # FK UUID 字段（每次 seed 时 SQLModel 生成新 UUID）
    "audit_run_id",
    "project_id",
    "tender_doc_id",
    "supplementary_doc_ids",
    "checkpoint_final_id",
    # FK UUID 列表的 JSON string 形式
    "checkpoint_final_ids",
    # raw finding JSON（内容已在 AuditGolden.findings 里解析出来，避免重复 + 防嵌入式引用）
    "finding_json",
    # workpaper 的 JSON blob（内含 project_id UUID + generated_at 时间戳；
    # findings 内容已在 AuditGolden.findings 解析出来，summary 由 _assemble_workpaper_draft 的单测覆盖）
    "workpaper_json",
    # usage stats 可能带 timing / tokens 数字，不确定是否稳定
    "usage_json",
}


def _sanitize(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k not in UNSTABLE_FIELDS}


@dataclass
class AuditGolden:
    audit_run: dict[str, Any]
    point_runs: list[dict[str, Any]]  # sorted by checkpoint_final_id
    findings: list[dict[str, Any]]  # parsed + sorted by checkpoint_id
    workpaper_drafts: list[dict[str, Any]]  # sorted by version


def capture(session: Session, audit_run_id: str) -> AuditGolden:
    """采集 DB 终态为可比较的 dict。"""
    audit_run = session.get(AuditRun, audit_run_id)
    assert audit_run is not None

    point_runs = session.exec(
        select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run_id)
    ).all()
    point_runs_sorted = sorted(point_runs, key=lambda pr: pr.checkpoint_final_id)

    findings = []
    for pr in point_runs_sorted:
        if pr.finding_json:
            findings.append(json.loads(pr.finding_json))
    findings.sort(key=lambda f: f.get("checkpoint", {}).get("id", ""))

    drafts = session.exec(
        select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == audit_run_id)
    ).all()
    drafts_sorted = sorted(drafts, key=lambda d: d.version)

    return AuditGolden(
        audit_run=_sanitize(audit_run.model_dump()),
        point_runs=[_sanitize(pr.model_dump()) for pr in point_runs_sorted],
        findings=findings,
        workpaper_drafts=[_sanitize(d.model_dump()) for d in drafts_sorted],
    )


def write_golden(golden: AuditGolden, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(golden), ensure_ascii=False, indent=2, sort_keys=True))


def load_golden(path: Path) -> AuditGolden:
    data = json.loads(path.read_text())
    return AuditGolden(**data)
