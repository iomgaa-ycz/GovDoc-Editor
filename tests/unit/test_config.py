from pathlib import Path

from govdoc.config import load_config


def test_load_config_expands_environment_variables(tmp_path, monkeypatch):
    config_path = tmp_path / "govdoc.yaml"
    monkeypatch.setenv("TEST_GOVDOC_API_KEY", "secret-key")
    config_path.write_text(
        "\n".join(
            [
                "app:",
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


class TestConverterConfig:
    """验证 AppConfig.converter 字段。"""

    def test_default_is_empty_dict(self) -> None:
        """AppConfig 默认 converter 为空 dict。"""
        from govdoc.config import AppConfig

        cfg = AppConfig()
        assert cfg.converter == {}

    def test_load_config_reads_converter(self) -> None:
        """完整配置加载后 app.converter 包含后端配置。"""
        cfg = load_config()
        assert "monkey_endpoints" in cfg.app.converter
