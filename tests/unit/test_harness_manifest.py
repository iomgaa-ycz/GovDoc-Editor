"""Harness manifest 加载器单元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from govdoc.harness.manifest import HarnessManifest, load_manifest


VALID_MANIFEST = """
projects:
  - name: "项目一"
    tender_doc: "docs/tender-one.docx"
    supplementary_docs:
      - "docs/appendix-one.pdf"
  - name: "项目二"
    tender_doc: "docs/tender-two.docx"
    supplementary_docs: []
rules:
  - name: "规则一"
    path: "rules/rule-one.doc"
checkpoints:
  - name: "检查点一"
    path: "checkpoints/checkpoint-one.xls"
"""


def test_load_valid_manifest(tmp_path: Path) -> None:
    """应能加载合法 manifest 并保留核心字段。"""
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(VALID_MANIFEST, encoding="utf-8")

    manifest = load_manifest(manifest_path)

    assert isinstance(manifest, HarnessManifest)
    assert len(manifest.projects) == 2
    assert len(manifest.rules) == 1
    assert len(manifest.checkpoints) == 1
    assert manifest.projects[0].name == "项目一"
    assert manifest.projects[1].name == "项目二"
    assert manifest.rules[0].name == "规则一"
    assert manifest.checkpoints[0].name == "检查点一"


def test_load_resolves_relative_paths(tmp_path: Path) -> None:
    """提供 project_root 时应将相对路径解析到该目录下。"""
    manifest_path = tmp_path / "manifest.yaml"
    project_root = tmp_path / "project-root"
    manifest_path.write_text(VALID_MANIFEST, encoding="utf-8")

    manifest = load_manifest(manifest_path, project_root=project_root)

    paths = [
        manifest.projects[0].tender_doc,
        manifest.projects[0].supplementary_docs[0],
        manifest.projects[1].tender_doc,
        manifest.rules[0].path,
        manifest.checkpoints[0].path,
    ]
    for path in paths:
        assert path.is_absolute()
        assert path.is_relative_to(project_root)


def test_load_missing_file_raises(tmp_path: Path) -> None:
    """manifest 文件不存在时应抛出 FileNotFoundError。"""
    with pytest.raises(FileNotFoundError):
        load_manifest(tmp_path / "missing.yaml")


def test_load_invalid_yaml_raises(tmp_path: Path) -> None:
    """YAML 格式错误时应抛出 ValueError 或 yaml.YAMLError。"""
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text("projects: [unclosed", encoding="utf-8")

    with pytest.raises((ValueError, yaml.YAMLError)):
        load_manifest(manifest_path)
