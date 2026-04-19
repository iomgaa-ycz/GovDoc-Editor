"""Workpaper CLI helpers.

当前初始化阶段只保留后续扩展入口，避免业务 CLI 分散到 pipeline 中。
"""

from __future__ import annotations

from govdoc.schemas import Workpaper


def workpaper_context_payload(workpaper: Workpaper) -> dict[str, object]:
    return workpaper.model_dump(mode="json")

