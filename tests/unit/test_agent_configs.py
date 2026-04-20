from pathlib import Path

from scrivai import load_pes_config


def test_agent_configs_load_with_current_pes_schema():
    repo_root = Path(__file__).resolve().parents[2]
    extractor = load_pes_config(repo_root / "agents" / "gov-extractor.yaml")
    auditor = load_pes_config(repo_root / "agents" / "gov-auditor.yaml")

    assert extractor.default_skills == ["gov-extract-checkpoint", "gov-cite-legal-basis"]
    assert auditor.default_skills == [
        "gov-audit-tender",
        "gov-locate-evidence",
        "gov-cite-legal-basis",
    ]

    assert "Bash" in auditor.phases["execute"].allowed_tools
    assert auditor.external_cli_tools == ["govdoc-cli"]

    for name, phase_cfg in extractor.phases.items():
        assert not hasattr(phase_cfg, "additional_system_prompt"), (
            f"extractor.{name} should not have additional_system_prompt"
        )
    for name, phase_cfg in auditor.phases.items():
        assert not hasattr(phase_cfg, "additional_system_prompt"), (
            f"auditor.{name} should not have additional_system_prompt"
        )
