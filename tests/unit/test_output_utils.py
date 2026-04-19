from govdoc.pipelines.output_utils import relaxed_json_loads
from govdoc.pipelines.pes_overrides import _load_previous_phase_output


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
