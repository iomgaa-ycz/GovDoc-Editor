"""测试 fixture 与 MockPES replay 辅助。"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from scrivai import PhaseOutcome


@dataclass(slots=True)
class MockReplayBundle:
    root: Path
    phase_outcomes: dict[str, list[PhaseOutcome]]

    @property
    def working_seed_dir(self) -> Path:
        return self.root / "working"


def get_fixtures_root(*, strict: bool = True) -> Path:
    raw = os.environ.get("GOVDOC_FIXTURES")
    if raw:
        root = Path(raw).expanduser().resolve()
    else:
        root = (Path(__file__).resolve().parents[1] / "tests" / "fixtures").resolve()
    if strict and not root.is_dir():
        raise FileNotFoundError(f"未找到 GOVDOC fixtures 目录: {root}")
    return root


def load_mock_replay(path: str | Path) -> MockReplayBundle:
    replay_root = Path(path).expanduser().resolve()
    if not replay_root.is_dir():
        raise FileNotFoundError(f"未找到 MockPES replay 目录: {replay_root}")

    raw = json.loads((replay_root / "phase_outcomes.json").read_text(encoding="utf-8"))
    phase_outcomes: dict[str, list[PhaseOutcome]] = {}
    for phase_name, attempts in raw.items():
        phase_outcomes[phase_name] = [
            PhaseOutcome(
                response_text=attempt.get("response_text", ""),
                usage=attempt.get("usage", {}),
                error=attempt.get("error"),
                error_type=attempt.get("error_type"),
                is_retryable=attempt.get("is_retryable", False),
                produced_files=list(attempt.get("produced_files", [])),
            )
            for attempt in attempts
        ]
    return MockReplayBundle(root=replay_root, phase_outcomes=phase_outcomes)


def seed_working_tree(seed_dir: Path, target_dir: Path) -> None:
    if not seed_dir.exists():
        return
    for source in seed_dir.rglob("*"):
        relative = source.relative_to(seed_dir)
        destination = target_dir / relative
        if source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
