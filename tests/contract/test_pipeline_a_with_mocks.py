import asyncio
import json
from pathlib import Path

from scrivai import FakeTrajectoryStore, TempWorkspaceManager
from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.db.models import CheckpointDraft, CheckpointFinal, ExtractRun, RuleSource
from govdoc.pipelines.extract_rules import run_extract


def test_pipeline_a_with_mock_pes_replay(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    fixtures_root = repo_root / "tests" / "fixtures"
    monkeypatch.setenv("GOVDOC_FIXTURES", str(fixtures_root))

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        rule_source = RuleSource(
            title="违法违规情形节选",
            source_path=str(fixtures_root / "guide_excerpt.md"),
            rule_library_entry_id="rules-entry-001",
        )
        session.add(rule_source)
        session.commit()
        session.refresh(rule_source)

        extract_run = ExtractRun(rule_source_id=rule_source.id, status="pending")
        session.add(extract_run)
        session.commit()
        session.refresh(extract_run)

        extract_run = asyncio.run(
            run_extract(
                rule_source.id,
                session,
                extract_run_id=extract_run.id,
                workspace_manager=TempWorkspaceManager(tmp_path / "workspaces"),
                trajectory_store=FakeTrajectoryStore(),
                replay_dir=fixtures_root / "mock_agent_trajectories" / "extract_case_01",
                project_root=repo_root,
            )
        )

        drafts = session.exec(
            select(CheckpointDraft).where(CheckpointDraft.extract_run_id == extract_run.id)
        ).all()
        finals = session.exec(select(CheckpointFinal)).all()
        expected = json.loads((fixtures_root / "checkpoints_golden.json").read_text(encoding="utf-8"))

    assert extract_run.status == "draft_ready"
    assert extract_run.workspace_archive_path is not None
    assert len(drafts) == len(expected["checkpoints"])
    assert len(finals) == len(expected["checkpoints"])
    assert all(item.status == "promoted" for item in drafts)
    assert sorted(json.loads(item.payload_json)["id"] for item in drafts) == sorted(
        checkpoint["id"] for checkpoint in expected["checkpoints"]
    )
