from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compare import compare_docx_files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare two DOCX files and export shared text results."
    )
    parser.add_argument("first_file", help="Path to the first DOCX file.")
    parser.add_argument("second_file", help="Path to the second DOCX file.")
    parser.add_argument(
        "-o",
        "--output-dir",
        default="output",
        help="Directory for exported comparison results.",
    )
    parser.add_argument(
        "--min-segment-length",
        type=int,
        default=12,
        help="Minimum character length for continuous common text segments.",
    )
    return parser


def write_exact_matches(path: Path, matches: list[dict], label: str) -> None:
    lines: list[str] = []

    if not matches:
        lines.append(f"No common {label} found.")
    else:
        for index, match in enumerate(matches, start=1):
            lines.append(f"[{index}]")
            lines.append(match["text"])
            lines.append(f"first_positions: {', '.join(map(str, match['first_positions']))}")
            lines.append(f"second_positions: {', '.join(map(str, match['second_positions']))}")
            lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_segments(path: Path, segments: list[dict]) -> None:
    lines: list[str] = []

    if not segments:
        lines.append("No continuous common text segments found.")
    else:
        for index, segment in enumerate(segments, start=1):
            lines.append(f"[{index}] length={segment['length']}")
            lines.append(
                "first_range: "
                f"{segment['first_start']}..{segment['first_end']}"
            )
            lines.append(
                "second_range: "
                f"{segment['second_start']}..{segment['second_end']}"
            )
            lines.append(segment["text"])
            lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = compare_docx_files(
        first_path=args.first_file,
        second_path=args.second_file,
        min_segment_length=args.min_segment_length,
    )

    (output_dir / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_exact_matches(
        output_dir / "common_paragraphs.txt",
        result["common_paragraphs"],
        "paragraphs",
    )
    write_exact_matches(
        output_dir / "common_sentences.txt",
        result["common_sentences"],
        "sentences",
    )
    write_segments(output_dir / "common_segments.txt", result["common_segments"])

    summary = result["summary"]
    print("Comparison finished.")
    print(f"Output directory: {output_dir}")
    print(f"Common paragraphs: {summary['common_paragraph_count']}")
    print(f"Common sentences: {summary['common_sentence_count']}")
    print(f"Common segments: {summary['common_segment_count']}")

    return 0
