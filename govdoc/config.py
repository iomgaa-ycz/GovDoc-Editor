"""GovDoc 配置加载。

设计基线：`docs/design.md` §13-14。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GovDocEnvOverrides(BaseSettings):
    """只负责读取少量环境覆盖项，保持 YAML 为单一配置文件。"""

    model_config = SettingsConfigDict(env_prefix="GOVDOC_", extra="ignore")

    config_path: str | None = None


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage_root: str = "./data/storage"
    database_url: str = "sqlite:///./data/app.sqlite"
    ocr_base_url: str | None = None


class ModelServiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    base_url: str | None = None
    api_key: str | None = None
    fallback_model: str | None = None
    provider: str | None = None


class QmdConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    db_path: str


class WorkspaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspaces_root: str
    archives_root: str
    cleanup_days: int = 30


class EvolutionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    proposer_model: str | None = None
    frontier_size: int = 5
    eval_dataset_path: str | None = None


class HarnessConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    db_path: str = "./results/harness.db"
    judge_model: str = "glm-5.1"
    judge_base_url: str = "http://110.42.53.85:11098/v1"


class AuditConfig(BaseModel):
    """审核管道配置。"""

    model_config = ConfigDict(extra="forbid")

    point_timeout_s: int = 900


class GovDocConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app: AppConfig
    model: ModelServiceConfig
    qmd: QmdConfig
    workspace: WorkspaceConfig
    evolution: EvolutionConfig = Field(default_factory=EvolutionConfig)
    harness: HarnessConfig = Field(default_factory=HarnessConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        return (self.project_root / path).resolve()

    @property
    def storage_root(self) -> Path:
        return self.resolve_path(self.app.storage_root)

    @property
    def qmd_db_path(self) -> Path:
        return self.resolve_path(self.qmd.db_path)

    @property
    def harness_db_path(self) -> Path:
        return self.resolve_path(self.harness.db_path)

    @property
    def app_db_path(self) -> Path:
        raw = self.app.database_url
        prefix = "sqlite:///"
        if not raw.startswith(prefix):
            raise ValueError("当前仅支持 sqlite:/// 形式的 database_url。")
        return self.resolve_path(raw[len(prefix) :])

    def ensure_directories(self) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.qmd_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.app_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.resolve_path(self.workspace.workspaces_root).mkdir(parents=True, exist_ok=True)
        self.resolve_path(self.workspace.archives_root).mkdir(parents=True, exist_ok=True)
        if self.evolution.eval_dataset_path:
            self.resolve_path(self.evolution.eval_dataset_path).parent.mkdir(
                parents=True,
                exist_ok=True,
            )


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


def load_config(path: str | Path | None = None) -> GovDocConfig:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    env = GovDocEnvOverrides()
    config_path = Path(path or env.config_path or "govdoc.yaml").expanduser()
    if not config_path.is_absolute():
        config_path = (Path(__file__).resolve().parents[1] / config_path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"未找到 GovDoc 配置文件: {config_path}")

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return GovDocConfig.model_validate(_expand_env(payload))
