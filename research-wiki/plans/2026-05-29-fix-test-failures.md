# 修复预存测试失败 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复两个预存测试失败——审核点库查询顺序不稳定（系统 bug）和 E2E fixture 缺少后端可达性检查（测试基础设施缺陷），使 `pytest tests/` 在本地开发环境下全部通过。

**Architecture:** Bug 1 在 `_resolve_checkpoint_ids_from_library` 查询中加 `order_by(added_at)` 保证稳定顺序；Bug 2 在 E2E `api` fixture 中先探测后端，不可达时 `pytest.skip`。

**Tech Stack:** Python 3.11 / SQLModel / FastAPI / pytest / httpx

---

## 文件结构

| 操作 | 文件路径 | 职责 |
|---|---|---|
| Modify | `govdoc/api/routes/audit.py:51-53` | 审核点库查询加 `order_by` |
| Modify | `tests/e2e/conftest.py:35-45` | `api` fixture 加后端可达性检查 |

---

### Task 1: 审核点库查询加 order_by（系统 bug）

**Files:**
- Modify: `govdoc/api/routes/audit.py:51-53`
- Test: `tests/unit/test_audit_library_snapshot.py`

**问题：** `_resolve_checkpoint_ids_from_library` 中 `select(CheckpointLibraryItem).where(...)` 无 `ORDER BY`，SQLite 不保证返回顺序，导致 `audit_run.checkpoint_final_ids` 快照顺序不稳定。生产影响：同一个审核点库创建审核任务，工作底稿中审核点排列可能每次不同。

- [ ] **Step 1: 确认测试当前失败**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_audit_library_snapshot.py::test_create_audit_run_from_library_snapshots_checkpoint_ids -x --tb=short
```

预期：FAIL，`AssertionError: assert [...] == [...]`（ID 顺序不一致）。

- [ ] **Step 2: 修改查询加 order_by**

`govdoc/api/routes/audit.py` 第 51-53 行，将：

```python
    items = session.exec(
        select(CheckpointLibraryItem).where(CheckpointLibraryItem.library_id == library_id)
    ).all()
```

改为：

```python
    items = session.exec(
        select(CheckpointLibraryItem)
        .where(CheckpointLibraryItem.library_id == library_id)
        .order_by(CheckpointLibraryItem.added_at)
    ).all()
```

- [ ] **Step 3: 运行测试验证通过**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_audit_library_snapshot.py -x --tb=short
```

预期：2 passed。

---

### Task 2: E2E fixture 加后端可达性检查（测试基础设施缺陷）

**Files:**
- Modify: `tests/e2e/conftest.py:35-45`

**问题：** `api` fixture 创建 httpx 客户端后直接 yield，未检查后端是否可达。本地开发时 testing 后端（`100.82.33.121:8001`）通常不可达，导致所有依赖 `api` 的 E2E 测试抛 `httpx.ConnectTimeout` 失败。应在 fixture 中先探测，不可达时 `pytest.skip` 跳过整个 E2E session。

- [ ] **Step 1: 确认测试当前失败**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/e2e/test_01_healthcheck.py -x --tb=line 2>&1 | tail -5
```

预期：FAILED，`httpx.ConnectTimeout`。

- [ ] **Step 2: 修改 api fixture 加可达性检查**

`tests/e2e/conftest.py` 第 35-45 行，将：

```python
@pytest.fixture(scope="session")
def api(backend_url: str) -> httpx.Client:
    """Session 级 httpx 客户端，自带 base_url 和无代理设置。"""
    transport = httpx.HTTPTransport(proxy=None)
    client = httpx.Client(
        base_url=backend_url,
        timeout=httpx.Timeout(30.0, read=120.0),
        transport=transport,
    )
    yield client
    client.close()
```

改为：

```python
@pytest.fixture(scope="session")
def api(backend_url: str) -> httpx.Client:
    """Session 级 httpx 客户端，自带 base_url 和无代理设置。"""
    transport = httpx.HTTPTransport(proxy=None)
    client = httpx.Client(
        base_url=backend_url,
        timeout=httpx.Timeout(30.0, read=120.0),
        transport=transport,
    )
    try:
        client.get("/healthz", timeout=5.0)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        client.close()
        pytest.skip(f"E2E 后端不可达: {backend_url}")
    yield client
    client.close()
```

- [ ] **Step 3: 运行 E2E 测试验证跳过**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/e2e/ -x --tb=short 2>&1 | tail -5
```

预期：2 skipped（而非 failed）。

---

### Task 3: 全量回归验证

- [ ] **Step 1: 运行全部测试**

```bash
source activate govdoc-auditor-v3 && export no_proxy="110.42.53.85,100.81.95.44,localhost,127.0.0.1" && export NO_PROXY="$no_proxy" && python -m pytest tests/ --tb=short
```

预期：0 failed，unit 全 passed，e2e 全 skipped（后端不可达时）。
