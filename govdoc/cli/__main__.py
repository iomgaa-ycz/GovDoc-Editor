"""GovDoc 业务 CLI 入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from govdoc.cli.tender import (
    locate_section_command,
    parse_tender_command,
    validate_checkpoint_command,
)


def _emit_stdout(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _emit_stderr(error: Exception) -> None:
    print(
        json.dumps({"error": type(error).__name__, "message": str(error)}, ensure_ascii=False),
        file=sys.stderr,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="govdoc-cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_tender = subparsers.add_parser("parse-tender")
    parse_tender.add_argument("--input", required=True)

    locate = subparsers.add_parser("locate-section")
    locate.add_argument("--md", required=True)
    locate.add_argument("--section", required=True)

    validate = subparsers.add_parser("validate-checkpoint")
    validate.add_argument("--json", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "parse-tender":
            _emit_stdout(parse_tender_command(Path(args.input)))
            return 0
        if args.command == "locate-section":
            _emit_stdout(locate_section_command(Path(args.md), args.section))
            return 0
        if args.command == "validate-checkpoint":
            _emit_stdout(validate_checkpoint_command(args.json))
            return 0
        parser.error(f"未知命令: {args.command}")
    except Exception as exc:  # noqa: BLE001 - CLI should always emit JSON
        _emit_stderr(exc)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

