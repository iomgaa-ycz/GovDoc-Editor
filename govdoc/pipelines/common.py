"""Pipeline 共用辅助。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from govdoc.pipelines.output_utils import relaxed_json_loads


def attach_workspace_output(result: Any, working_dir: Path) -> None:
    output_path = working_dir / "output.json"
    if result.final_output_path is None and output_path.exists():
        result.final_output_path = output_path
    if result.final_output is None and output_path.exists():
        result.final_output = relaxed_json_loads(output_path.read_text(encoding="utf-8"))


def load_result_payload(
    final_output_path: Path | None,
    final_output: str | dict[str, Any] | None,
) -> dict[str, Any]:
    if final_output_path is not None and final_output_path.exists():
        return relaxed_json_loads(final_output_path.read_text(encoding="utf-8"))
    if isinstance(final_output, dict):
        return final_output
    if isinstance(final_output, str) and final_output.strip():
        return relaxed_json_loads(final_output)
    raise ValueError("缺少可解析的 PES 输出。design 要求优先读取 final_output_path。")


def dump_phase_usage(phase_results: dict[str, Any]) -> str:
    return json.dumps(
        {phase: result.usage for phase, result in phase_results.items()},
        ensure_ascii=False,
    )
