"""Harness manifest 加载器，用于读取评测夹具配置。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProjectFixture:
    """单个项目夹具，包含招标文件与补充材料路径。"""

    name: str
    tender_doc: Path
    supplementary_docs: list[Path]


@dataclass(frozen=True)
class RuleFixture:
    """规则夹具，包含规则名称与文件路径。"""

    name: str
    path: Path


@dataclass(frozen=True)
class CheckpointFixture:
    """检查点夹具，包含检查点名称与文件路径。"""

    name: str
    path: Path


@dataclass(frozen=True)
class HumanWorkpaperFixture:
    """人类工作底稿参考文件。"""

    project_name: str
    path: Path


@dataclass(frozen=True)
class GroundTruthFixture:
    """Ground truth 参考数据配置。"""

    gold_checkpoints: Path | None
    human_workpapers: list[HumanWorkpaperFixture]


@dataclass(frozen=True)
class HarnessManifest:
    """Harness manifest 的结构化表示。"""

    projects: list[ProjectFixture]
    rules: list[RuleFixture]
    checkpoints: list[CheckpointFixture]
    ground_truth: GroundTruthFixture | None = None


def _resolve_path(path: str, project_root: Path | None) -> Path:
    """按项目根目录解析路径。

    如果提供 project_root，则相对路径会拼接到该根目录下；未提供时返回原始
    Path 表示。
    """
    path_obj = Path(path)
    if project_root is None:
        return path_obj
    return project_root / path_obj


def load_manifest(
    manifest_path: str | Path,
    project_root: str | Path | None = None,
) -> HarnessManifest:
    """加载 Harness manifest YAML 文件并返回结构化配置。

    参数:
        manifest_path: manifest YAML 文件路径。
        project_root: 用于解析 manifest 内相对路径的项目根目录。

    返回:
        解析后的 HarnessManifest 实例。

    异常:
        FileNotFoundError: 当 manifest_path 不存在时抛出。
        ValueError: 当 YAML 内容无效时抛出，并包装原始 yaml.YAMLError。
    """
    manifest_file = Path(manifest_path)
    if not manifest_file.exists():
        raise FileNotFoundError(manifest_file)

    root_path = Path(project_root) if project_root is not None else None

    try:
        raw_data = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid manifest YAML: {manifest_file}") from exc

    data: dict[str, Any] = raw_data or {}
    projects = [
        ProjectFixture(
            name=item["name"],
            tender_doc=_resolve_path(item["tender_doc"], root_path),
            supplementary_docs=[
                _resolve_path(path, root_path) for path in item.get("supplementary_docs", [])
            ],
        )
        for item in data.get("projects", [])
    ]
    rules = [
        RuleFixture(name=item["name"], path=_resolve_path(item["path"], root_path))
        for item in data.get("rules", [])
    ]
    checkpoints = [
        CheckpointFixture(name=item["name"], path=_resolve_path(item["path"], root_path))
        for item in data.get("checkpoints", [])
    ]

    gt_data = data.get("ground_truth")
    ground_truth = None
    if gt_data:
        gt_cp_path = gt_data.get("gold_checkpoints")
        human_wps = [
            HumanWorkpaperFixture(
                project_name=item["project_name"],
                path=_resolve_path(item["path"], root_path),
            )
            for item in gt_data.get("human_workpapers", [])
        ]
        ground_truth = GroundTruthFixture(
            gold_checkpoints=_resolve_path(gt_cp_path, root_path) if gt_cp_path else None,
            human_workpapers=human_wps,
        )

    manifest = HarnessManifest(
        projects=projects, rules=rules, checkpoints=checkpoints, ground_truth=ground_truth
    )
    logger.debug(
        "Loaded harness manifest from %s: %d projects, %d rules, %d checkpoints",
        manifest_file,
        len(projects),
        len(rules),
        len(checkpoints),
    )
    return manifest
