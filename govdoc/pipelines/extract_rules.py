"""管道 A：法规/指引 -> 审核点。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scrivai import MockPES, WorkspaceSpec
from sqlmodel import Session

from govdoc.db.models import CheckpointDraft, CheckpointFinal, ExtractRun, RuleSource
from govdoc.pipelines.common import attach_workspace_output, dump_phase_usage, load_result_payload
from govdoc.runtime import (
    build_gov_extractor_pes,
    get_config,
    get_gov_extractor_config,
    get_project_root,
    get_trajectory_store,
    get_workspace_manager,
)
from govdoc.schemas import CheckpointListOutput
from govdoc.testing_support import load_mock_replay, seed_working_tree


async def run_extract(
    rule_source_id: str,
    session: Session,
    *,
    extract_run_id: str | None = None,
    workspace_manager: Any | None = None,
    trajectory_store: Any | None = None,
    replay_dir: str | Path | None = None,
    project_root: str | Path | None = None,
) -> ExtractRun:
    rule_source = session.get(RuleSource, rule_source_id)
    if rule_source is None:
        raise ValueError(f"未找到 RuleSource: {rule_source_id}")

    if extract_run_id is None:
        extract_run = ExtractRun(rule_source_id=rule_source_id, status="running")
        session.add(extract_run)
        session.commit()
        session.refresh(extract_run)
    else:
        extract_run = session.get(ExtractRun, extract_run_id)
        if extract_run is None:
            raise ValueError(f"未找到 ExtractRun: {extract_run_id}")
        if extract_run.rule_source_id != rule_source_id:
            raise ValueError(
                f"ExtractRun {extract_run_id} 不属于 RuleSource {rule_source_id}"
            )
        extract_run.status = "running"
        extract_run.error = None
        extract_run.workspace_archive_path = None
        extract_run.workspace_failed_path = None
        session.add(extract_run)
        session.commit()
        session.refresh(extract_run)

    manager = workspace_manager or get_workspace_manager()
    store = trajectory_store or get_trajectory_store()
    repo_root = Path(project_root).expanduser().resolve() if project_root else get_project_root()
    workspace = None
    result = None

    try:
        workspace = manager.create(
            WorkspaceSpec(
                run_id=extract_run.id,
                project_root=repo_root,
                data_inputs={"guide.md": Path(rule_source.source_path).expanduser().resolve()},
                extra_env={
                    "GOVDOC_RULE_SOURCE_ID": rule_source.id,
                    "GOVDOC_RULE_LIBRARY_ENTRY_ID": rule_source.rule_library_entry_id,
                    "GOVDOC_DB_PATH": str(get_config().qmd_db_path),
                },
            )
        )

        runtime_context = {"output_schema": CheckpointListOutput}
        if replay_dir is not None:
            replay = load_mock_replay(replay_dir)
            seed_working_tree(replay.working_seed_dir, workspace.working_dir)
            pes = MockPES(
                config=get_gov_extractor_config(),
                workspace=workspace,
                trajectory_store=store,
                runtime_context=runtime_context,
                phase_outcomes=replay.phase_outcomes,
            )
        else:
            pes = build_gov_extractor_pes(workspace=workspace, runtime_context=runtime_context)

        result = await pes.run(task_prompt="抽取 data/guide.md 中的所有审核点。")
        attach_workspace_output(result, workspace.working_dir)
        extract_run.total_usage_json = dump_phase_usage(result.phase_results)

        if result.status == "completed":
            payload = CheckpointListOutput.model_validate(
                load_result_payload(result.final_output_path, result.final_output)
            )
            for checkpoint in payload.checkpoints:
                draft = CheckpointDraft(
                    rule_source_id=rule_source.id,
                    payload_json=checkpoint.model_dump_json(),
                    extract_run_id=extract_run.id,
                    status="promoted",
                )
                session.add(draft)
                session.add(
                    CheckpointFinal(
                        payload_json=checkpoint.model_dump_json(),
                        approved_by="system:auto-promote",
                    )
                )
            archive_path = manager.archive(workspace, success=True)
            extract_run.workspace_archive_path = str(archive_path)
            extract_run.status = "draft_ready"
        else:
            failed_path = manager.archive(workspace, success=False)
            extract_run.workspace_failed_path = str(failed_path)
            extract_run.status = "failed"
            extract_run.error = result.error

        session.add(extract_run)
        session.commit()
        session.refresh(extract_run)
        return extract_run
    except Exception as exc:
        if workspace is not None and workspace.root_dir.exists() and extract_run.workspace_failed_path is None:
            failed_path = manager.archive(workspace, success=False)
            extract_run.workspace_failed_path = str(failed_path)
        extract_run.status = "failed"
        extract_run.error = str(exc)
        if result is not None:
            extract_run.total_usage_json = dump_phase_usage(result.phase_results)
        session.add(extract_run)
        session.commit()
        raise
