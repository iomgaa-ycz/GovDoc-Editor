from pathlib import Path

import pytest

from govdoc.pipelines.output_utils import relaxed_json_loads
from govdoc.pipelines.pes_overrides import _load_previous_phase_output

# 真实 LLM 输出样本目录（P1b Task 1 采集）
_SAMPLES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "output_utils_samples"


def test_relaxed_json_loads_repairs_unescaped_quotes_in_string_values():
    raw = """
    {
      "verdict": {
        "verdict": "合规",
        "rationale": "经审核，招标文件明确声明"本项目不收取投标保证金"，符合要求。",
        "suggestion": "保持现状"
      }
    }
    """

    data = relaxed_json_loads(raw)

    assert data["verdict"]["verdict"] == "合规"
    assert (
        data["verdict"]["rationale"]
        == '经审核，招标文件明确声明"本项目不收取投标保证金"，符合要求。'
    )


def test_load_previous_phase_output_uses_relaxed_json_for_findings(tmp_path):
    working_dir = tmp_path / "working"
    findings_dir = working_dir / "findings"
    findings_dir.mkdir(parents=True)
    (findings_dir / "cp_02.json").write_text(
        """
        {
          "checkpoint": {"id": "cp_02"},
          "verdict": {
            "verdict": "合规",
            "rationale": "文件中写明"售价：免费"，未发现违规收费。"
          }
        }
        """,
        encoding="utf-8",
    )

    previous_output = _load_previous_phase_output(working_dir, "summarize")

    assert previous_output == {
        "cp_02.json": {
            "checkpoint": {"id": "cp_02"},
            "verdict": {
                "verdict": "合规",
                "rationale": '文件中写明"售价：免费"，未发现违规收费。',
            },
        }
    }


# ---------------------------------------------------------------------------
# P1b Task 2：覆盖 6 类常见 LLM 输出错误 + 真实样本回归护栏
# 错误模式参考 docs/superpowers/plans/2026-04-19-p1b-output-utils-json5.md
# ---------------------------------------------------------------------------


# 错误模式 1：中文弯引号（\u201c / \u201d）
def test_chinese_double_quotes_on_keys_and_values():
    """LLM 常见将键名和字符串值包成中文弯引号，需要统一为 ASCII 双引号。"""
    raw = "{\u201cverdict\u201d: \u201c合规\u201d, \u201cscore\u201d: 95}"

    data = relaxed_json_loads(raw)

    assert data == {"verdict": "合规", "score": 95}


def test_chinese_double_quotes_in_nested_structure():
    """嵌套对象中的中文弯引号也需要修复。"""
    raw = (
        "{\u201cresult\u201d: {\u201cverdict\u201d: \u201c不合规\u201d, "
        "\u201cseverity\u201d: \u201chigh\u201d}}"
    )

    data = relaxed_json_loads(raw)

    assert data == {"result": {"verdict": "不合规", "severity": "high"}}


# 错误模式 2：字符串值内的裸引号（已在基础用例中覆盖一次，这里补一次多字段场景）
def test_multiple_unescaped_quotes_in_values():
    """同一字符串中多处裸引号都应被修复。"""
    raw = '{"note": "文件第3页写明"免费"，第5页又写"象征性收费"，两处矛盾。"}'

    data = relaxed_json_loads(raw)

    assert data["note"] == '文件第3页写明"免费"，第5页又写"象征性收费"，两处矛盾。'


# 错误模式 3：尾随逗号
def test_trailing_comma_in_object():
    """对象末尾尾随逗号应被剥离。"""
    raw = '{"a": 1, "b": 2,}'

    data = relaxed_json_loads(raw)

    assert data == {"a": 1, "b": 2}


def test_trailing_comma_in_array():
    """数组末尾尾随逗号应被剥离。"""
    raw = '{"items": [1, 2, 3,]}'

    data = relaxed_json_loads(raw)

    assert data == {"items": [1, 2, 3]}


# 错误模式 4：单引号键（P1b Task 4 切到 json5 后原生支持）
def test_single_quoted_keys():
    """json5 允许单引号作为字符串分隔符，切到 json5.loads 后直通。"""
    raw = "{'key': 'value', 'n': 1}"

    data = relaxed_json_loads(raw)

    assert data == {"key": "value", "n": 1}


# 错误模式 5：标准 JSON / 嵌套 JSON 直通（回归护栏）
def test_standard_json_passthrough():
    """已是合法 JSON 的输入必须原样解析，不被任何修复逻辑破坏。"""
    raw = '{"id": "cp_01", "title": "供应商资格", "legal_basis": []}'

    data = relaxed_json_loads(raw)

    assert data == {"id": "cp_01", "title": "供应商资格", "legal_basis": []}


def test_nested_standard_json_passthrough():
    """嵌套的标准 JSON 也必须完整保留结构与类型。"""
    raw = (
        '{"checkpoints": [{"id": "cp_01", "severity": "major", '
        '"legal_basis": [{"law": "招标投标法", "article": "第18条"}]}]}'
    )

    data = relaxed_json_loads(raw)

    assert len(data["checkpoints"]) == 1
    assert data["checkpoints"][0]["legal_basis"][0]["article"] == "第18条"


# 错误模式 6：组合错误
def test_chinese_quotes_plus_trailing_comma():
    """中文弯引号与尾随逗号组合出现时都应被修复。"""
    raw = "{\u201ca\u201d: \u201chello\u201d, \u201cb\u201d: 2,}"

    data = relaxed_json_loads(raw)

    assert data == {"a": "hello", "b": 2}


def test_markdown_fence_plus_chinese_quotes():
    """LLM 常把 JSON 包在 ```json``` 代码块里，且使用中文弯引号。"""
    raw = "```json\n{\u201cverdict\u201d: \u201c合规\u201d, \u201cscore\u201d: 100}\n```"

    data = relaxed_json_loads(raw)

    assert data == {"verdict": "合规", "score": 100}


# 错误模式 7：json5 行注释（P1b Task 4 切到 json5 后原生支持）
def test_line_comments():
    """json5 允许 // 行注释，切到 json5.loads 后直通。"""
    raw = '{"a": 1, // 这是一个注释\n"b": 2}'

    data = relaxed_json_loads(raw)

    assert data == {"a": 1, "b": 2}


# 真实样本回归护栏：所有 P1b Task 1 采集的样本必须直通解析
@pytest.mark.parametrize(
    "sample_path",
    sorted(_SAMPLES_DIR.glob("*.json")),
    ids=lambda p: p.name,
)
def test_real_llm_samples_parse_without_error(sample_path: Path):
    """对每个真实 LLM 输出样本调用 relaxed_json_loads，确保不抛异常。

    这是 P1b Task 4（json5 重构）的回归护栏：重构后这些样本仍须全部通过。
    """
    raw = sample_path.read_text(encoding="utf-8")

    data = relaxed_json_loads(raw)

    assert isinstance(data, dict), f"样本 {sample_path.name} 顶层应为对象"
