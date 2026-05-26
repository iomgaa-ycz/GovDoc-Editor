from pathlib import Path

from govdoc.config import CompareConfig, load_config


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


class TestCompareOcrBackend:
    """验证 CompareConfig 支持 ocr_backend 字段。"""

    def test_default_is_glm(self) -> None:
        """CompareConfig 默认 ocr_backend 为 glm。"""
        cfg = CompareConfig()
        assert cfg.ocr_backend == "glm"

    def test_load_config_reads_compare_ocr_backend(self) -> None:
        """完整配置加载后 compare.ocr_backend 为 glm。"""
        cfg = load_config()
        assert cfg.compare.ocr_backend == "glm"
