"""文档对比路由单元测试。"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator
import asyncio
import json
import uuid

from fastapi import BackgroundTasks, Response
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.api.routes.compare import create_compare_run, get_compare_summary, retry_compare_run
from govdoc.config import CompareConfig
from govdoc.db.models import CompareRun, Document


@pytest.fixture()
def compare_session(monkeypatch: pytest.MonkeyPatch) -> Iterator[Session]:
    """创建隔离内存数据库并替换 compare 路由的会话入口。"""
    db_name = f"test_compare_route_{uuid.uuid4().hex}"
    engine = create_engine(
        f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    @contextmanager
    def _fake_session() -> Iterator[Session]:
        yield session

    monkeypatch.setattr("govdoc.api.routes.compare.get_db_session", _fake_session)
    try:
        yield session
    finally:
        session.close()
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


def _write_summary(review_dir: Path) -> None:
    """写入含不同长度匹配项的 summary.json。"""
    payload = {
        "reviewId": "review-1",
        "summary": {
            "fileCount": 2,
            "files": [],
            "commonParagraphCount": 2,
            "commonSentenceCount": 1,
            "commonSegmentCount": 0,
            "commonSimilarCount": 1,
            "matchCount": 4,
            "minSegmentLength": 16,
        },
        "matches": [
            {
                "id": "paragraph-short",
                "category": "paragraph",
                "label": "相同段落",
                "color": "#f5b700",
                "length": 3,
                "fileIndices": [0, 1],
                "occurrenceCount": 2,
                "preview": "短句。",
            },
            {
                "id": "paragraph-long",
                "category": "paragraph",
                "label": "相同段落",
                "color": "#f5b700",
                "length": 12,
                "fileIndices": [0, 1],
                "occurrenceCount": 2,
                "preview": "这是一段足够长的文本。",
            },
            {
                "id": "sentence-long",
                "category": "sentence",
                "label": "相同句子",
                "color": "#12b5cb",
                "length": 11,
                "fileIndices": [0, 1],
                "occurrenceCount": 2,
                "preview": "这是一句足够长的话。",
            },
            {
                "id": "similar-short",
                "category": "similar",
                "label": "近似段落",
                "color": "#9b59b6",
                "length": 8,
                "fileIndices": [0, 1],
                "occurrenceCount": 2,
                "preview": "近似但较短。",
            },
        ],
        "categories": [],
        "downloads": {"files": {}},
        "artifacts": {"reviewDir": str(review_dir), "downloadNames": {}},
    }
    (review_dir / "summary.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    (review_dir / "review.json").write_text("{}", encoding="utf-8")


def test_compare_summary_filters_by_dynamic_min_length(
    compare_session: Session,
    tmp_path: Path,
) -> None:
    """summary 接口应按调用方传入的最小长度阈值动态过滤匹配项。"""
    review_dir = tmp_path / "review-1"
    review_dir.mkdir()
    _write_summary(review_dir)
    compare_session.add(
        CompareRun(
            id="review-1",
            status="completed",
            file_count=2,
            result_path=str(review_dir / "review.json"),
        )
    )
    compare_session.commit()

    data = get_compare_summary("review-1", category="paragraph", min_length=10)

    assert [item["id"] for item in data["matches"]] == ["paragraph-long"]
    assert data["matchPagination"]["totalInCategory"] == 1
    assert data["matchPagination"]["categoryCounts"] == {
        "paragraph": 1,
        "sentence": 1,
    }


def test_create_compare_run_rejects_missing_markdown_result(
    compare_session: Session,
    tmp_path: Path,
) -> None:
    """文档 markdown_path 为空或文件不存在时应返回 400，不回退 raw_path。"""
    raw_path = tmp_path / "source.docx"
    raw_path.write_bytes(b"fake")
    docs = [
        Document(
            id="doc-a",
            filename="a.docx",
            file_type="docx",
            file_size=4,
            sha256="sha-a",
            raw_path=str(raw_path),
            markdown_path=None,
            status="ready",
        ),
        Document(
            id="doc-b",
            filename="b.docx",
            file_type="docx",
            file_size=4,
            sha256="sha-b",
            raw_path=str(raw_path),
            markdown_path=str(tmp_path / "missing.md"),
            status="ready",
        ),
    ]
    compare_session.add_all(docs)
    compare_session.commit()

    response = asyncio.run(
        create_compare_run({"document_ids": ["doc-a", "doc-b"]}, background_tasks=BackgroundTasks())
    )

    assert response.status_code == 400
    assert (
        json.loads(response.body)["detail"]
        == "文档「a.docx」转换结果缺失，请在文件管理中重新转换后再对比"
    )


def test_create_compare_run_rejects_over_max_files(
    compare_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """超过后端配置的最大文件数时应在创建任务前返回 400。"""
    markdown_paths = []
    for index in range(3):
        path = tmp_path / f"doc-{index}.md"
        path.write_text(f"文档{index}", encoding="utf-8")
        markdown_paths.append(path)
        compare_session.add(
            Document(
                id=f"doc-{index}",
                filename=f"doc-{index}.docx",
                file_type="docx",
                file_size=8,
                sha256=f"sha-{index}",
                raw_path=str(tmp_path / f"doc-{index}.docx"),
                markdown_path=str(path),
                status="ready",
            )
        )
    compare_session.commit()

    class FakeConfig:
        compare = CompareConfig(max_files=2)

    monkeypatch.setattr("govdoc.api.routes.compare.get_config", lambda: FakeConfig())

    response = asyncio.run(
        create_compare_run(
            {"document_ids": [f"doc-{index}" for index in range(3)]},
            background_tasks=BackgroundTasks(),
        )
    )

    assert response.status_code == 400
    assert json.loads(response.body)["detail"] == "当前部署最多支持 2 份文件。"


def _add_ready_compare_documents(compare_session: Session, tmp_path: Path) -> list[str]:
    """写入两个已转换文档，返回可用于重试的文档 ID。"""
    document_ids = ["doc-a", "doc-b"]
    for document_id in document_ids:
        markdown_path = tmp_path / f"{document_id}.md"
        markdown_path.write_text(f"{document_id} 已转换内容", encoding="utf-8")
        compare_session.add(
            Document(
                id=document_id,
                filename=f"{document_id}.docx",
                file_type="docx",
                file_size=16,
                sha256=f"sha-{document_id}",
                raw_path=str(tmp_path / f"{document_id}.docx"),
                markdown_path=str(markdown_path),
                status="ready",
            )
        )
    compare_session.commit()
    return document_ids


def _compare_run_count(compare_session: Session) -> int:
    """返回当前 CompareRun 总行数。"""
    return len(compare_session.exec(select(CompareRun)).all())


def test_retry_failed_compare_run_reuses_original_row(
    compare_session: Session,
    tmp_path: Path,
) -> None:
    """失败任务重试应复用原 reviewId，并原地清理失败状态。"""
    document_ids = _add_ready_compare_documents(compare_session, tmp_path)
    compare_session.add(
        CompareRun(
            id="review-failed",
            status="failed",
            file_count=2,
            document_ids=json.dumps(document_ids),
            error="子进程异常退出",
            progress_json=json.dumps({"phase": "matching"}, ensure_ascii=False),
            result_path=str(tmp_path / "old-review.json"),
            completed_at=datetime.utcnow(),
        )
    )
    compare_session.commit()
    before_count = _compare_run_count(compare_session)
    background_tasks = BackgroundTasks()

    response = asyncio.run(
        retry_compare_run("review-failed", background_tasks, response=Response(status_code=202))
    )

    compare_session.expire_all()
    run = compare_session.get(CompareRun, "review-failed")
    assert response == {"reviewId": "review-failed", "status": "pending"}
    assert run is not None
    assert run.status == "pending"
    assert run.error is None
    assert run.progress_json is None
    assert run.result_path is None
    assert run.completed_at is None
    assert _compare_run_count(compare_session) == before_count
    assert len(background_tasks.tasks) == 1


def test_retry_pending_compare_run_returns_current_status_without_dispatch(
    compare_session: Session,
    tmp_path: Path,
) -> None:
    """排队中的任务再次重试应幂等返回，不重复派发后台任务。"""
    document_ids = _add_ready_compare_documents(compare_session, tmp_path)
    compare_session.add(
        CompareRun(
            id="review-pending",
            status="pending",
            file_count=2,
            document_ids=json.dumps(document_ids),
            error="保留现场",
        )
    )
    compare_session.commit()
    before_count = _compare_run_count(compare_session)
    background_tasks = BackgroundTasks()
    http_response = Response(status_code=202)

    response = asyncio.run(
        retry_compare_run("review-pending", background_tasks, response=http_response)
    )

    compare_session.expire_all()
    run = compare_session.get(CompareRun, "review-pending")
    assert response == {"reviewId": "review-pending", "status": "pending"}
    assert http_response.status_code == 200
    assert run is not None
    assert run.status == "pending"
    assert run.error == "保留现场"
    assert _compare_run_count(compare_session) == before_count
    assert len(background_tasks.tasks) == 0


def test_retry_failed_compare_run_twice_keeps_single_row(
    compare_session: Session,
    tmp_path: Path,
) -> None:
    """连续重试同一失败任务时第二次应走幂等分支，不新增任务行。"""
    document_ids = _add_ready_compare_documents(compare_session, tmp_path)
    compare_session.add(
        CompareRun(
            id="review-clicked",
            status="failed",
            file_count=2,
            document_ids=json.dumps(document_ids),
            error="首次失败",
        )
    )
    compare_session.commit()
    before_count = _compare_run_count(compare_session)
    first_background_tasks = BackgroundTasks()
    second_background_tasks = BackgroundTasks()
    first_http_response = Response(status_code=202)
    second_http_response = Response(status_code=202)

    first_response = asyncio.run(
        retry_compare_run("review-clicked", first_background_tasks, response=first_http_response)
    )
    second_response = asyncio.run(
        retry_compare_run("review-clicked", second_background_tasks, response=second_http_response)
    )

    compare_session.expire_all()
    assert first_response == {"reviewId": "review-clicked", "status": "pending"}
    assert second_response == {"reviewId": "review-clicked", "status": "pending"}
    assert first_http_response.status_code == 202
    assert second_http_response.status_code == 200
    assert _compare_run_count(compare_session) == before_count
    assert len(first_background_tasks.tasks) == 1
    assert len(second_background_tasks.tasks) == 0


def test_retry_failed_compare_run_removes_old_review_dir_only_under_compare_root(
    compare_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """失败任务重试后只删除对比根目录下的旧 review_dir。"""
    document_ids = _add_ready_compare_documents(compare_session, tmp_path)
    compare_root = tmp_path / "storage" / "compare"
    old_review_dir = compare_root / "old-review"
    old_review_dir.mkdir(parents=True)
    (old_review_dir / "review.json").write_text("{}", encoding="utf-8")
    (old_review_dir / "uploads").mkdir()
    (old_review_dir / "uploads" / "copy.docx").write_bytes(b"old-copy")

    outside_review_dir = tmp_path / "outside-review"
    outside_review_dir.mkdir()
    (outside_review_dir / "review.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "govdoc.api.routes.compare.get_compare_root", lambda: compare_root, raising=False
    )

    compare_session.add(
        CompareRun(
            id="review-cleanup",
            status="failed",
            file_count=2,
            document_ids=json.dumps(document_ids),
            result_path=str(old_review_dir / "review.json"),
        )
    )
    compare_session.add(
        CompareRun(
            id="review-outside",
            status="failed",
            file_count=2,
            document_ids=json.dumps(document_ids),
            result_path=str(outside_review_dir / "review.json"),
        )
    )
    compare_session.commit()

    asyncio.run(
        retry_compare_run(
            "review-cleanup",
            BackgroundTasks(),
            response=Response(status_code=202),
        )
    )
    asyncio.run(
        retry_compare_run(
            "review-outside",
            BackgroundTasks(),
            response=Response(status_code=202),
        )
    )

    assert not old_review_dir.exists()
    assert outside_review_dir.exists()
