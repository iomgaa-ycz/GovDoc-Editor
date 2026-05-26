---
type: plan
node_id: plan:2026-05-24-checkpoint-title-dedup-plan
title: 审核点按标题去重实施计划
date: 2026-05-24
---

# Checkpoint Title Dedup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 手动导入审核点时，按 `GovCheckpoint.title.strip()` 去重，导入前清理旧库重复，导入时跳过与旧库重复的新记录。

**Architecture:** 保持 MVP，不新增 API、不新增 DB 唯一索引、不改解析器随机 ID 策略。去重逻辑集中在现有 `govdoc/api/routes/checkpoints.py` 的私有 helper 中，由 `POST /api/v1/checkpoints/import` 在同一 DB session 内触发；后端单测覆盖引用迁移，前端 E2E 覆盖重复导入用户流程。

**Tech Stack:** Python 3.11 / FastAPI / SQLModel / SQLite / Pydantic v2 / Vite React / `@playwright/cli`

**Design Spec:** `research-wiki/designs/checkpoint-title-dedup-design.md`

---

## File Structure

| 文件 | 操作 | 职责 |
|---|---|---|
| `tests/unit/test_checkpoints_route.py` | MODIFY | 新增后端失败测试：重复导入、单文件重复 title、旧库内部去重、引用迁移 |
| `govdoc/api/routes/checkpoints.py` | MODIFY | 新增 title 去重 helper，并在现有 import endpoint 中调用 |
| `frontend/e2e/test-02-import-checkpoints.js` | MODIFY | 追加重复导入同一 XLS 的 UI 回归检查 |

不新增迁移文件，不新增端点，不新增 `govdoc/checkpoints/` 包。旧库内部去重在导入事务内完成。

## Task 1: Backend Failing Tests

**Files:**
- Modify: `tests/unit/test_checkpoints_route.py`

- [ ] **Step 1: Add imports for JSON, timestamps, and referenced DB models**

在 `tests/unit/test_checkpoints_route.py` 顶部 import 区改成：

```python
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.api.routes.checkpoints import router
from govdoc.db.models import AuditPointRun, AuditRun, CheckpointFinal, Project, TenderDoc
```

- [ ] **Step 2: Add payload and audit-run test helpers**

在 `seed_checkpoint()` fixture 后追加：

```python
def _checkpoint_payload(title: str, description: str = "有效表现形式") -> str:
    """构造最小合法 GovCheckpoint JSON。"""
    return json.dumps(
        {
            "id": uuid.uuid4().hex,
            "category": "其他违法违规",
            "title": title,
            "description": description,
            "legal_basis": [],
            "severity": "major",
            "retrieval_hint": description[:80],
        },
        ensure_ascii=False,
    )


def _csv_with_rows(rows: list[tuple[str, str]]) -> bytes:
    """构造审核点导入 CSV，rows 为 (title, description)。"""
    body = "大类,违法违规问题,表现形式,处理依据,处罚依据,处理建议,责任主体\n"
    for title, description in rows:
        body += f"一、限制条款,{title},{description},法条,,建议,主体\n"
    return body.encode("utf-8")


def _seed_project_and_tender(session: Session) -> tuple[Project, TenderDoc]:
    """创建 AuditRun 外键依赖的项目和文书。"""
    project = Project(name="去重测试项目", created_by="tester")
    session.add(project)
    session.flush()
    tender = TenderDoc(
        project_id=project.id,
        filename="tender.docx",
        storage_path="/tmp/tender.docx",
        markdown_path="/tmp/tender.md",
        qmd_collection="test_collection",
        uploaded_by="tester",
    )
    session.add(tender)
    session.flush()
    return project, tender
```

- [ ] **Step 3: Add duplicate import tests**

在 `class TestImportCheckpoints:` 的现有测试后追加：

```python
    def test_reimport_same_title_skips_new_checkpoint(self, client, engine):
        """重复导入同一 title 时，第二次不应新增 CheckpointFinal。"""
        csv_content = _csv_with_rows([("1.重复标题", "设置供应商注册地限制")])

        first = client.post(
            "/api/v1/checkpoints/import",
            files={"file": ("checkpoints.csv", csv_content, "text/csv")},
        )
        second = client.post(
            "/api/v1/checkpoints/import",
            files={"file": ("checkpoints.csv", csv_content, "text/csv")},
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["imported_count"] == 1
        assert second.json()["imported_count"] == 0
        assert second.json()["skipped_count"] == 1
        assert "审核点标题已存在" in second.json()["skipped_reasons"][0]

        with Session(engine) as session:
            finals = session.exec(select(CheckpointFinal)).all()
        assert len(finals) == 1

    def test_import_file_with_duplicate_titles_keeps_first_new_row(self, client, engine):
        """同一文件内 title 重复时，只导入先出现的记录。"""
        csv_content = _csv_with_rows(
            [
                ("1.重复标题", "第一条表现形式"),
                ("1.重复标题", "第二条表现形式"),
            ]
        )

        resp = client.post(
            "/api/v1/checkpoints/import",
            files={"file": ("checkpoints.csv", csv_content, "text/csv")},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["imported_count"] == 1
        assert body["skipped_count"] == 1
        assert "审核点标题已存在" in body["skipped_reasons"][0]

        with Session(engine) as session:
            finals = session.exec(select(CheckpointFinal)).all()
        assert len(finals) == 1
        assert "第一条表现形式" in finals[0].payload_json
```

- [ ] **Step 4: Add existing-table dedup tests**

继续在 `class TestImportCheckpoints:` 中追加：

```python
    def test_existing_duplicates_keep_newer_checkpoint(self, client, engine):
        """导入前清理旧库重复 title，并保留 approved_at 最新的记录。"""
        older_time = datetime(2026, 1, 1, 10, 0, 0)
        newer_time = older_time + timedelta(hours=1)

        with Session(engine) as session:
            older = CheckpointFinal(
                payload_json=_checkpoint_payload("旧库重复标题", "旧记录"),
                approved_by="tester",
                approved_at=older_time,
            )
            newer = CheckpointFinal(
                payload_json=_checkpoint_payload("旧库重复标题", "新记录"),
                approved_by="tester",
                approved_at=newer_time,
            )
            session.add(older)
            session.add(newer)
            session.commit()
            older_id = older.id
            newer_id = newer.id

        csv_content = _csv_with_rows([("2.新标题", "新导入记录")])
        resp = client.post(
            "/api/v1/checkpoints/import",
            files={"file": ("checkpoints.csv", csv_content, "text/csv")},
        )

        assert resp.status_code == 200
        assert resp.json()["imported_count"] == 1
        with Session(engine) as session:
            assert session.get(CheckpointFinal, older_id) is None
            assert session.get(CheckpointFinal, newer_id) is not None
            finals = session.exec(select(CheckpointFinal)).all()
        assert len(finals) == 2

    def test_existing_duplicate_rewires_audit_point_runs(self, client, engine):
        """删除旧库重复记录前，应迁移 AuditPointRun.checkpoint_final_id。"""
        older_time = datetime(2026, 1, 1, 10, 0, 0)
        newer_time = older_time + timedelta(hours=1)

        with Session(engine) as session:
            project, tender = _seed_project_and_tender(session)
            older = CheckpointFinal(
                payload_json=_checkpoint_payload("引用重复标题", "旧记录"),
                approved_by="tester",
                approved_at=older_time,
            )
            newer = CheckpointFinal(
                payload_json=_checkpoint_payload("引用重复标题", "新记录"),
                approved_by="tester",
                approved_at=newer_time,
            )
            session.add(older)
            session.add(newer)
            session.flush()
            audit_run = AuditRun(
                project_id=project.id,
                tender_doc_id=tender.id,
                checkpoint_final_ids=json.dumps([older.id], ensure_ascii=False),
            )
            session.add(audit_run)
            session.flush()
            point_run = AuditPointRun(
                audit_run_id=audit_run.id,
                checkpoint_final_id=older.id,
            )
            session.add(point_run)
            session.commit()
            point_run_id = point_run.id
            older_id = older.id
            newer_id = newer.id

        csv_content = _csv_with_rows([("3.新标题", "新导入记录")])
        resp = client.post(
            "/api/v1/checkpoints/import",
            files={"file": ("checkpoints.csv", csv_content, "text/csv")},
        )

        assert resp.status_code == 200
        with Session(engine) as session:
            assert session.get(CheckpointFinal, older_id) is None
            point_run = session.get(AuditPointRun, point_run_id)
        assert point_run is not None
        assert point_run.checkpoint_final_id == newer_id
```

- [ ] **Step 5: Add AuditRun JSON reference test**

继续在 `class TestImportCheckpoints:` 中追加：

```python
    def test_existing_duplicate_rewires_audit_run_checkpoint_ids(self, client, engine):
        """删除旧库重复记录前，应替换 AuditRun.checkpoint_final_ids 并去重保序。"""
        older_time = datetime(2026, 1, 1, 10, 0, 0)
        newer_time = older_time + timedelta(hours=1)

        with Session(engine) as session:
            project, tender = _seed_project_and_tender(session)
            older = CheckpointFinal(
                payload_json=_checkpoint_payload("列表重复标题", "旧记录"),
                approved_by="tester",
                approved_at=older_time,
            )
            newer = CheckpointFinal(
                payload_json=_checkpoint_payload("列表重复标题", "新记录"),
                approved_by="tester",
                approved_at=newer_time,
            )
            stable = CheckpointFinal(
                payload_json=_checkpoint_payload("稳定标题", "稳定记录"),
                approved_by="tester",
                approved_at=newer_time,
            )
            session.add(older)
            session.add(newer)
            session.add(stable)
            session.flush()
            audit_run = AuditRun(
                project_id=project.id,
                tender_doc_id=tender.id,
                checkpoint_final_ids=json.dumps(
                    [older.id, newer.id, older.id, stable.id],
                    ensure_ascii=False,
                ),
            )
            session.add(audit_run)
            session.commit()
            audit_run_id = audit_run.id
            older_id = older.id
            newer_id = newer.id
            stable_id = stable.id

        csv_content = _csv_with_rows([("4.新标题", "新导入记录")])
        resp = client.post(
            "/api/v1/checkpoints/import",
            files={"file": ("checkpoints.csv", csv_content, "text/csv")},
        )

        assert resp.status_code == 200
        with Session(engine) as session:
            assert session.get(CheckpointFinal, older_id) is None
            audit_run = session.get(AuditRun, audit_run_id)
        assert audit_run is not None
        assert json.loads(audit_run.checkpoint_final_ids) == [newer_id, stable_id]
```

- [ ] **Step 6: Run tests and verify they fail**

运行：

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoints_route.py -v
```

预期：

- 新增测试失败。
- 典型失败为第二次导入仍 `imported_count == 1`，或旧库重复记录未删除。

- [ ] **Step 7: Commit failing tests**

```bash
git add tests/unit/test_checkpoints_route.py
git commit -m "test: add checkpoint title dedup coverage"
```

## Task 2: Backend Dedup Implementation

**Files:**
- Modify: `govdoc/api/routes/checkpoints.py`
- Test: `tests/unit/test_checkpoints_route.py`

- [ ] **Step 1: Add backend imports**

把 `govdoc/api/routes/checkpoints.py` 顶部 import 改成：

```python
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import ValidationError
from sqlmodel import Session, select

from govdoc.api.deps import get_db_session
from govdoc.api.middleware import log_activity
from govdoc.api.schemas import UpdateCheckpointRequest
from govdoc.db.models import AuditPointRun, AuditRun, CheckpointFinal
from govdoc.schemas import GovCheckpoint
```

- [ ] **Step 2: Add dedup types and title helper**

在 `_ALLOWED_EXTENSIONS` 之后追加：

```python
class CheckpointDedupError(RuntimeError):
    """审核点去重失败。"""


@dataclass(slots=True)
class DedupStats:
    """审核点去重诊断信息。

    Attributes:
        removed_existing_count: 删除的旧库重复审核点数量。
        rewired_audit_point_runs: 被迁移的 AuditPointRun 数量。
        rewired_audit_runs: 被迁移的 AuditRun 数量。
    """

    removed_existing_count: int = 0
    rewired_audit_point_runs: int = 0
    rewired_audit_runs: int = 0


def _checkpoint_title_key(payload_json: str) -> str | None:
    """从 CheckpointFinal.payload_json 提取 title 去重键。

    Args:
        payload_json: CheckpointFinal.payload_json 原始 JSON 字符串。

    Returns:
        去除首尾空白后的 title；payload 非法或 title 为空时返回 None。
    """
    try:
        checkpoint = GovCheckpoint.model_validate_json(payload_json)
    except ValidationError:
        return None

    title = checkpoint.title.strip()
    return title or None
```

- [ ] **Step 3: Add reference rewiring helper**

继续追加：

```python
def _dedupe_ids_preserving_order(ids: list[str]) -> list[str]:
    """对 ID 列表去重并保持第一次出现顺序。"""
    seen: set[str] = set()
    result: list[str] = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _rewire_checkpoint_references(
    session: Session,
    replacement_map: dict[str, str],
) -> tuple[int, int]:
    """把被删除审核点的引用迁移到保留审核点。

    Args:
        session: 当前数据库 session，调用方负责 commit/rollback。
        replacement_map: old_checkpoint_id -> keep_checkpoint_id。

    Returns:
        (rewired_audit_point_runs, rewired_audit_runs)。

    Raises:
        CheckpointDedupError: AuditRun.checkpoint_final_ids 不是合法 JSON list[str]。
    """
    if not replacement_map:
        return 0, 0

    old_ids = list(replacement_map)
    point_runs = session.exec(
        select(AuditPointRun).where(AuditPointRun.checkpoint_final_id.in_(old_ids))
    ).all()
    for point_run in point_runs:
        point_run.checkpoint_final_id = replacement_map[point_run.checkpoint_final_id]
        session.add(point_run)

    rewired_audit_runs = 0
    audit_runs = session.exec(select(AuditRun)).all()
    for audit_run in audit_runs:
        try:
            raw_ids = json.loads(audit_run.checkpoint_final_ids)
        except json.JSONDecodeError as exc:
            raise CheckpointDedupError(
                f"AuditRun {audit_run.id} checkpoint_final_ids 不是合法 JSON"
            ) from exc

        if not isinstance(raw_ids, list) or not all(isinstance(item, str) for item in raw_ids):
            raise CheckpointDedupError(
                f"AuditRun {audit_run.id} checkpoint_final_ids 必须是 list[str]"
            )

        replaced_ids = [replacement_map.get(item, item) for item in raw_ids]
        deduped_ids = _dedupe_ids_preserving_order(replaced_ids)
        if deduped_ids != raw_ids:
            audit_run.checkpoint_final_ids = json.dumps(deduped_ids, ensure_ascii=False)
            session.add(audit_run)
            rewired_audit_runs += 1

    return len(point_runs), rewired_audit_runs
```

- [ ] **Step 4: Add existing-table dedup helper**

继续追加：

```python
def deduplicate_existing_checkpoints(session: Session) -> DedupStats:
    """清理 CheckpointFinal 旧库中 title 重复的记录。

    同一 title 只保留 approved_at 最新的记录；approved_at 相同时保留 id 字典序较大者。
    删除旧记录前会迁移 AuditPointRun 和 AuditRun 引用。

    Args:
        session: 当前数据库 session，调用方负责 commit/rollback。

    Returns:
        DedupStats 去重诊断。
    """
    finals = session.exec(select(CheckpointFinal)).all()
    groups: dict[str, list[CheckpointFinal]] = {}
    for final in finals:
        title_key = _checkpoint_title_key(final.payload_json)
        if title_key is None:
            continue
        groups.setdefault(title_key, []).append(final)

    replacement_map: dict[str, str] = {}
    delete_targets: list[CheckpointFinal] = []
    for grouped_finals in groups.values():
        if len(grouped_finals) < 2:
            continue
        keep = max(grouped_finals, key=lambda item: (item.approved_at, item.id))
        for final in grouped_finals:
            if final.id == keep.id:
                continue
            replacement_map[final.id] = keep.id
            delete_targets.append(final)

    rewired_point_runs, rewired_audit_runs = _rewire_checkpoint_references(
        session,
        replacement_map,
    )
    for final in delete_targets:
        session.delete(final)

    return DedupStats(
        removed_existing_count=len(delete_targets),
        rewired_audit_point_runs=rewired_point_runs,
        rewired_audit_runs=rewired_audit_runs,
    )
```

- [ ] **Step 5: Update import endpoint to call dedup and skip new duplicates**

替换 `import_checkpoints()` 中写入 DB 的部分：

```python
    imported: list[dict[str, str | None]] = []
    with get_db_session() as session:
        deduplicate_existing_checkpoints(session)
        existing_titles = {
            title
            for final in session.exec(select(CheckpointFinal)).all()
            if (title := _checkpoint_title_key(final.payload_json)) is not None
        }

        for cp in checkpoints:
            title_key = cp.title.strip()
            if title_key in existing_titles:
                skipped_reasons.append(f"审核点标题已存在，跳过导入：{title_key}")
                continue

            final = CheckpointFinal(
                payload_json=cp.model_dump_json(),
                approved_by="system:import",
            )
            session.add(final)
            session.flush()
            existing_titles.add(title_key)
            imported.append(_serialize_final(final))
        session.commit()

    return {
        "imported_count": len(imported),
        "skipped_count": len(skipped_reasons),
        "skipped_reasons": skipped_reasons,
        "checkpoints": imported,
    }
```

- [ ] **Step 6: Run backend route tests**

运行：

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoints_route.py -v
```

预期：

- 所有 `tests/unit/test_checkpoints_route.py` 测试通过。

- [ ] **Step 7: Run parser and route regression tests**

运行：

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_import.py tests/unit/test_checkpoints_route.py -v
```

预期：

- `tests/unit/test_checkpoint_import.py` 继续通过。
- `tests/unit/test_checkpoints_route.py` 继续通过。

- [ ] **Step 8: Commit backend implementation**

```bash
git add govdoc/api/routes/checkpoints.py
git commit -m "fix: deduplicate imported checkpoints by title"
```

## Task 3: Frontend E2E Regression

**Files:**
- Modify: `frontend/e2e/test-02-import-checkpoints.js`

- [ ] **Step 1: Extend the import E2E with repeated import**

在 `frontend/e2e/test-02-import-checkpoints.js` 中，现有 Step 6 之后、最终 `console.log('== test-02...')` 之前追加：

```javascript
  // Step 7: 再次导入同一 XLS，验证不会继续新增审核点
  await page.getByRole('button', { name: /上传/ }).click();
  await page.getByText('导入审查点表格').click();
  await page.waitForLoadState('domcontentloaded');

  const secondFileInput = page.locator("input[type='file']");
  await secondFileInput.setInputFiles(XLS_PATH);
  const secondImportBtn = page.getByRole('button', { name: /启动解析|导入/ });
  await secondImportBtn.click();

  const secondSuccess = page.getByText(/成功导入/);
  await secondSuccess.waitFor({ timeout: 60000 });
  const secondSuccessText = await secondSuccess.textContent();
  console.log('Step 7: ' + secondSuccessText);

  await page.getByRole('button', { name: /返回列表/ }).click();
  await page.waitForLoadState('domcontentloaded');

  const rowsAfterSecondImport = page.locator('table tbody tr');
  await rowsAfterSecondImport.first().waitFor({ timeout: 10000 });
  const countAfterSecondImport = await rowsAfterSecondImport.count();
  if (countAfterSecondImport !== count) {
    throw new Error('重复导入后列表数量发生变化：' + count + ' -> ' + countAfterSecondImport);
  }

  const importedCountMatch = secondSuccessText.match(/成功导入\s*(\d+)\s*条/);
  if (importedCountMatch && Number(importedCountMatch[1]) !== 0) {
    throw new Error('重复导入应成功导入 0 条，实际提示：' + secondSuccessText);
  }

  await page.screenshot({ path: 'e2e/screenshots/02-import-dedup.png', fullPage: true });
```

- [ ] **Step 2: Run the quick E2E import test**

确认前端 testing 环境或本地 dev 环境可访问后运行：

```bash
export NO_PROXY="100.70.102.30,100.83.164.94,110.42.53.85,localhost,127.0.0.1"
export no_proxy="$NO_PROXY"
cd frontend && bash e2e/run-tests.sh --only 02-import-checkpoints
```

预期：

- `test-02-import-checkpoints` 通过。
- 输出包含 `Step 7:`。
- `frontend/e2e/screenshots/02-import-dedup.png` 生成。

- [ ] **Step 3: Commit E2E update**

```bash
git add frontend/e2e/test-02-import-checkpoints.js
git commit -m "test: cover checkpoint import dedup e2e"
```

## Task 4: Final Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Run focused backend tests**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_checkpoint_import.py tests/unit/test_checkpoints_route.py -v
```

预期：

- 两个测试文件全部通过。

- [ ] **Step 2: Run targeted E2E**

```bash
export NO_PROXY="100.70.102.30,100.83.164.94,110.42.53.85,localhost,127.0.0.1"
export no_proxy="$NO_PROXY"
cd frontend && bash e2e/run-tests.sh --only 02-import-checkpoints
```

预期：

- `== test-02-import-checkpoints 全部通过 ==`
- 无 `### Error`。

- [ ] **Step 3: Inspect final diff**

```bash
git status --short
git diff --stat HEAD
```

预期：

- 只出现本功能相关文件，或明确识别已有无关工作树变更。
- 不包含 `.env`、密钥、生成的大文件。

- [ ] **Step 4: Commit any remaining implementation changes**

如果 Task 2/3 已按任务分别提交，本步骤无需提交。若存在未提交的本功能小修，执行：

```bash
git add tests/unit/test_checkpoints_route.py govdoc/api/routes/checkpoints.py frontend/e2e/test-02-import-checkpoints.js
git commit -m "fix: prevent duplicate checkpoint imports"
```

## Acceptance Criteria

- 重复导入相同 CSV/XLS 时，第二次不新增相同 title 的 `CheckpointFinal`。
- 同一导入文件内部重复 title 时，只导入第一条。
- 旧库内部重复 title 在导入前被清理，保留 `approved_at` 最新记录。
- 被删除旧记录的 `AuditPointRun.checkpoint_final_id` 迁移到保留记录。
- 被删除旧记录的 `AuditRun.checkpoint_final_ids` 迁移到保留记录，并去重保序。
- 现有 `POST /api/v1/checkpoints/import` 响应字段保持兼容。
- `tests/unit/test_checkpoint_import.py` 和 `tests/unit/test_checkpoints_route.py` 通过。
- `frontend/e2e/test-02-import-checkpoints.js` 使用 `@playwright/cli` 跑通重复导入 UI 回归。

## Self-Review

- Spec coverage: 计划覆盖了 title 去重、旧库保新、新旧冲突保旧、引用迁移、响应兼容、前端 E2E。
- Placeholder scan: 无未定项或“稍后实现”类描述。
- Type consistency: helper 名称、返回类型、DB 字段名均与当前代码一致。
