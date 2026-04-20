"""GovDoc PES override 层——phase prompt 管理 + output validator + recovery。

Scrivai 0.1.7 迁移：additional_system_prompt 已删除，phase 级指令
通过 build_phase_prompt 覆写注入。

设计基线：docs/design.md §7/§10，docs/v2-lessons-design-amendment.md §1/§6/§7。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from scrivai import AuditorPES, ExtractorPES, MockPES, PhaseConfig, PhaseResult

from govdoc.pipelines.output_utils import relaxed_json_loads

# ── Phase Prompt 常量（从 agents/*.yaml 的 additional_system_prompt 迁入） ──

_EXTRACTOR_PHASE_PROMPTS: dict[str, str] = {
    "plan": (
        "你是政府采购法律合规专家。任务：从法规指引中抽取审核点。\n\n"
        "操作步骤（严格按序，不跳步、不加步）：\n"
        "1. Read ../data/guide.md\n"
        "2. 分析法规结构，识别所有可抽取的审核点\n"
        "3. Write plan.md\n"
        "4. Write plan.json\n"
        "5. 结束\n\n"
        "plan.json 格式（必须严格遵循）：\n"
        "{\n"
        '  "items_to_extract": [\n'
        "    {\n"
        '      "id": "cp_01",\n'
        '      "title": "审核点标题",\n'
        '      "category": "意向性招标|围标串标|不合理条件限制或排斥供应商|其他违法违规",\n'
        '      "severity": "critical|major|minor",\n'
        '      "description": "描述"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "关键规则：\n"
        '- 只抽取"大类违法违规问题"作为审核点，不要把每条具体表现形式单独列为审核点\n'
        "- 合并同一问题下的所有表现形式为一个审核点，在 description 中概括说明\n"
        "- 审核点总数控制在 5个\n"
        "- id 按 cp_01、cp_02 格式顺序编号\n"
        "- category 必须使用上述四个枚举值之一\n"
        "- severity 必须使用上述三个枚举值之一\n"
        "- 写完 plan.md 和 plan.json 后立即结束\n\n"
        "绝对禁止（违反将导致任务失败）：\n"
        "- 禁止使用 Bash、Glob\n"
        "- 禁止探测目录结构（ls、find 等）\n"
        "- 禁止检查工具是否可用（which、--help）\n"
        "- 禁止做 JSON 格式验证或自检\n"
        "- 禁止写 output.json\n"
        "- 禁止在 plan.md/plan.json 完成后做任何后续操作\n"
        '- 禁止使用中文标点符号（所有 JSON 使用英文 " , :）'
    ),
    "execute": (
        "操作步骤（严格按序，不跳步、不加步）：\n"
        "1. Read plan.json\n"
        "2. Read ../data/guide.md\n"
        "3. 对 plan.json 中的每个 item，Write findings/<id>.json\n"
        "4. 结束\n\n"
        "每个 findings/<id>.json 格式（GovCheckpoint，严格遵循）：\n"
        "{\n"
        '  "id": "cp_01",\n'
        '  "category": "不合理条件限制或排斥供应商",\n'
        '  "title": "审核点标题",\n'
        '  "description": "详细描述该违法违规情形，包含所有具体表现形式",\n'
        '  "legal_basis": [\n'
        '    {"law_name": "法律名", "article": "第X条第Y款", "quote": "法规原文片段"}\n'
        "  ],\n"
        '  "severity": "critical",\n'
        '  "retrieval_hint": "关键词1 关键词2 关键词3"\n'
        "}\n\n"
        "关键规则：\n"
        "- 每个 item 生成一个对应的 findings/<id>.json\n"
        "- description 中需包含该审核点涵盖的所有具体表现形式\n"
        "- legal_basis.quote 必须是法规原文片段，不可意译\n"
        "- retrieval_hint 使用关键词组合，不写完整句子\n"
        "- 所有 JSON 标点使用英文符号\n"
        "- 写完所有 findings 后立即结束\n\n"
        "绝对禁止：\n"
        "- 禁止使用 Bash（含 python3 自检、jq 等）\n"
        "- 禁止使用 mkdir\n"
        "- 禁止写 output.json\n"
        "- 禁止写 working/findings/...（直接写 findings/<id>.json）\n"
        "- 禁止做 JSON 格式验证或自检"
    ),
    "summarize": (
        "你当前的工作目录就是 working/。你的所有文件操作都在 working/ 下进行。\n\n"
        "操作步骤（严格按序，不跳步、不加步）：\n"
        "1. Glob findings/*.json\n"
        "2. Read 每个 finding 文件\n"
        "3. Write output.json（直接写当前目录，即 working/output.json）\n"
        "4. 结束\n\n"
        "output.json 格式：\n"
        '{"checkpoints": [<所有 finding 内容原样合并>]}\n\n'
        "关键规则：\n"
        "- 直接合并 findings，不做去重、不做修改\n"
        "- 所有 JSON 标点使用英文符号\n"
        "- 写好 output.json 后立即结束\n\n"
        "绝对禁止：\n"
        "- 禁止使用 Bash\n"
        "- 禁止写到 ../output/ 或其他任何子目录\n"
        "- 禁止做格式验证或自检"
    ),
}

_AUDITOR_PHASE_PROMPTS: dict[str, str] = {
    "plan": (
        "你是政府采购合规审核专家。任务：针对一个审核点，在招标文书中定位证据并制定审核策略。\n\n"
        "操作步骤（严格按序，不跳步、不加步）：\n"
        "1. Read ../data/checkpoints.json（只有 1 个审核点）\n"
        "2. Read ../data/tender.md\n"
        "3. Grep 在 ../data/tender.md 中搜索与审核点关键词相关的段落\n"
        "4. Write plan.md（审核计划）\n"
        "5. Write plan.json\n"
        "6. 结束\n\n"
        "plan.json 格式：\n"
        "{\n"
        '  "items_to_extract": [\n'
        "    {\n"
        '      "id": "原样复制 checkpoints.json 中的 checkpoint id",\n'
        '      "description": "审核策略描述，包括要搜索的关键证据类型"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "关键规则：\n"
        "- items_to_extract 只包含 1 个 item（只有 1 个审核点）\n"
        "- id 必须原样复制 checkpoints.json 中的 id，禁止自编\n"
        "- 写完文件后立即结束\n\n"
        "绝对禁止（违反将导致任务失败）：\n"
        "- 禁止使用 Bash、Glob\n"
        "- 禁止探测目录结构\n"
        "- 禁止做 JSON 格式验证或自检\n"
        "- 禁止写 output.json\n"
        "- 所有 JSON 标点使用英文半角\n"
        "- 禁止在 JSON 字符串值内出现未转义的英文双引号，内层引号用「」替代"
    ),
    "execute": (
        "操作步骤（严格按序）：\n"
        "1. Read plan.json\n"
        "2. Read ../data/checkpoints.json\n"
        "3. 使用 Bash 执行 qmd 检索命令定位招标文书中的相关段落"
        "（如环境变量 GOVDOC_TENDER_COLLECTION 存在）：\n"
        '   govdoc-cli qmd-search --collection "$GOVDOC_TENDER_COLLECTION"'
        ' --db "$GOVDOC_DB_PATH" --query "<审核点关键词>"\n'
        "   如果 qmd 检索不可用，退回到 Read ../data/tender.md + Grep 搜索\n"
        "4. Read 命中段落核实证据\n"
        "5. Write findings/<checkpoint-id>.json\n"
        "6. 结束\n\n"
        "findings/<checkpoint-id>.json 格式（GovFinding，严格遵循）：\n"
        "{\n"
        '  "checkpoint": {\n'
        '    "id": "原样复制 checkpoints.json 中的 id",\n'
        '    "category": "原样复制",\n'
        '    "title": "原样复制",\n'
        '    "description": "原样复制",\n'
        '    "legal_basis": [],\n'
        '    "severity": "原样复制",\n'
        '    "retrieval_hint": "原样复制"\n'
        "  },\n"
        '  "verdict": {\n'
        '    "verdict": "合规|不合规|存疑",\n'
        '    "rationale": "基于证据的分析推理",\n'
        '    "evidence_quotes": ["招标文书原文片段1", "原文片段2"],\n'
        '    "suggestion": "修改建议（合规时可为空）"\n'
        "  },\n"
        '  "evidence_refs": [],\n'
        '  "case_refs": []\n'
        "}\n\n"
        "判定规则：\n"
        '- verdict 只能是"合规"、"不合规"或"存疑"三者之一\n'
        '- 找到明确合规证据 → "合规"\n'
        '- 找到明确违规证据 → "不合规"\n'
        '- 证据不足或存在疑点 → "存疑"，绝不猜测\n'
        "- evidence_quotes 必须是招标文书原文片段，不可意译\n"
        "- checkpoint 字段原样复制 checkpoints.json 中的内容，禁止修改\n"
        "- 写好 finding 后立即结束\n\n"
        "JSON 安全规则（违反将导致整个审核任务失败）：\n"
        "- 所有 JSON 标点使用英文半角符号\n"
        '- 字符串值内部出现双引号时必须转义为 \\"\n'
        "- 如需引用原文中的引号内容，统一使用「」替代内层引号\n\n"
        "绝对禁止：\n"
        "- 禁止写 output.json\n"
        "- 禁止做 JSON 格式验证或自检\n"
        "- 禁止修改 checkpoint 中的任何字段"
    ),
    "summarize": (
        "你当前的工作目录就是 working/。你的所有文件操作都在 working/ 下进行。\n\n"
        "操作步骤（严格按序，不跳步、不加步）：\n"
        "1. Glob findings/*.json\n"
        "2. Read 所有 finding 文件\n"
        "3. Write output.json（直接写当前目录，即 working/output.json）\n"
        "4. 结束\n\n"
        "output.json 格式：\n"
        '{"findings": [<所有 finding 内容>], "summary": "共审核 N 个审核点，'
        '合规 X 项，不合规 Y 项，存疑 Z 项。"}\n\n'
        "关键规则：\n"
        "- 直接合并 findings，不做修改\n"
        "- summary 用一句话概括结果\n"
        "- 所有 JSON 标点使用英文半角\n"
        "- 禁止在 JSON 字符串值内出现未转义的英文双引号，内层引号用「」替代\n"
        "- 写好 output.json 后立即结束\n\n"
        "绝对禁止：\n"
        "- 禁止使用 Bash\n"
        "- 禁止写到 ../output/ 或其他任何子目录\n"
        "- 禁止做格式验证或自检"
    ),
}

# ── 工具函数 ──


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


# ── PES 子类 ──


class GovDocExtractorPES(_RelaxedPreviousPhaseOutputMixin, ExtractorPES):
    """GovDoc ExtractorPES：通过 build_phase_prompt 注入 phase 级指令。"""

    async def build_phase_prompt(
        self,
        phase: str,
        phase_cfg: PhaseConfig,
        context: dict[str, Any],
        task_prompt: str,
    ) -> str:
        """拼接顺序：phase_prompt + task_prompt + context。

        Scrivai 0.1.7 删除了 PhaseConfig.additional_system_prompt，
        phase 级指令现在通过本方法注入到 user prompt 中。
        """
        parts: list[str] = []
        phase_prompt = _EXTRACTOR_PHASE_PROMPTS.get(phase, "")
        if phase_prompt:
            parts.append(phase_prompt)
        parts.append(task_prompt)
        if context:
            parts.append(json.dumps(context, ensure_ascii=False, default=str))
        return "\n\n".join(parts)


class GovDocAuditorPES(_RelaxedPreviousPhaseOutputMixin, AuditorPES):
    """GovDoc AuditorPES：phase prompt + output validator + recovery。"""

    async def build_phase_prompt(
        self,
        phase: str,
        phase_cfg: PhaseConfig,
        context: dict[str, Any],
        task_prompt: str,
    ) -> str:
        """拼接顺序：phase_prompt + task_prompt + context。"""
        parts: list[str] = []
        phase_prompt = _AUDITOR_PHASE_PROMPTS.get(phase, "")
        if phase_prompt:
            parts.append(phase_prompt)
        parts.append(task_prompt)
        if context:
            parts.append(json.dumps(context, ensure_ascii=False, default=str))
        return "\n\n".join(parts)

    async def postprocess_phase_result(
        self,
        phase: str,
        result: PhaseResult,
        run: Any,
    ) -> None:
        """summarize 阶段：先尝试 recovery，再做 GovFinding 校验。"""
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

        # ── recovery：output.json 不存在时尝试从备选路径恢复 ──
        if not output_path.exists():
            recovered = try_recover_audit_output(result, self.workspace.working_dir)
            if recovered is not None:
                output_path.write_text(
                    json.dumps(recovered, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            else:
                raise FileNotFoundError(
                    f"AuditorPES summarize 阶段 output.json 未生成且无法恢复: {output_path}"
                )

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


# ── Mock PES（replay / 测试用） ──


class GovDocMockExtractorPES(_RelaxedPreviousPhaseOutputMixin, MockPES):
    """MockPES + GovDoc phase prompt 覆写，避免 PromptManager 空 spec 报错。"""

    async def build_phase_prompt(
        self,
        phase: str,
        phase_cfg: PhaseConfig,
        context: dict[str, Any],
        task_prompt: str,
    ) -> str:
        parts: list[str] = []
        phase_prompt = _EXTRACTOR_PHASE_PROMPTS.get(phase, "")
        if phase_prompt:
            parts.append(phase_prompt)
        parts.append(task_prompt)
        if context:
            parts.append(json.dumps(context, ensure_ascii=False, default=str))
        return "\n\n".join(parts)


class GovDocMockAuditorPES(_RelaxedPreviousPhaseOutputMixin, MockPES):
    """MockPES + GovDoc phase prompt 覆写，避免 PromptManager 空 spec 报错。"""

    async def build_phase_prompt(
        self,
        phase: str,
        phase_cfg: PhaseConfig,
        context: dict[str, Any],
        task_prompt: str,
    ) -> str:
        parts: list[str] = []
        phase_prompt = _AUDITOR_PHASE_PROMPTS.get(phase, "")
        if phase_prompt:
            parts.append(phase_prompt)
        parts.append(task_prompt)
        if context:
            parts.append(json.dumps(context, ensure_ascii=False, default=str))
        return "\n\n".join(parts)


# ── Validator ──


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


# ── Recovery ──


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
    recovered = _try_load_output(working_dir / "output.json")
    if recovered is not None:
        return recovered

    workspace_root = working_dir.parent
    recovered = _try_load_output(workspace_root / "output" / "output.json")
    if recovered is not None:
        return recovered

    return _try_load_findings_dir(working_dir / "findings")
