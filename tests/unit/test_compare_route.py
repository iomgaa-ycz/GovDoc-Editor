"""文档对比路由单元测试。"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
import asyncio
import json
import uuid

from fastapi import BackgroundTasks
import pytest
from sqlmodel import Session, SQLModel, create_engine

from govdoc.api.routes.compare import create_compare_run, get_compare_summary
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
