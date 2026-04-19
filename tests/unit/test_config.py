import os
from pathlib import Path

from govdoc.config import load_config


def test_load_config_expands_environment_variables(tmp_path, monkeypatch):
    config_path = tmp_path / "govdoc.yaml"
    monkeypatch.setenv("TEST_GOVDOC_API_KEY", "secret-key")
    config_path.write_text(
        "\n".join(
            [
                "app:",
                "  host: 127.0.0.1",
                "  port: 9000",
                "  storage_root: ./data/storage",
                "  database_url: sqlite:///./data/app.sqlite",
                "model:",
                "  model: test-model",
                "  base_url: https://example.com",
                "  api_key: ${TEST_GOVDOC_API_KEY}",
                "  fallback_model: test-fallback",
                "qmd:",
                "  db_path: ./data/qmd.sqlite",
                "workspace:",
                "  workspaces_root: ~/.govdoc/workspaces",
                "  archives_root: ~/.govdoc/archives",
                "  cleanup_days: 30",
                "evolution:",
                "  enabled: false",
                "  proposer_model: test-model",
                "  frontier_size: 5",
                "  eval_dataset_path: ./data/eval/checkpoints_golden.json",
            ]
        ),
        encoding="utf-8",
    )
    config = load_config(config_path)
    assert config.model.api_key == "secret-key"
    assert config.project_root == Path(__file__).resolve().parents[2]

