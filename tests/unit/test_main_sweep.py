"""FastAPI 启动清扫任务测试。"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.config import (
    AppConfig,
    CompareConfig,
    GovDocConfig,
    ModelServiceConfig,
    QmdConfig,
    WorkspaceConfig,
)
from govdoc.db.models import CompareRun


def test_startup_sweep_marks_pending_and_running_compare_runs_failed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """服务启动时应把未终结的 CompareRun 标记为 failed。"""
    database_url = f"sqlite:///{tmp_path}/app.db"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(CompareRun(id="pending-run", status="pending", file_count=2))
        session.add(CompareRun(id="running-run", status="running", file_count=2))
        session.add(CompareRun(id="done-run", status="completed", file_count=2))
        session.commit()

    @contextmanager
    def _session_scope() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    cfg = GovDocConfig(
        app=AppConfig(storage_root=str(tmp_path / "storage"), database_url=database_url),
        model=ModelServiceConfig(model="glm-5.1"),
        qmd=QmdConfig(db_path=str(tmp_path / "qmd.sqlite")),
        workspace=WorkspaceConfig(
            workspaces_root=str(tmp_path / "workspaces"),
            archives_root=str(tmp_path / "archives"),
        ),
        compare=CompareConfig(),
    )

    import govdoc.api.main as main_module

    monkeypatch.setattr(main_module, "init_db", lambda: None)
    monkeypatch.setattr("govdoc.config.load_config", lambda: cfg)
    monkeypatch.setattr(main_module, "get_db_session", _session_scope)

    app = main_module.create_app()
    for handler in app.router.on_startup:
        handler()

    with Session(engine) as session:
        runs = {run.id: run for run in session.exec(select(CompareRun)).all()}

    assert runs["pending-run"].status == "failed"
    assert runs["running-run"].status == "failed"
    assert runs["pending-run"].error == "对比任务中途中断，未能完成，请点击「重试」继续"
    assert runs["done-run"].status == "completed"
