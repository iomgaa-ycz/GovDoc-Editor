"""Tender CLI helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from scrivai import build_qmd_client_from_config

from govdoc.parsers.tender_doc import locate_section, parse
from govdoc.schemas import GovCheckpoint


def parse_tender_command(input_path: Path) -> dict[str, object]:
    md = input_path.read_text(encoding="utf-8")
    structure = parse(md)
    return structure.model_dump(mode="json")


def locate_section_command(input_path: Path, section: str) -> dict[str, object]:
    md = input_path.read_text(encoding="utf-8")
    result = locate_section(md, section)
    if result is None:
        return {"text": "", "char_start": -1, "char_end": -1}
    return result.model_dump(mode="json")


def validate_checkpoint_command(raw_json: str) -> dict[str, object]:
    try:
        payload = json.loads(raw_json)
        GovCheckpoint.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - CLI returns structured error JSON
        return {"valid": False, "errors": [str(exc)]}
    return {"valid": True}


def _resolve_qmd_db_path(db_path: str | None) -> Path:
    resolved = db_path or os.environ.get("GOVDOC_DB_PATH") or os.environ.get("QMD_DB_PATH")
    if not resolved:
        raise ValueError("missing qmd db path: pass --db/--db-path or set GOVDOC_DB_PATH")
    return Path(resolved).expanduser()


def _search_result_to_json(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    if hasattr(result, "__dict__"):
        return {key: value for key, value in result.__dict__.items() if not key.startswith("_")}
    return {"value": str(result)}


def qmd_search_command(
    *,
    collection: str,
    query: str,
    db_path: str | None = None,
    top_k: int = 5,
    rerank: bool = False,
    filters_json: str | None = None,
) -> dict[str, Any]:
    """Search a GovDoc/qmd collection through Scrivai's qmd facade."""
    filters = json.loads(filters_json) if filters_json else None
    if filters is not None and not isinstance(filters, dict):
        raise ValueError("--filters must be a JSON object")

    client = build_qmd_client_from_config(_resolve_qmd_db_path(db_path))
    try:
        hits = client.collection(collection).hybrid_search(
            query,
            top_k=top_k,
            rerank=rerank,
            filters=filters,
        )
        return {
            "collection": collection,
            "query": query,
            "hits": [_search_result_to_json(hit) for hit in hits],
        }
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
