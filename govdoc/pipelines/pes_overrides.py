"""GovDoc PES override 层——解决 prompt duplication + 接 validator / recovery hook。

设计基线：docs/design.md §7/§10，docs/v2-lessons-design-amendment.md §1/§6/§7。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from scrivai import AuditorPES, ExtractorPES, PhaseConfig, PhaseResult

from govdoc.pipelines.output_utils import relaxed_json_loads


def _load_previous_phase_output(working_dir: Path, phase: str) -> Any:
    """GovDoc 版前序 phase 读取：统一走 relaxed_json_loads。"""
    if phase == "execute":
        plan_json = working_dir / "plan.json"
        if plan_json.exists():
            return relaxed_json_loads(plan_json.read_text(encoding="utf-8"))
    elif phase == "summarize":
        findings_dir = working_dir / "findings"
        if findings_dir.is_dir():
            return {
                fp.name: relaxed_json_loads(fp.read_text(encoding="utf-8"))
                for fp in sorted(findings_dir.glob("*.json"))
            }
    return None


class _RelaxedPreviousPhaseOutputMixin:
    """把前序 phase 读取改成 GovDoc 的宽松 JSON 解析。"""

    def _read_previous_phase_output(self, phase: str) -> Any:
        return _load_previous_phase_output(self.workspace.working_dir, phase)


class GovDocExtractorPES(_RelaxedPreviousPhaseOutputMixin, ExtractorPES):
    """GovDoc 侧 ExtractorPES 覆盖：修复 prompt duplication，接 output validator。"""

    async def build_phase_prompt(
        self,
        phase: str,
        phase_cfg: PhaseConfig,
        context: dict[str, Any],
        task_prompt: str,
    ) -> str:
        """Override: 只拼 task_prompt + context，不重复拼 prompt_text / additional_system_prompt。

        原因：Scrivai _call_sdk_query 已把 prompt_text + additional_system_prompt 作为 system_prompt，
        如果 build_phase_prompt 再拼一次，LLM 会看到两份相同内容。
        """
        parts: list[str] = [task_prompt]
        if context:
            parts.append(json.dumps(context, ensure_ascii=False, default=str))
        return "\n\n".join(parts)


class GovDocAuditorPES(_RelaxedPreviousPhaseOutputMixin, AuditorPES):
    """GovDoc 侧 AuditorPES 覆盖：修复 prompt duplication，接 output validator + recovery。"""

    async def build_phase_prompt(
        self,
        phase: str,
        phase_cfg: PhaseConfig,
        context: dict[str, Any],
        task_prompt: str,
    ) -> str:
        """Override: 同 GovDocExtractorPES，避免 prompt duplication。"""
        parts: list[str] = [task_prompt]
        if context:
            parts.append(json.dumps(context, ensure_ascii=False, default=str))
        return "\n\n".join(parts)

    async def postprocess_phase_result(
        self,
        phase: str,
        result: PhaseResult,
        run: Any,
    ) -> None:
        """summarize 阶段按 GovDoc 的 GovFinding 结构做校验。"""
        if phase != "summarize":
            return

        schema = self.runtime_context.get("output_schema")
        if schema is None:
            raise ValueError(
                "AuditorPES 需要 runtime_context['output_schema'](pydantic BaseModel 子类)"
            )
        if not (isinstance(schema, type) and issubclass(schema, BaseModel)):
            raise ValueError(
                "runtime_context['output_schema'] 必须是 BaseModel 子类,"
                f"得到 {type(schema).__name__}"
            )

        output_path = self.workspace.working_dir / "output.json"
        if not output_path.exists():
            raise FileNotFoundError(f"AuditorPES summarize 阶段 output.json 未生成: {output_path}")

        try:
            data = relaxed_json_loads(output_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ValueError(f"output.json 不是合法 JSON: {exc}") from exc

        try:
            validated = schema.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"output.json 不符 output_schema: {exc}") from exc

        verdict_levels: list[str] = list(
            self.runtime_context.get("verdict_levels") or ("合规", "不合规", "存疑")
        )
        evidence_required: bool = bool(self.runtime_context.get("evidence_required", True))
        payload = validated.model_dump(mode="json")

        _validate_govdoc_auditor_payload(
            payload,
            verdict_levels=verdict_levels,
            evidence_required=evidence_required,
        )

        run.final_output = payload
        run.final_output_path = output_path


def _validate_govdoc_auditor_payload(
    payload: dict[str, Any],
    *,
    verdict_levels: list[str],
    evidence_required: bool,
) -> None:
    """按 GovDoc 的 GovFinding 结构校验 summarize 输出。"""
    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("output.json.findings 必须是列表")

    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ValueError(f"findings[{idx}] 必须是对象")

        verdict_obj = finding.get("verdict")
        verdict_value = verdict_obj.get("verdict") if isinstance(verdict_obj, dict) else verdict_obj
        if verdict_value not in verdict_levels:
            raise ValueError(
                f"findings[{idx}].verdict={verdict_obj!r} 不在 verdict_levels={verdict_levels}"
            )

        if not evidence_required:
            continue

        evidence_quotes = (
            verdict_obj.get("evidence_quotes") if isinstance(verdict_obj, dict) else []
        )
        evidence_refs = finding.get("evidence_refs") or []
        has_evidence_quotes = isinstance(evidence_quotes, list) and any(
            isinstance(item, str) and item.strip() for item in evidence_quotes
        )
        has_evidence_refs = isinstance(evidence_refs, list) and len(evidence_refs) > 0
        if not (has_evidence_quotes or has_evidence_refs):
            raise ValueError(
                f"findings[{idx}] 缺少 evidence_quotes/evidence_refs(evidence_required=True)"
            )


def _try_load_output(path: Path) -> dict[str, Any] | None:
    """尝试从指定路径加载合法的 output JSON。"""
    if not path.exists():
        return None
    try:
        data = relaxed_json_loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "findings" in data:
            return data
    except Exception:
        pass
    return None


def _try_load_findings_dir(findings_dir: Path) -> dict[str, Any] | None:
    """尝试从 findings/ 目录逐个加载 JSON 并拼凑结果。"""
    if not findings_dir.exists() or not any(findings_dir.glob("*.json")):
        return None
    findings: list[dict[str, Any]] = []
    for fp in sorted(findings_dir.glob("*.json")):
        try:
            findings.append(relaxed_json_loads(fp.read_text(encoding="utf-8")))
        except Exception:
            continue
    if findings:
        return {"findings": findings, "summary": ""}
    return None


def try_recover_audit_output(
    result: PhaseResult,
    working_dir: Path,
) -> dict[str, Any] | None:
    """max-turn recovery：如果 workspace 中已有合法产物，接受结果。

    依次检查：
    1. working/output.json（标准路径）
    2. workspace_root/output/output.json（LLM 常见误写路径）
    3. working/findings/*.json 逐个加载拼凑

    返回 None 表示无法恢复。
    """
    # 1. 标准 working/output.json
    recovered = _try_load_output(working_dir / "output.json")
    if recovered is not None:
        return recovered

    # 2. LLM 误写到 output/output.json（working_dir 是 working/，上级是 workspace root）
    workspace_root = working_dir.parent
    recovered = _try_load_output(workspace_root / "output" / "output.json")
    if recovered is not None:
        return recovered

    # 3. 从 findings/ 目录拼凑
    return _try_load_findings_dir(working_dir / "findings")
