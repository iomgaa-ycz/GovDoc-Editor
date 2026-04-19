"""GovDoc 文件存储与 DocumentStore。"""

from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path
from typing import Any

from govdoc.config import load_config


def get_storage_root() -> Path:
    root = load_config().storage_root
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_rule_source_dir(rule_source_id: str) -> Path:
    path = get_storage_root() / "rules" / rule_source_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_project_dir(project_id: str) -> Path:
    path = get_storage_root() / "projects" / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_workpaper_dir(audit_run_id: str) -> Path:
    path = get_storage_root() / "workpapers" / audit_run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


class DocumentStore:
    """文档存储：统一管理原始文件与 prepared markdown。

    - 上传阶段通过 save_raw 保存原始文件
    - get_or_convert 负责转换为 markdown（仅转一次，后续复用）
    - prepared markdown 存储在稳定的 prepared/ 目录下
    """

    def __init__(self, storage_root: Path) -> None:
        self._root = storage_root
        self._prepared_dir = storage_root / "prepared"
        self._raw_dir = storage_root / "raw"
        self._prepared_dir.mkdir(parents=True, exist_ok=True)
        self._raw_dir.mkdir(parents=True, exist_ok=True)

    @property
    def storage_root(self) -> Path:
        return self._root

    def _sha256(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _prepared_path(self, sha: str) -> Path:
        return self._prepared_dir / f"{sha}.md"

    def _manifest_path(self, raw_path: Path) -> Path:
        return self._raw_dir / f"{raw_path.name}.manifest.json"

    def save_raw(self, filename: str, content: bytes, subdir: str = "") -> Path:
        """保存原始文件到 raw/ 目录，返回存储路径。"""
        target_dir = self._raw_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        target.write_bytes(content)
        return target

    def get_or_convert(
        self,
        raw_path: str | Path,
        *,
        warnings_stack: list[str] | None = None,
    ) -> Path:
        """将原始文件转换为 markdown。如果已是 .md 则直接返回。

        转换结果按 SHA256 缓存到 prepared/，同一文件不重复转换。
        """
        raw = Path(raw_path).expanduser().resolve()
        if not raw.exists():
            raise FileNotFoundError(f"原始文件不存在: {raw}")

        suffix = raw.suffix.lower()
        if suffix == ".md":
            return raw

        content = raw.read_bytes()
        sha = self._sha256(content)
        prepared = self._prepared_path(sha)
        if prepared.exists():
            return prepared

        if suffix in (".docx", ".doc"):
            prepared = self._convert_docx(raw, prepared, warnings_stack)
        elif suffix == ".pdf":
            prepared = self._convert_pdf(raw, prepared, warnings_stack)
        else:
            msg = f"不支持的文档格式: {suffix}，尝试作为纯文本处理"
            if warnings_stack is not None:
                warnings_stack.append(msg)
            warnings.warn(msg)
            text = content.decode("utf-8", errors="replace")
            prepared.write_text(text, encoding="utf-8")

        self._write_manifest(raw, prepared, sha)
        return prepared

    def build_prepared_manifest(self) -> list[dict[str, Any]]:
        """列出所有已转换的 prepared 文件及其 manifest 信息。"""
        manifests: list[dict[str, Any]] = []
        for mf in self._raw_dir.rglob("*.manifest.json"):
            try:
                manifests.append(json.loads(mf.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return manifests

    def _convert_docx(
        self, raw: Path, target: Path, warnings_stack: list[str] | None
    ) -> Path:
        try:
            from scrivai import docx_to_markdown

            md = docx_to_markdown(raw)
            target.write_text(md, encoding="utf-8")
            return target
        except Exception as exc:
            msg = f"docx_to_markdown 失败 ({exc})，使用 fallback 文本提取"
            if warnings_stack is not None:
                warnings_stack.append(msg)
            warnings.warn(msg)
            return self._fallback_text_extract(raw, target)

    def _convert_pdf(
        self, raw: Path, target: Path, warnings_stack: list[str] | None
    ) -> Path:
        try:
            from scrivai import pdf_to_markdown

            md = pdf_to_markdown(raw)
            if not md or not md.strip():
                raise RuntimeError("pdf_to_markdown 返回空内容")
            target.write_text(md, encoding="utf-8")
            return target
        except Exception as exc:
            msg = f"pdf_to_markdown 失败 ({exc})，无法转换该 PDF"
            if warnings_stack is not None:
                warnings_stack.append(msg)
            raise RuntimeError(msg) from exc

    def _fallback_text_extract(self, raw: Path, target: Path) -> Path:
        """最简 fallback：把文件当二进制读，提取可读文本。"""
        try:
            text = raw.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = raw.read_text(encoding="latin-1")
        target.write_text(text, encoding="utf-8")
        return target

    def _write_manifest(self, raw: Path, prepared: Path, sha: str) -> None:
        manifest = {
            "raw_filename": raw.name,
            "raw_path": str(raw),
            "sha256": sha,
            "prepared_path": str(prepared),
        }
        mf = self._manifest_path(raw)
        mf.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
