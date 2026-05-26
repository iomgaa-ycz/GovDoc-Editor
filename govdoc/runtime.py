"""GovDoc 运行时装配。

设计基线：`docs/design.md` §13。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from scrivai import (
    ModelConfig,
    TrajectoryStore,
    build_libraries,
    build_qmd_client_from_config,
    build_workspace_manager,
    load_pes_config,
)
from scrivai.pes.prompts.manager import PromptManager as _PromptManager

from govdoc.config import GovDocConfig, load_config
from govdoc.pipelines.pes_overrides import GovDocAuditorPES, GovDocExtractorPES
from govdoc.storage.files import DocumentStore


@lru_cache
def get_config(config_path: str | Path | None = None) -> GovDocConfig:
    return load_config(config_path)


@lru_cache
def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@lru_cache
def get_document_store() -> DocumentStore:
    cfg = get_config()
    return DocumentStore(cfg.storage_root, ocr_backend=cfg.app.ocr_backend)


@lru_cache
def get_qmd() -> Any:
    return build_qmd_client_from_config(get_config().qmd_db_path)


@lru_cache
def get_libraries() -> Any:
    return build_libraries(get_qmd())


@lru_cache
def get_workspace_manager() -> Any:
    cfg = get_config()
    return build_workspace_manager(
        workspaces_root=cfg.resolve_path(cfg.workspace.workspaces_root),
        archives_root=cfg.resolve_path(cfg.workspace.archives_root),
    )


@lru_cache
def get_trajectory_store() -> TrajectoryStore:
    return TrajectoryStore(get_config().app_db_path.with_name("trajectories.sqlite"))


@lru_cache
def get_harness_log() -> Any:
    """获取 HarnessLog 单例（惰性初始化）。"""
    import uuid

    from govdoc.harness import HarnessLog

    cfg = get_config()
    return HarnessLog(
        db_path=str(cfg.harness_db_path),
        run_id=uuid.uuid4().hex,
    )


def configure_logging() -> None:
    """配置 Python logging，将日志同时写入 harness.db。"""
    import logging

    from govdoc.harness.handler import SqliteHandler

    cfg = get_config()
    harness_log = get_harness_log()
    handler = SqliteHandler(
        db_path=str(cfg.harness_db_path),
        run_id=harness_log._run_id,
    )
    root = logging.getLogger()
    root.addHandler(handler)
    if root.level == logging.NOTSET:
        root.setLevel(logging.INFO)


@lru_cache
def get_gov_extractor_config():
    return load_pes_config(get_project_root() / "agents" / "gov-extractor.yaml")


@lru_cache
def get_gov_auditor_config():
    return load_pes_config(get_project_root() / "agents" / "gov-auditor.yaml")


@lru_cache
def get_prompt_manager() -> _PromptManager:
    """构造最小化 PromptManager，解决 scrivai 0.1.7 BasePES 初始化时
    _create_default_prompt_manager 找不到 prompt_spec.yaml 的问题。"""
    prompts_dir = get_project_root() / "govdoc" / "prompts"
    return _PromptManager(
        template_dir=prompts_dir / "templates",
        fragments_dir=prompts_dir / "fragments",
        spec_path=prompts_dir / "prompt_spec.yaml",
    )


def get_model_config() -> ModelConfig:
    cfg = get_config()
    return ModelConfig(
        model=cfg.model.model,
        base_url=cfg.model.base_url,
        api_key=cfg.model.api_key,
        provider=cfg.model.provider,
        fallback_model=cfg.model.fallback_model,
    )


def _build_hooks() -> Any:
    from scrivai.pes.hooks import HookManager
    from scrivai.trajectory.hooks import TrajectoryRecorderHook

    mgr = HookManager()
    mgr.register(TrajectoryRecorderHook(get_trajectory_store()))
    return mgr


def build_gov_extractor_pes(
    *,
    workspace: Any,
    runtime_context: dict[str, Any],
    hooks: Any = None,
    extra_hooks: list[Any] | None = None,
) -> GovDocExtractorPES:
    mgr = hooks or _build_hooks()
    if extra_hooks:
        for h in extra_hooks:
            mgr.register(h)
    return GovDocExtractorPES(
        config=get_gov_extractor_config(),
        model=get_model_config(),
        workspace=workspace,
        hooks=mgr,
        trajectory_store=get_trajectory_store(),
        runtime_context=runtime_context,
        prompt_manager=get_prompt_manager(),
    )


def build_gov_auditor_pes(
    *,
    workspace: Any,
    runtime_context: dict[str, Any],
    hooks: Any = None,
    extra_hooks: list[Any] | None = None,
) -> GovDocAuditorPES:
    mgr = hooks or _build_hooks()
    if extra_hooks:
        for h in extra_hooks:
            mgr.register(h)
    return GovDocAuditorPES(
        config=get_gov_auditor_config(),
        model=get_model_config(),
        workspace=workspace,
        hooks=mgr,
        trajectory_store=get_trajectory_store(),
        runtime_context=runtime_context,
        prompt_manager=get_prompt_manager(),
    )


def collect_diagnostics() -> dict[str, Any]:
    """收集 runtime 诊断信息。"""
    cfg = get_config()
    diag: dict[str, Any] = {
        "config_loaded": True,
        "project_root": str(get_project_root()),
        "storage_root": str(cfg.storage_root),
    }
    try:
        diag["qmd_db_exists"] = cfg.qmd_db_path.exists()
    except Exception as exc:
        diag["qmd_db_exists"] = f"error: {exc}"
    try:
        diag["app_db_exists"] = cfg.app_db_path.exists()
    except Exception as exc:
        diag["app_db_exists"] = f"error: {exc}"
    return diag
