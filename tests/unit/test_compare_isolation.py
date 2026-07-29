"""文档对比子进程隔离测试。"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
import asyncio

from sqlmodel import Session, SQLModel, create_engine

from govdoc.api.routes import compare as compare_route
from govdoc.config import (
    AppConfig,
    AuditConfig,
    CompareConfig,
    GovDocConfig,
    ModelServiceConfig,
    QmdConfig,
    WorkspaceConfig,
)
from govdoc.db.models import CompareRun


def _make_config(tmp_path: Path, database_url: str, timeout_s: int) -> GovDocConfig:
    """构造隔离的最小 GovDocConfig。"""
    return GovDocConfig(
        app=AppConfig(storage_root=str(tmp_path / "storage"), database_url=database_url),
        model=ModelServiceConfig(model="glm-5.1"),
        qmd=QmdConfig(db_path=str(tmp_path / "qmd.sqlite")),
        workspace=WorkspaceConfig(
            workspaces_root=str(tmp_path / "workspaces"),
            archives_root=str(tmp_path / "archives"),
        ),
        audit=AuditConfig(),
        compare=CompareConfig(pdf_timeout_s=timeout_s, max_concurrent=1),
    )


def _read_run(database_url: str, review_id: str) -> CompareRun:
    """从临时 SQLite 读取 CompareRun。"""
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    with Session(engine) as session:
        run = session.get(CompareRun, review_id)
        assert run is not None
        session.expunge(run)
        return run


def test_compare_subprocess_completes_small_markdown_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """正常小输入应在子进程完成，并把 run 标记为 completed。"""
    database_url = f"sqlite:///{tmp_path}/compare.db"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(CompareRun(id="run-ok", status="pending", file_count=2))
        session.commit()

    @contextmanager
    def _session_scope() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    first.write_text("共同段落内容用于测试。\n\n独有A。", encoding="utf-8")
    second.write_text("共同段落内容用于测试。\n\n独有B。", encoding="utf-8")
    cfg = _make_config(tmp_path, database_url, timeout_s=30)
    monkeypatch.setattr(compare_route, "get_config", lambda: cfg, raising=False)
    monkeypatch.setattr(compare_route, "get_db_session", _session_scope)

    asyncio.run(
        compare_route._run_compare_from_docs(
            "run-ok", [(str(first), "a.docx"), (str(second), "b.docx")]
        )
    )

    run = _read_run(database_url, "run-ok")
    assert run.status == "completed"
    assert run.result_path is not None


def test_compare_subprocess_memory_death_marks_failed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """子进程被内存上限杀死时，父进程应正常返回并标记 failed。"""
    database_url = f"sqlite:///{tmp_path}/compare.db"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(CompareRun(id="run-oom", status="pending", file_count=2))
        session.commit()

    @contextmanager
    def _session_scope() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    first.write_text("共同段落内容用于测试。" * 1000, encoding="utf-8")
    second.write_text("共同段落内容用于测试。" * 1000, encoding="utf-8")
    cfg = _make_config(tmp_path, database_url, timeout_s=30)
    monkeypatch.setattr(compare_route, "get_config", lambda: cfg, raising=False)
    monkeypatch.setattr(compare_route, "get_db_session", _session_scope)
    monkeypatch.setattr(compare_route, "COMPARE_CHILD_MEMORY_LIMIT_BYTES", 32 * 1024 * 1024)

    asyncio.run(
        compare_route._run_compare_from_docs(
            "run-oom", [(str(first), "a.docx"), (str(second), "b.docx")]
        )
    )

    run = _read_run(database_url, "run-oom")
    assert run.status == "failed"
    assert run.error == "对比规模过大或文件异常，已安全终止，请减少文件数量后重试"
