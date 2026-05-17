"""工作底稿定稿与 CaseLibrary 回灌。

设计基线：docs/design.md §10.2 / docs/TD.md T1.8。

两种定稿模式：
- partial=True：基于已完成 findings 生成 WorkpaperDraft，不写 WorkpaperFinal / CaseLibrary
- partial=False（完整定稿）：写 WorkpaperFinal + CaseLibrary 回灌 + 状态改为 finalized
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from govdoc.db.models import AuditPointRun, AuditRun, TenderDoc, WorkpaperDraft, WorkpaperFinal
from govdoc.pipelines.summary import generate_summary
from govdoc.runtime import get_libraries
from govdoc.schemas import GovFinding, Workpaper


def workpaper_to_markdown(workpaper: Workpaper) -> str:
    lines = [
        f"# 项目工作底稿：{workpaper.project_id}",
        "",
        f"招标文书：`{workpaper.tender_doc_path}`",
        "",
        "## 总结",
        workpaper.summary or "（待补充）",
        "",
        "## Findings",
    ]
    for index, finding in enumerate(workpaper.findings, start=1):
        lines.extend(
            [
                f"### {index}. {finding.checkpoint.title}",
                f"- 类别：{finding.checkpoint.category}",
                f"- 严重程度：{finding.checkpoint.severity}",
                f"- 结论：{finding.verdict.verdict}",
                f"- 理由：{finding.verdict.rationale}",
                f"- 建议：{finding.verdict.suggestion or '（无）'}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


async def finalize_workpaper(
    audit_run_id: str,
    *,
    approved_by: str,
    session: Session,
    partial: bool = False,
) -> WorkpaperDraft | WorkpaperFinal:
    audit_run = session.get(AuditRun, audit_run_id)
    if audit_run is None:
        raise ValueError(f"未找到 AuditRun: {audit_run_id}")

    if partial:
        return await _finalize_partial(audit_run, approved_by, session)
    else:
        return await _finalize_full(audit_run, approved_by, session)


async def _finalize_partial(
    audit_run: AuditRun,
    approved_by: str,
    session: Session,
) -> WorkpaperDraft:
    """部分定稿：从已完成 findings 生成/更新 WorkpaperDraft，不改终态。"""
    completed = session.exec(
        select(AuditPointRun).where(
            AuditPointRun.audit_run_id == audit_run.id,
            AuditPointRun.status == "completed",
            AuditPointRun.finding_json.is_not(None),
        )
    ).all()

    if not completed:
        raise ValueError(f"AuditRun {audit_run.id} 没有已完成的审核点")

    findings = [GovFinding.model_validate_json(pr.finding_json) for pr in completed]
    tender_doc = session.get(TenderDoc, audit_run.tender_doc_id)
    workpaper = Workpaper(
        project_id=audit_run.project_id,
        tender_doc_path=tender_doc.storage_path if tender_doc is not None else "",
        findings=findings,
        summary=generate_summary(findings),
    )

    current_drafts = session.exec(
        select(WorkpaperDraft).where(WorkpaperDraft.audit_run_id == audit_run.id)
    ).all()
    next_version = max((d.version for d in current_drafts), default=0) + 1

    from govdoc.workpaper_renderer import render_workpaper_docx

    draft_path = render_workpaper_docx(workpaper, audit_run.id, version=next_version)

    draft = WorkpaperDraft(
        audit_run_id=audit_run.id,
        workpaper_json=workpaper.model_dump_json(),
        docx_path=str(draft_path),
        version=next_version,
    )
    session.add(draft)

    # partial 不改 AuditRun 终态，保持 partial_ready 让专家继续修订
    if audit_run.status == "partial_ready":
        audit_run.status = "partial_ready"
    session.add(audit_run)
    session.commit()
    session.refresh(draft)
    return draft


async def _finalize_full(
    audit_run: AuditRun,
    approved_by: str,
    session: Session,
) -> WorkpaperFinal:
    """完整定稿：写 WorkpaperFinal + CaseLibrary 回灌。"""
    drafts = session.exec(
        select(WorkpaperDraft)
        .where(WorkpaperDraft.audit_run_id == audit_run.id)
        .order_by(WorkpaperDraft.version.desc())
    ).all()
    if not drafts:
        raise ValueError(f"AuditRun {audit_run.id} 没有 WorkpaperDraft，无法定稿")

    latest_draft = drafts[0]
    workpaper = Workpaper.model_validate_json(latest_draft.workpaper_json)
    final_md = workpaper_to_markdown(workpaper)

    # CaseLibrary 回灌
    rule_library, case_library, template_library = get_libraries()
    entry = case_library.add(
        entry_id=f"case_{audit_run.id}",
        markdown=final_md,
        metadata={
            "project_id": audit_run.project_id,
            "approved_at": datetime.utcnow().isoformat(),
            "approved_by": approved_by,
        },
    )

    final = WorkpaperFinal(
        audit_run_id=audit_run.id,
        workpaper_json=latest_draft.workpaper_json,
        docx_path=latest_draft.docx_path,
        approved_by=approved_by,
        case_library_entry_id=entry.entry_id,
    )
    session.add(final)

    audit_run.status = "finalized"
    session.add(audit_run)
    session.commit()
    session.refresh(final)
    return final
