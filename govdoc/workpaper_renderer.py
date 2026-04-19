"""工作底稿 docx 渲染辅助。"""

from __future__ import annotations

import os
from pathlib import Path

from scrivai import DocxRenderer

from govdoc.schemas import Workpaper
from govdoc.storage.files import ensure_workpaper_dir


def resolve_workpaper_template(template_path: str | Path | None = None) -> Path:
    if template_path is not None:
        path = Path(template_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"工作底稿模板不存在: {path}")
        return path

    fixture_root = os.environ.get("GOVDOC_FIXTURES")
    if fixture_root:
        fixture_path = Path(fixture_root).expanduser().resolve() / "workpaper_template.docx"
        if fixture_path.is_file():
            return fixture_path

    default_path = Path(__file__).resolve().parent / "templates" / "workpaper.docx"
    if default_path.is_file():
        return default_path

    raise FileNotFoundError(
        "未找到工作底稿模板。请提供 template_path，或设置 GOVDOC_FIXTURES 指向含 "
        "workpaper_template.docx 的目录。"
    )


def render_workpaper_docx(
    workpaper: Workpaper,
    audit_run_id: str,
    *,
    template_path: str | Path | None = None,
    version: int = 1,
) -> Path:
    output_dir = ensure_workpaper_dir(audit_run_id)
    output_path = output_dir / f"workpaper-draft-v{version}.docx"
    renderer = DocxRenderer(resolve_workpaper_template(template_path))
    return renderer.render(workpaper.model_dump(mode="json"), output_path)
