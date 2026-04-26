from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from govdoc.cli.__main__ import main
from govdoc.cli.tender import (
    _resolve_qmd_db_path,
    _search_result_to_json,
    qmd_search_command,
)


def test_qmd_search_command_uses_scrivai_qmd_facade():
    hit = MagicMock()
    hit.model_dump.return_value = {
        "chunk_ref": {
            "document_id": "tender-1",
            "chunk_index": 0,
            "char_start": 0,
            "char_end": 12,
        },
        "text": "本项目不接受联合体投标。",
        "score": 0.9,
        "metadata": {"source": "tender.docx"},
    }
    collection = MagicMock()
    collection.hybrid_search.return_value = [hit]
    client = MagicMock()
    client.collection.return_value = collection

    with patch("govdoc.cli.tender.build_qmd_client_from_config", return_value=client) as factory:
        payload = qmd_search_command(
            collection="run_abc_tender",
            query="联合体",
            db_path="/tmp/qmd.sqlite",
            top_k=3,
            rerank=True,
            filters_json='{"audit_run":"abc"}',
        )

    factory.assert_called_once()
    assert str(factory.call_args.args[0]) == "/tmp/qmd.sqlite"
    client.collection.assert_called_once_with("run_abc_tender")
    collection.hybrid_search.assert_called_once_with(
        "联合体",
        top_k=3,
        rerank=True,
        filters={"audit_run": "abc"},
    )
    client.close.assert_called_once_with()
    assert payload["collection"] == "run_abc_tender"
    assert payload["hits"][0]["text"] == "本项目不接受联合体投标。"


def test_qmd_search_command_accepts_env_db_path(monkeypatch):
    client = MagicMock()
    client.collection.return_value.hybrid_search.return_value = []
    monkeypatch.setenv("GOVDOC_DB_PATH", "/tmp/env-qmd.sqlite")

    with patch("govdoc.cli.tender.build_qmd_client_from_config", return_value=client) as factory:
        payload = qmd_search_command(collection="run_abc_tender", query="关键词")

    assert str(factory.call_args.args[0]) == "/tmp/env-qmd.sqlite"
    assert payload == {"collection": "run_abc_tender", "query": "关键词", "hits": []}


def test_cli_qmd_search_emits_json(capsys):
    with patch("govdoc.cli.__main__.qmd_search_command") as command:
        command.return_value = {"collection": "c", "query": "q", "hits": []}

        code = main(
            [
                "qmd-search",
                "--collection",
                "c",
                "--db",
                "/tmp/qmd.sqlite",
                "--query",
                "q",
            ]
        )

    assert code == 0
    assert json.loads(capsys.readouterr().out) == {"collection": "c", "query": "q", "hits": []}
    command.assert_called_once_with(
        collection="c",
        query="q",
        db_path="/tmp/qmd.sqlite",
        top_k=5,
        rerank=False,
        filters_json=None,
    )


def test_qmd_search_rejects_non_object_filters():
    with patch("govdoc.cli.tender.build_qmd_client_from_config") as factory:
        client = MagicMock()
        factory.return_value = client
        client.collection.return_value.hybrid_search.return_value = []

        with pytest.raises(ValueError, match="must be a JSON object"):
            qmd_search_command(
                collection="c",
                query="q",
                db_path="/tmp/qmd.sqlite",
                filters_json="[1, 2, 3]",
            )


def test_resolve_qmd_db_path_raises_when_missing(monkeypatch):
    monkeypatch.delenv("GOVDOC_DB_PATH", raising=False)
    monkeypatch.delenv("QMD_DB_PATH", raising=False)

    with pytest.raises(ValueError, match="missing qmd db path"):
        _resolve_qmd_db_path(None)


def test_cli_qmd_search_emits_error_json_on_failure(capsys):
    with patch("govdoc.cli.__main__.qmd_search_command") as command:
        command.side_effect = RuntimeError("db not found")
        code = main(["qmd-search", "--collection", "c", "--query", "q", "--db", "/bad"])

    assert code == 1
    err = json.loads(capsys.readouterr().err)
    assert err["error"] == "RuntimeError"
    assert "db not found" in err["message"]


def test_search_result_to_json_dict_fallback():
    class FakeHit:
        def __init__(self):
            self.text = "段落内容"
            self.score = 0.8
            self._internal = "skip"

    result = _search_result_to_json(FakeHit())
    assert result == {"text": "段落内容", "score": 0.8}


def test_search_result_to_json_str_fallback():
    result = _search_result_to_json(42)
    assert result == {"value": "42"}
