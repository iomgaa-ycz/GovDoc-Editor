---
type: plan
node_id: plan:compare-lazy-load
title: 文档对比分层加载与前端重构实施计划
date: 2026-05-27
---

# 文档对比分层加载与前端重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解决文档对比 861MB JSON 导致前端崩溃的问题，通过后端存储拆分 + API 分层 + 前端按需加载实现大文件对比结果秒开。

**Architecture:** 后端对比完成时拆分生成 `summary.json`（~5MB 摘要）+ `blocks_{N}.json`（按文件分段落）+ `match_index.json`（匹配索引）。新增 summary/context/retry 三个 API。前端入口页合并进度展示，结果页改为摘要首屏 + 点击匹配按需加载上下文。

**Tech Stack:** Python/FastAPI/Pydantic v2 (后端), React/TypeScript/shadcn-ui (前端)

**Design doc:** `research-wiki/designs/compare-lazy-load.md`

---

## 文件变更清单

| 操作 | 文件 | 职责 |
|------|------|------|
| MODIFY | `govdoc/config.py` | 新增 `max_concurrent` 配置项 |
| MODIFY | `govdoc.yaml` | 新增 `compare.max_concurrent: 1` |
| MODIFY | `govdoc/schemas/compare.py` | 新增 `MatchSummaryItem`、`CompareSummaryResponse`、`CompareContextResponse`、`FileContext` schema |
| CREATE | `govdoc/compare/splitter.py` | 从 `CompareResponse` 生成拆分文件（summary/blocks/match_index） |
| CREATE | `govdoc/compare/context_loader.py` | 按 matchId 从拆分文件加载上下文 |
| CREATE | `govdoc/compare/concurrency.py` | 信号量并发控制 |
| MODIFY | `govdoc/compare/service.py:861-864` | 对比完成后调用 splitter 生成拆分文件 |
| MODIFY | `govdoc/api/routes/compare.py` | 新增 summary/context/retry 路由，创建任务走并发控制 |
| MODIFY | `govdoc/db/models.py:130-142` | CompareRun 无需改动（document_ids 已存在） |
| CREATE | `tests/unit/test_compare_splitter.py` | splitter 单元测试 |
| CREATE | `tests/unit/test_compare_context_loader.py` | context_loader 单元测试 |
| CREATE | `tests/unit/test_compare_concurrency.py` | 并发控制单元测试 |
| MODIFY | `frontend/src/api/compare.ts` | 新增 `getCompareSummary`、`getCompareContext`、`retryCompareRun` |
| MODIFY | `frontend/src/pages/DocCompareHubPage.tsx` | 行内进度 + 4 种状态操作 + 轮询刷新 |
| CREATE | `frontend/src/pages/DocCompareResultPage.tsx` | 全新结果页（摘要首屏 + 上下文视图） |
| MODIFY | `frontend/src/App.tsx` (或路由文件) | 结果页路由指向新组件 |

---

### Task 1: 后端 Schema — 新增分层响应模型

**Files:**
- Modify: `govdoc/schemas/compare.py`
- Test: `tests/unit/test_compare_schemas.py`

- [ ] **Step 1: 写测试 — 验证新 schema 可实例化**

```python
# tests/unit/test_compare_schemas.py
"""分层加载新增 schema 单元测试。"""
from govdoc.schemas.compare import (
    MatchSummaryItem,
    CompareSummaryResponse,
    FileContext,
    CompareContextResponse,
)


class TestMatchSummaryItem:
    def test_basic(self) -> None:
        item = MatchSummaryItem(
            id="p-001",
            category="paragraph",
            label="完全重复",
            color="#F59E0B",
            length=100,
            file_indices=[0, 1],
            occurrence_count=2,
            preview="本工程位于...",
        )
        assert item.id == "p-001"
        assert item.preview == "本工程位于..."

    def test_camel_alias(self) -> None:
        item = MatchSummaryItem(
            id="p-001", category="paragraph", label="x", color="#000",
            length=1, file_indices=[0], occurrence_count=1, preview="x",
        )
        dumped = item.model_dump(mode="json", by_alias=True)
        assert "fileIndices" in dumped
        assert "occurrenceCount" in dumped


class TestCompareSummaryResponse:
    def test_basic(self) -> None:
        from govdoc.schemas.compare import CompareSummary, CompareCategory, CompareDownloads, CompareArtifacts
        resp = CompareSummaryResponse(
            review_id="abc",
            summary=CompareSummary(
                file_count=2, files=[], common_paragraph_count=0,
                common_sentence_count=0, common_segment_count=0,
                match_count=0, min_segment_length=16,
            ),
            matches=[],
            categories=[],
            downloads=CompareDownloads(files={}),
            artifacts=CompareArtifacts(review_dir="/tmp", download_names={}),
        )
        assert resp.review_id == "abc"


class TestCompareContextResponse:
    def test_basic(self) -> None:
        from govdoc.schemas.compare import CompareDocumentBlock
        ctx = CompareContextResponse(
            match=MatchSummaryItem(
                id="p-001", category="paragraph", label="x", color="#000",
                length=1, file_indices=[0], occurrence_count=1, preview="x",
                text="full text",
            ),
            file_contexts=[
                FileContext(
                    file_index=0, name="test.pdf", total_blocks=100,
                    match_block_index=50, blocks=[],
                )
            ],
        )
        assert ctx.match.text == "full text"
        assert ctx.file_contexts[0].match_block_index == 50
```

- [ ] **Step 2: 运行测试确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_schemas.py -v`
Expected: ImportError（`MatchSummaryItem` 不存在）

- [ ] **Step 3: 实现新 schema**

在 `govdoc/schemas/compare.py` 末尾添加：

```python
class MatchSummaryItem(CompareModel):
    """摘要中的匹配项（无完整 text，只有 preview）。"""

    id: str
    category: CompareCategoryId
    label: str
    color: str
    length: int
    file_indices: list[int]
    occurrence_count: int
    preview: str
    text: str | None = None
    similarity: float | None = None


class CompareSummaryResponse(CompareModel):
    """分层加载摘要响应（不含 documents）。"""

    review_id: str
    summary: CompareSummary
    matches: list[MatchSummaryItem]
    categories: list[CompareCategory]
    downloads: CompareDownloads
    artifacts: CompareArtifacts


class FileContext(CompareModel):
    """单个文件的匹配上下文。"""

    file_index: int
    name: str
    total_blocks: int
    match_block_index: int
    blocks: list[CompareDocumentBlock]


class CompareContextResponse(CompareModel):
    """按需加载的匹配上下文响应。"""

    match: MatchSummaryItem
    file_contexts: list[FileContext]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_schemas.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add govdoc/schemas/compare.py tests/unit/test_compare_schemas.py
git commit -m "feat(compare): 新增分层加载 schema — MatchSummaryItem / CompareSummaryResponse / CompareContextResponse"
```

---

### Task 2: 后端 — 存储拆分器 (splitter)

**Files:**
- Create: `govdoc/compare/splitter.py`
- Test: `tests/unit/test_compare_splitter.py`

- [ ] **Step 1: 写测试**

```python
# tests/unit/test_compare_splitter.py
"""splitter 单元测试：验证 CompareResponse 拆分为多文件。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from govdoc.compare.splitter import split_compare_response
from govdoc.schemas.compare import (
    CompareArtifacts,
    CompareBlockSegment,
    CompareCategory,
    CompareDocumentBlock,
    CompareDocument,
    CompareDocuments,
    CompareDownloads,
    CompareMatch,
    CompareOccurrence,
    CompareOccurrenceSegment,
    CompareResponse,
    CompareSummary,
    CompareFileMeta,
)


def _make_block(index: int, text: str) -> CompareDocumentBlock:
    return CompareDocumentBlock(
        id=f"b-{index}", index=index, text=text,
        segments=[CompareBlockSegment(text=text, match_ids=[], categories=[])],
    )


def _make_response() -> CompareResponse:
    blocks_0 = [_make_block(i, f"文件0段落{i}") for i in range(5)]
    blocks_1 = [_make_block(i, f"文件1段落{i}") for i in range(3)]
    return CompareResponse(
        review_id="test-review",
        summary=CompareSummary(
            file_count=2,
            files=[
                CompareFileMeta(file_index=0, name="a.pdf", suffix=".pdf", paragraph_count=5, block_count=5),
                CompareFileMeta(file_index=1, name="b.pdf", suffix=".pdf", paragraph_count=3, block_count=3),
            ],
            common_paragraph_count=1, common_sentence_count=0,
            common_segment_count=0, match_count=1, min_segment_length=16,
        ),
        documents=CompareDocuments(files=[
            CompareDocument(file_index=0, name="a.pdf", suffix=".pdf", block_count=5, blocks=blocks_0),
            CompareDocument(file_index=1, name="b.pdf", suffix=".pdf", block_count=3, blocks=blocks_1),
        ]),
        matches=[
            CompareMatch(
                id="p-001", category="paragraph", label="完全重复", color="#F59E0B",
                text="这是一段很长的重复文本内容" * 10, length=100,
                file_indices=[0, 1],
                occurrences={
                    "0": [CompareOccurrence(file_index=0, start=0, end=100, segments=[
                        CompareOccurrenceSegment(file_index=0, block_id="b-2", block_index=2, start=0, end=100),
                    ])],
                    "1": [CompareOccurrence(file_index=1, start=0, end=100, segments=[
                        CompareOccurrenceSegment(file_index=1, block_id="b-1", block_index=1, start=0, end=100),
                    ])],
                },
                per_file_counts={"0": 1, "1": 1}, file_count=2, occurrence_count=2,
            ),
        ],
        categories=[CompareCategory(id="paragraph", label="完全重复", color="#F59E0B")],
        downloads=CompareDownloads(files={}),
        artifacts=CompareArtifacts(review_dir="/tmp/test", download_names={}),
    )


class TestSplitCompareResponse:
    def test_generates_summary_json(self, tmp_path: Path) -> None:
        resp = _make_response()
        split_compare_response(resp, tmp_path)
        summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        assert summary["reviewId"] == "test-review"
        assert len(summary["matches"]) == 1
        assert "preview" in summary["matches"][0]
        assert len(summary["matches"][0]["preview"]) <= 150

    def test_generates_blocks_files(self, tmp_path: Path) -> None:
        resp = _make_response()
        split_compare_response(resp, tmp_path)
        b0 = json.loads((tmp_path / "blocks_0.json").read_text(encoding="utf-8"))
        b1 = json.loads((tmp_path / "blocks_1.json").read_text(encoding="utf-8"))
        assert len(b0) == 5
        assert len(b1) == 3

    def test_generates_match_index(self, tmp_path: Path) -> None:
        resp = _make_response()
        split_compare_response(resp, tmp_path)
        idx = json.loads((tmp_path / "match_index.json").read_text(encoding="utf-8"))
        assert "p-001" in idx
        assert idx["p-001"]["0"]["blockIndices"] == [2]
        assert idx["p-001"]["1"]["blockIndices"] == [1]

    def test_summary_matches_no_full_text(self, tmp_path: Path) -> None:
        resp = _make_response()
        split_compare_response(resp, tmp_path)
        summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
        match = summary["matches"][0]
        assert "text" not in match or match.get("text") is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_splitter.py -v`
Expected: ImportError

- [ ] **Step 3: 实现 splitter**

```python
# govdoc/compare/splitter.py
"""对比结果拆分器：将 CompareResponse 拆分为多个索引文件。"""
from __future__ import annotations

import json
from pathlib import Path

from govdoc.schemas.compare import CompareResponse

PREVIEW_MAX_LENGTH = 100


def split_compare_response(response: CompareResponse, review_dir: Path) -> None:
    """将完整对比响应拆分为 summary.json + blocks_{N}.json + match_index.json。"""
    _write_summary(response, review_dir)
    _write_blocks(response, review_dir)
    _write_match_index(response, review_dir)


def _write_summary(response: CompareResponse, review_dir: Path) -> None:
    """生成 summary.json：摘要 + 匹配列表（仅 preview，无 text）。"""
    match_items = []
    for m in response.matches:
        match_items.append({
            "id": m.id,
            "category": m.category,
            "label": m.label,
            "color": m.color,
            "length": m.length,
            "fileIndices": m.file_indices,
            "occurrenceCount": m.occurrence_count,
            "preview": m.text[:PREVIEW_MAX_LENGTH] if m.text else "",
            "similarity": m.similarity,
        })

    summary_payload = {
        "reviewId": response.review_id,
        "summary": response.summary.model_dump(mode="json", by_alias=True),
        "matches": match_items,
        "categories": [c.model_dump(mode="json", by_alias=True) for c in response.categories],
        "downloads": response.downloads.model_dump(mode="json", by_alias=True),
        "artifacts": response.artifacts.model_dump(mode="json", by_alias=True),
    }
    (review_dir / "summary.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False), encoding="utf-8",
    )


def _write_blocks(response: CompareResponse, review_dir: Path) -> None:
    """生成 blocks_{fileIndex}.json：每个文件的段落块独立存储。"""
    for doc in response.documents.files:
        blocks_data = [b.model_dump(mode="json", by_alias=True) for b in doc.blocks]
        (review_dir / f"blocks_{doc.file_index}.json").write_text(
            json.dumps(blocks_data, ensure_ascii=False), encoding="utf-8",
        )


def _write_match_index(response: CompareResponse, review_dir: Path) -> None:
    """生成 match_index.json：matchId → 各文件的 blockIndex 映射。"""
    index: dict[str, dict[str, dict]] = {}
    for m in response.matches:
        entry: dict[str, dict] = {}
        for file_idx_str, occurrences in m.occurrences.items():
            block_indices = []
            for occ in occurrences:
                for seg in occ.segments:
                    if seg.block_index not in block_indices:
                        block_indices.append(seg.block_index)
            entry[file_idx_str] = {"blockIndices": sorted(block_indices)}
        index[m.id] = entry

    (review_dir / "match_index.json").write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8",
    )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_splitter.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add govdoc/compare/splitter.py tests/unit/test_compare_splitter.py
git commit -m "feat(compare): 实现存储拆分器 — summary.json + blocks + match_index"
```

---

### Task 3: 后端 — 上下文加载器 (context_loader)

**Files:**
- Create: `govdoc/compare/context_loader.py`
- Test: `tests/unit/test_compare_context_loader.py`

- [ ] **Step 1: 写测试**

```python
# tests/unit/test_compare_context_loader.py
"""context_loader 单元测试。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from govdoc.compare.context_loader import load_match_context


@pytest.fixture()
def review_dir(tmp_path: Path) -> Path:
    """构造带拆分文件的 review 目录。"""
    blocks_0 = [
        {"id": f"b-{i}", "index": i, "text": f"段落{i}", "segments": [{"text": f"段落{i}", "matchIds": [], "categories": []}]}
        for i in range(10)
    ]
    blocks_1 = [
        {"id": f"b-{i}", "index": i, "text": f"文件1段落{i}", "segments": [{"text": f"文件1段落{i}", "matchIds": [], "categories": []}]}
        for i in range(8)
    ]
    (tmp_path / "blocks_0.json").write_text(json.dumps(blocks_0, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "blocks_1.json").write_text(json.dumps(blocks_1, ensure_ascii=False), encoding="utf-8")

    match_index = {
        "p-001": {
            "0": {"blockIndices": [5]},
            "1": {"blockIndices": [3]},
        },
    }
    (tmp_path / "match_index.json").write_text(json.dumps(match_index), encoding="utf-8")

    summary = {
        "reviewId": "test",
        "summary": {"fileCount": 2, "files": [
            {"fileIndex": 0, "name": "a.pdf", "suffix": ".pdf", "paragraphCount": 10, "blockCount": 10},
            {"fileIndex": 1, "name": "b.pdf", "suffix": ".pdf", "paragraphCount": 8, "blockCount": 8},
        ], "commonParagraphCount": 1, "commonSentenceCount": 0, "commonSegmentCount": 0, "matchCount": 1, "minSegmentLength": 16},
        "matches": [
            {"id": "p-001", "category": "paragraph", "label": "完全重复", "color": "#F59E0B",
             "length": 50, "fileIndices": [0, 1], "occurrenceCount": 2, "preview": "段落5"},
        ],
        "categories": [], "downloads": {"files": {}}, "artifacts": {"reviewDir": str(tmp_path), "downloadNames": {}},
    }
    (tmp_path / "summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    return tmp_path


class TestLoadMatchContext:
    def test_returns_correct_file_contexts(self, review_dir: Path) -> None:
        result = load_match_context(review_dir, "p-001", surrounding=2)
        assert result["match"]["id"] == "p-001"
        assert len(result["fileContexts"]) == 2

    def test_surrounding_blocks(self, review_dir: Path) -> None:
        result = load_match_context(review_dir, "p-001", surrounding=2)
        ctx0 = result["fileContexts"][0]
        assert ctx0["fileIndex"] == 0
        assert ctx0["matchBlockIndex"] == 5
        indices = [b["index"] for b in ctx0["blocks"]]
        assert indices == [3, 4, 5, 6, 7]

    def test_clamps_at_boundaries(self, review_dir: Path) -> None:
        result = load_match_context(review_dir, "p-001", surrounding=5)
        ctx1 = result["fileContexts"][1]
        indices = [b["index"] for b in ctx1["blocks"]]
        assert indices[0] == 0
        assert indices[-1] == 7

    def test_unknown_match_raises(self, review_dir: Path) -> None:
        with pytest.raises(KeyError):
            load_match_context(review_dir, "nonexistent", surrounding=2)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_context_loader.py -v`
Expected: ImportError

- [ ] **Step 3: 实现 context_loader**

```python
# govdoc/compare/context_loader.py
"""按需加载匹配上下文：从拆分文件中读取指定 match 涉及的段落。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_match_context(
    review_dir: Path,
    match_id: str,
    surrounding: int = 3,
) -> dict[str, Any]:
    """加载指定 matchId 的上下文。

    Returns:
        包含 match 信息和各文件上下文 blocks 的字典。
    """
    match_index = json.loads((review_dir / "match_index.json").read_text(encoding="utf-8"))
    summary_data = json.loads((review_dir / "summary.json").read_text(encoding="utf-8"))

    if match_id not in match_index:
        raise KeyError(f"matchId 不存在: {match_id}")

    match_entry = match_index[match_id]
    match_info = _find_match_in_summary(summary_data, match_id)

    file_metas = {f["fileIndex"]: f for f in summary_data["summary"]["files"]}
    file_contexts = []
    for file_idx_str, idx_data in match_entry.items():
        file_idx = int(file_idx_str)
        block_indices = idx_data["blockIndices"]
        if not block_indices:
            continue

        blocks_path = review_dir / f"blocks_{file_idx}.json"
        all_blocks = json.loads(blocks_path.read_text(encoding="utf-8"))
        total = len(all_blocks)

        primary_block = block_indices[0]
        start = max(0, primary_block - surrounding)
        end = min(total, primary_block + surrounding + 1)
        sliced_blocks = all_blocks[start:end]

        meta = file_metas.get(file_idx, {})
        file_contexts.append({
            "fileIndex": file_idx,
            "name": meta.get("name", f"file_{file_idx}"),
            "totalBlocks": total,
            "matchBlockIndex": primary_block,
            "blocks": sliced_blocks,
        })

    return {"match": match_info, "fileContexts": file_contexts}


def _find_match_in_summary(summary_data: dict, match_id: str) -> dict:
    """从 summary 的 matches 列表中找到指定 match。"""
    for m in summary_data.get("matches", []):
        if m["id"] == match_id:
            return m
    return {"id": match_id}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_context_loader.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add govdoc/compare/context_loader.py tests/unit/test_compare_context_loader.py
git commit -m "feat(compare): 实现上下文加载器 — 按 matchId 切片读取段落"
```

---

### Task 4: 后端 — 并发控制

**Files:**
- Create: `govdoc/compare/concurrency.py`
- Modify: `govdoc/config.py:82-91`
- Modify: `govdoc.yaml:34-38`
- Test: `tests/unit/test_compare_concurrency.py`

- [ ] **Step 1: 写测试**

```python
# tests/unit/test_compare_concurrency.py
"""并发控制单元测试。"""
from __future__ import annotations

import asyncio
import time

import pytest

from govdoc.compare.concurrency import get_compare_semaphore


class TestCompareSemaphore:
    def test_default_limit_is_1(self) -> None:
        sem = get_compare_semaphore(max_concurrent=1)
        assert isinstance(sem, asyncio.Semaphore)

    @pytest.mark.asyncio
    async def test_limits_concurrency(self) -> None:
        sem = get_compare_semaphore(max_concurrent=1)
        running = []

        async def task(task_id: int) -> None:
            async with sem:
                running.append(task_id)
                await asyncio.sleep(0.1)
                assert len(running) <= 1
                running.remove(task_id)

        await asyncio.gather(task(1), task(2), task(3))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_concurrency.py -v`
Expected: ImportError

- [ ] **Step 3: 实现并发控制 + 配置项**

```python
# govdoc/compare/concurrency.py
"""对比任务并发控制。"""
from __future__ import annotations

import asyncio
from functools import lru_cache


@lru_cache
def get_compare_semaphore(max_concurrent: int = 1) -> asyncio.Semaphore:
    """获取对比任务信号量（进程级单例）。"""
    return asyncio.Semaphore(max_concurrent)
```

在 `govdoc/config.py` 的 `CompareConfig` 中新增：

```python
    max_concurrent: int = 1
```

在 `govdoc.yaml` 的 `compare:` 下新增：

```yaml
  max_concurrent: 1
```

- [ ] **Step 4: 运行测试确认通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_concurrency.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add govdoc/compare/concurrency.py govdoc/config.py govdoc.yaml tests/unit/test_compare_concurrency.py
git commit -m "feat(compare): 新增并发控制 Semaphore + max_concurrent 配置项"
```

---

### Task 5: 后端 — 集成 splitter 到对比流程 + 新增 API 路由

**Files:**
- Modify: `govdoc/compare/service.py:861-865`
- Modify: `govdoc/api/routes/compare.py`

- [ ] **Step 1: 修改 service.py — 对比完成后调用 splitter**

在 `govdoc/compare/service.py` 的 `_build_compare_response` 函数中，在写入 `review.json` 之后添加：

```python
    from govdoc.compare.splitter import split_compare_response
    split_compare_response(payload, review_dir)
```

即在现有的 `(review_dir / "review.json").write_text(...)` 之后（约第 864 行后）插入一行调用。

- [ ] **Step 2: 修改 compare.py 路由 — 新增 summary/context/retry + 并发控制**

在 `govdoc/api/routes/compare.py` 中新增三个路由：

```python
@router.get("/{review_id}/summary")
def get_compare_summary(review_id: str) -> dict:
    """读取对比摘要（轻量版，不含文档全文）。"""
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        if run is None:
            raise HTTPException(status_code=404, detail="对比任务不存在。")
        if run.status != "completed":
            raise HTTPException(status_code=409, detail="对比任务尚未完成。")
        result_path = run.result_path

    if result_path is None:
        raise HTTPException(status_code=404, detail="对比结果不存在。")

    review_dir = Path(result_path).parent
    summary_path = review_dir / "summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="摘要文件不存在，请重新对比。")

    return json.loads(summary_path.read_text(encoding="utf-8"))


@router.get("/{review_id}/context")
def get_compare_context(review_id: str, matchId: str, surrounding: int = 3) -> dict:
    """按需加载指定匹配项的上下文段落。"""
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        if run is None:
            raise HTTPException(status_code=404, detail="对比任务不存在。")
        if run.status != "completed":
            raise HTTPException(status_code=409, detail="对比任务尚未完成。")
        result_path = run.result_path

    if result_path is None:
        raise HTTPException(status_code=404, detail="对比结果不存在。")

    review_dir = Path(result_path).parent
    from govdoc.compare.context_loader import load_match_context
    try:
        return load_match_context(review_dir, matchId, surrounding=surrounding)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="拆分文件缺失，请重新对比。") from exc


@router.post("/{review_id}/retry", status_code=202)
async def retry_compare_run(
    review_id: str,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """重试失败的对比任务（创建新任务）。"""
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        if run is None:
            raise HTTPException(status_code=404, detail="对比任务不存在。")
        if run.status != "failed":
            raise HTTPException(status_code=409, detail="仅失败任务可重试。")
        document_ids = json.loads(run.document_ids) if run.document_ids else []

    if len(document_ids) < 2:
        raise HTTPException(status_code=400, detail="原始文档信息丢失，无法重试。")

    with get_db_session() as session:
        docs = []
        for doc_id in document_ids:
            doc = session.get(Document, doc_id)
            if doc is None or doc.status != "ready":
                raise HTTPException(status_code=400, detail=f"文档 {doc_id} 不存在或未就绪。")
            docs.append(doc)

        file_names = [d.filename for d in docs]
        file_info_list = [(d.markdown_path or d.raw_path, d.filename) for d in docs]
        new_id = uid()
        new_run = CompareRun(
            id=new_id, status="pending", file_count=len(docs),
            file_names_json=json.dumps(file_names, ensure_ascii=False),
            document_ids=json.dumps(document_ids),
        )
        session.add(new_run)
        session.commit()

    background_tasks.add_task(_run_compare_from_docs, new_id, file_info_list)
    return {"reviewId": new_id, "status": "pending"}
```

修改 `_run_compare_from_docs` 加入并发控制：

```python
async def _run_compare_from_docs(
    review_id: str,
    file_info_list: list[tuple[str, str]],
) -> None:
    from govdoc.compare.concurrency import get_compare_semaphore
    from govdoc.runtime import get_config

    sem = get_compare_semaphore(get_config().compare.max_concurrent)
    async with sem:
        def _execute_compare() -> None:
            _set_compare_run_running(review_id)
            try:
                payload = create_compare_bundle(
                    files=[(Path(raw_path), filename) for raw_path, filename in file_info_list],
                    on_progress=lambda progress: _update_compare_progress(review_id, progress),
                )
            except (BadZipFile, ValueError) as exc:
                _set_compare_run_failed(review_id, f"文件解析失败: {exc}")
                return
            except (RuntimeError, OSError) as exc:
                _set_compare_run_failed(review_id, f"文档转换失败: {exc}")
                return
            except Exception:
                logger.exception("后台对比执行失败: %s", review_id)
                _set_compare_run_failed(review_id, "后台任务异常退出")
                return

            result_path = Path(payload.artifacts.review_dir) / "review.json"
            _set_compare_run_completed(review_id, str(result_path))

        await to_thread(_execute_compare)
```

- [ ] **Step 3: 运行全部后端测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v`
Expected: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add govdoc/compare/service.py govdoc/api/routes/compare.py
git commit -m "feat(compare): 集成 splitter + 新增 summary/context/retry API + 并发控制"
```

---

### Task 6: 前端 — API 层新增

**Files:**
- Modify: `frontend/src/api/compare.ts`

- [ ] **Step 1: 新增类型和函数**

在 `frontend/src/api/compare.ts` 中新增：

```typescript
// --- 分层加载类型 ---

export interface MatchSummaryItem {
  id: string;
  category: CompareCategoryId;
  label: string;
  color: string;
  length: number;
  fileIndices: number[];
  occurrenceCount: number;
  preview: string;
  similarity: number | null;
}

export interface CompareSummaryResponse {
  reviewId: string;
  summary: CompareSummary;
  matches: MatchSummaryItem[];
  categories: CompareCategory[];
  downloads: { files: Record<string, string> };
  artifacts: { reviewDir: string; downloadNames: Record<string, string> };
}

export interface FileContext {
  fileIndex: number;
  name: string;
  totalBlocks: number;
  matchBlockIndex: number;
  blocks: CompareDocumentBlock[];
}

export interface CompareContextResponse {
  match: MatchSummaryItem & { text?: string };
  fileContexts: FileContext[];
}

// --- 分层加载 API ---

export function getCompareSummary(reviewId: string): Promise<CompareSummaryResponse> {
  return request(`/api/v1/compare/${reviewId}/summary`);
}

export function getCompareContext(
  reviewId: string,
  matchId: string,
  surrounding = 3,
): Promise<CompareContextResponse> {
  return request(`/api/v1/compare/${reviewId}/context?matchId=${encodeURIComponent(matchId)}&surrounding=${surrounding}`);
}

export function retryCompareRun(reviewId: string): Promise<CompareSubmitResponse> {
  return request(`/api/v1/compare/${reviewId}/retry`, { method: "POST" });
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/api/compare.ts
git commit -m "feat(compare): 前端 API 层新增 summary/context/retry 函数"
```

---

### Task 7: 前端 — 入口页重构（行内进度 + 4 状态 + 重试 + 轮询）

**Files:**
- Modify: `frontend/src/pages/DocCompareHubPage.tsx`

- [ ] **Step 1: 重构入口页**

重写 `DocCompareHubPage.tsx`，关键变更：

1. **状态区分**：已完成（查看）、进行中（无按钮）、失败（重试）、排队中（无按钮）
2. **行内进度**：进行中的行展开 6 步进度条，蓝色左边框 + 浅蓝底
3. **重试**：失败行点击"重试"调用 `retryCompareRun`，刷新列表
4. **轮询**：有进行中任务时每 3 秒轮询 `listCompareRuns` 刷新状态
5. **提交后不跳转**：提交对比后留在入口页，列表自动刷新显示新任务

变更的关键函数/组件：

```typescript
// 状态标签——区分"进行中"和"排队中"
function statusLabel(status: string): string {
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  if (status === "running") return "进行中";
  if (status === "pending") return "排队中";
  return "未知";
}

// 状态样式
function statusBadgeClass(status: string): string {
  if (status === "completed") return "bg-green-50 text-[#16A34A]";
  if (status === "failed") return "bg-red-50 text-[#DC2626]";
  if (status === "running") return "bg-blue-50 text-[#3B82F6]";
  if (status === "pending") return "bg-gray-50 text-text-muted";
  return "bg-gray-50 text-text-muted";
}
```

在历史表格的 `runs.map(...)` 中，每行根据 status 渲染：
- 操作列：completed → `<Link>查看</Link>`，failed → `<Button onClick={handleRetry}>重试</Button>`，其他 → 空
- 进行中行：外层 div 加 `border-l-4 border-[#3B82F6] bg-[#F0F9FF]`，下方展示 `<ProgressSteps>`
- 提交后：`handleSubmit` 不再 `navigate()`，改为刷新列表 `refreshRuns()`

轮询逻辑：

```typescript
useEffect(() => {
  const hasRunning = runs.some((r) => r.status === "running" || r.status === "pending");
  if (!hasRunning) return;
  const timer = setInterval(() => {
    listCompareRuns().then(setRuns).catch(() => {});
  }, 3000);
  return () => clearInterval(timer);
}, [runs]);
```

进度条组件（行内使用）：

```typescript
const PROGRESS_STEPS = ["上传文件", "文档转换", "段落匹配", "句子匹配", "近似检测", "生成结果"];

function InlineProgress({ run }: { run: CompareRunStatus }) {
  const stepIndex = progressIndex(run);
  return (
    <div className="flex items-center gap-4 px-4 py-2">
      {PROGRESS_STEPS.map((step, i) => (
        <div key={step} className="flex items-center gap-1.5">
          {i < stepIndex ? (
            <CircleCheck className="h-3.5 w-3.5 text-[#16A34A]" />
          ) : i === stepIndex ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-[#3B82F6]" />
          ) : (
            <Circle className="h-3.5 w-3.5 text-gray-300" />
          )}
          <span className={cn("text-xs", i < stepIndex && "text-[#16A34A]", i === stepIndex && "font-medium text-[#3B82F6]", i > stepIndex && "text-text-muted")}>
            {step}
          </span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: 本地启动前端验证**

Run: `cd frontend && npx vite --host 0.0.0.0 --port 5173`
手动验证：入口页显示历史表格，各状态行样式正确，进行中行展示进度条。

- [ ] **Step 3: 提交**

```bash
git add frontend/src/pages/DocCompareHubPage.tsx
git commit -m "feat(compare): 入口页重构 — 行内进度 + 4 种状态 + 重试 + 轮询"
```

---

### Task 8: 前端 — 结果页（摘要首屏 + 上下文视图）

**Files:**
- Create: `frontend/src/pages/DocCompareResultPage.tsx`
- Modify: 路由配置（将 `/compare/:id` 指向新页面）

- [ ] **Step 1: 创建新结果页**

创建 `frontend/src/pages/DocCompareResultPage.tsx`，包含两个视图模式：

**A. SummaryView（未选中匹配时）**：
- 调用 `getCompareSummary(reviewId)` 加载数据
- 渲染：统计卡片 + 筛选按钮 + 匹配表格
- 表格列：类型（badge）| 匹配内容（preview）| 涉及文件 | 出现次数
- 表格行可点击，点击后设置 `selectedMatchId`

**B. ContextView（选中匹配后）**：
- 调用 `getCompareContext(reviewId, matchId)` 加载上下文
- 布局：左侧匹配清单侧栏（300px）+ 右侧多文件段落对照
- 匹配清单使用 summary 中的 matches 数据渲染
- 右侧每个 fileContext 一列，渲染 blocks 并高亮 matchBlockIndex 对应的段落
- 每列标题："文件 N · 文件名"，副标题："第 X 段 / 共 Y 段"
- 返回按钮回到 SummaryView（清除 selectedMatchId）

关键状态管理：

```typescript
export function DocCompareResultPage() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const [summary, setSummary] = useState<CompareSummaryResponse | null>(null);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);
  const [context, setContext] = useState<CompareContextResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [contextLoading, setContextLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载 summary
  useEffect(() => {
    if (!reviewId) return;
    setLoading(true);
    getCompareSummary(reviewId)
      .then(setSummary)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [reviewId]);

  // 选中 match 时加载 context
  useEffect(() => {
    if (!reviewId || !selectedMatchId) { setContext(null); return; }
    setContextLoading(true);
    getCompareContext(reviewId, selectedMatchId)
      .then(setContext)
      .catch((e) => setError(e.message))
      .finally(() => setContextLoading(false));
  }, [reviewId, selectedMatchId]);

  if (loading) return <LoadingView />;
  if (error) return <ErrorView error={error} />;
  if (!summary) return null;

  return selectedMatchId && context ? (
    <ContextView
      summary={summary}
      context={context}
      selectedMatchId={selectedMatchId}
      onSelect={setSelectedMatchId}
      onBack={() => setSelectedMatchId(null)}
      loading={contextLoading}
    />
  ) : (
    <SummaryView summary={summary} onSelectMatch={setSelectedMatchId} />
  );
}
```

- [ ] **Step 2: 更新路由**

在路由配置中将 `/compare/:reviewId` 的组件从 `DocCompareDetailPage` 改为 `DocCompareResultPage`。同时保留旧组件文件不删除（渐进迁移）。

找到路由配置文件（通常为 `App.tsx` 或 `router.tsx`），修改 import 和 Route 组件。

- [ ] **Step 3: 本地启动前端验证**

Run: `cd frontend && npx vite --host 0.0.0.0 --port 5173`

验证：
1. 打开一个已完成的对比结果 → 显示统计卡片 + 匹配表格（秒开）
2. 点击某条匹配 → 切换到上下文视图，显示涉及文件的段落
3. 点击另一条匹配 → 右侧刷新为新的上下文
4. 点返回 → 回到匹配表格

- [ ] **Step 4: 提交**

```bash
git add frontend/src/pages/DocCompareResultPage.tsx frontend/src/App.tsx
git commit -m "feat(compare): 新结果页 — 摘要首屏 + 按需加载上下文视图"
```

---

### Task 9: 集成测试 + 部署验证

**Files:**
- 无新文件

- [ ] **Step 1: 后端全量测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v`
Expected: 全部 PASS

- [ ] **Step 2: 前端构建检查**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: 无编译错误，构建成功

- [ ] **Step 3: 提交所有变更并部署 testing**

```bash
git add -A
git commit -m "feat(compare): 文档对比分层加载完整实现"
bash scripts/deploy.sh --target testing
```

- [ ] **Step 4: 在 testing 环境验证**

1. 访问 `http://175.178.131.134:8080/compare`
2. 提交一个 2 文件对比 → 入口页行内显示进度
3. 完成后点击"查看" → 结果页秒开
4. 点击匹配项 → 上下文视图正确展示
5. 大文件（3 份投标文件）对比完成后验证结果页不崩溃

- [ ] **Step 5: 部署 stable**

```bash
bash scripts/deploy.sh --target stable
```
