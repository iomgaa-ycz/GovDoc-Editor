"""DeepXiv CLI 的轻量适配器。"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from typing import cast

if shutil.which("deepxiv") is None:
    print("警告: 未找到 deepxiv CLI，已跳过 DeepXiv 适配器。", file=sys.stderr)
    sys.exit(0)


def _run_deepxiv(arguments: list[str]) -> int:
    """调用底层 deepxiv 命令并透传输出。"""
    completed = subprocess.run(["deepxiv", *arguments], check=False)
    return completed.returncode


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="DeepXiv 命令适配器")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command_name in ("search", "paper-brief", "paper-head", "paper-section"):
        subparser = subparsers.add_parser(command_name, help=f"转发 deepxiv {command_name} 命令")
        subparser.add_argument("args", nargs=argparse.REMAINDER, help="透传给 deepxiv 的参数")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        command_args = [args.command, *cast(list[str], args.args)]
        return _run_deepxiv(command_args)
    except OSError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
