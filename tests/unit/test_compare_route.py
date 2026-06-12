"""文档对比路由单元测试。"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
import json
import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine

from govdoc.api.routes.compare import get_compare_summary
from govdoc.db.models import CompareRun


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
                "similarity": None,
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
                "similarity": None,
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
                "similarity": None,
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
                "similarity": 0.9,
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
