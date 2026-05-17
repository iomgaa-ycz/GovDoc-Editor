"""审核结论摘要生成——公共函数。"""

from __future__ import annotations

from govdoc.schemas import GovFinding


def generate_summary(findings: list[GovFinding]) -> str:
    """从 findings 列表生成一句话摘要。

    参数:
        findings: GovFinding 列表。

    返回:
        摘要文本。
    """
    if not findings:
        return "无审核结果。"
    total = len(findings)
    compliant = sum(1 for f in findings if f.verdict.verdict == "合规")
    non_compliant = sum(1 for f in findings if f.verdict.verdict == "不合规")
    uncertain = total - compliant - non_compliant
    parts = [f"共审核 {total} 个审核点。"]
    if non_compliant:
        parts.append(f"不合规 {non_compliant} 项。")
    if compliant:
        parts.append(f"合规 {compliant} 项。")
    if uncertain:
        parts.append(f"存疑 {uncertain} 项。")
    return " ".join(parts)
