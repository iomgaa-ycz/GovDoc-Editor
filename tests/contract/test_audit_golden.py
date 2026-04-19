"""P0 拆分的 golden 对比测试。

流程：
1. 首次跑：采集当前行为的 golden 到 tests/contract/golden/audit_case_01.json（skip）
2. 拆分后跑：与 golden 对比，要求 diff 为 0

注意：本测试只在 replay 模式下运行（确定性），不吃真 LLM。
实现参考 tests/contract/test_pipeline_b_with_mocks.py::test_pipeline_b_with_mock_pes_replay 的 inline setup。
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from scrivai import FakeTrajectoryStore, TempWorkspaceManager

from govdoc.db.models import (
    AuditPointRun,
    AuditRun,
    CheckpointFinal,
    Project,
    TenderDoc,
)
from govdoc.pipelines.audit_tender import run_audit
from tests.contract.golden.capture import capture, load_golden, write_golden
from tests.contract.test_pipeline_b_with_mocks import _write_test_config


GOLDEN_PATH = Path(__file__).parent / "golden" / "audit_case_01.json"


def test_audit_case_01_golden_match(monkeypatch, tmp_path):
    """跑 audit_case_01，采集结果，和 golden 对比。首次跑自动生成 golden（skip）。"""
    repo_root = Path(__file__).resolve().parents[2]
    fixtures_root = repo_root / "tests" / "fixtures"
    monkeypatch.setenv("GOVDOC_FIXTURES", str(fixtures_root))
    monkeypatch.setenv("GOVDOC_CONFIG_PATH", str(_write_test_config(tmp_path)))

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    checkpoints_payload = json.loads(
        (fixtures_root / "checkpoints_golden.json").read_text(encoding="utf-8")
    )["checkpoints"]

    with Session(engine) as session:
        project = Project(name="golden 测试项目", created_by="tester")
        session.add(project)
        session.commit()
        session.refresh(project)

        tender_doc = TenderDoc(
            project_id=project.id,
            filename="tender_small.docx",
            storage_path="tests/fixtures/tender_small.docx",
            markdown_path=str(fixtures_root / "tender_small.md"),
            qmd_collection="test-tender-collection",
        )
        session.add(tender_doc)
        session.commit()
        session.refresh(tender_doc)

        final_ids: list[str] = []
        for payload in checkpoints_payload:
            cf = CheckpointFinal(
                payload_json=json.dumps(payload, ensure_ascii=False),
                approved_by="tester",
            )
            session.add(cf)
            session.commit()
            session.refresh(cf)
            final_ids.append(cf.id)

        audit_run = AuditRun(
            project_id=project.id,
            tender_doc_id=tender_doc.id,
            checkpoint_final_ids=json.dumps(final_ids, ensure_ascii=False),
            total_count=len(final_ids),
        )
        session.add(audit_run)
        session.commit()
        session.refresh(audit_run)

        for cp_id in final_ids:
            session.add(AuditPointRun(audit_run_id=audit_run.id, checkpoint_final_id=cp_id))
        session.commit()

        result = asyncio.run(
            run_audit(
                audit_run.id,
                session,
                workspace_manager=TempWorkspaceManager(tmp_path / "workspaces"),
                trajectory_store=FakeTrajectoryStore(),
                replay_dir=fixtures_root / "mock_agent_trajectories" / "audit_case_01",
                project_root=repo_root,
                template_path=fixtures_root / "workpaper_template.docx",
            )
        )

        actual = capture(session, result.id)

    if not GOLDEN_PATH.exists():
        write_golden(actual, GOLDEN_PATH)
        pytest.skip(f"golden 首次生成于 {GOLDEN_PATH}，下次跑开始对比")

    expected = load_golden(GOLDEN_PATH)
    actual_dict = asdict(actual)
    expected_dict = asdict(expected)

    assert actual_dict == expected_dict, (
        f"golden 不匹配！\n"
        f"实际: {json.dumps(actual_dict, ensure_ascii=False, indent=2)[:500]}...\n"
        f"期望: {json.dumps(expected_dict, ensure_ascii=False, indent=2)[:500]}..."
    )
