"""Tender CLI helpers."""

from __future__ import annotations

import json
from pathlib import Path

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
