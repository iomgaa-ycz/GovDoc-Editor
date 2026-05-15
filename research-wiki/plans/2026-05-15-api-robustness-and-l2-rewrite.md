# API 后台任务健壮性 + L2 评估重写

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 API 后台任务的 4 个设计缺口（A1-A4），重写 L2 评估使其覆盖全部 25 个端点并能在合理时间内跑完（B1-B4）。

**Architecture:** 分两大阶段：先修 API 层（heartbeat + startup sweep + per-point timeout + extract 异常修复 + cancel 端点），再重写 L2 评估（per-project 端到端 + 全端点覆盖 + CLI 基础设施）。两阶段之间有依赖——L2 的 cancel 测试依赖 A4 的新端点。

**Tech Stack:** Python 3.11 / FastAPI / SQLModel / SQLite / Alembic / httpx / asyncio

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `govdoc/db/models.py` | AuditRun 增加 `heartbeat_at`；ExtractRun 增加 `heartbeat_at` | [MODIFY] |
| `govdoc/db/migrations/versions/xxxx_add_heartbeat_at.py` | Alembic 迁移 | [NEW] |
| `govdoc/pipelines/audit_tender.py` | `run_audit` 主循环：心跳更新 + 单点 `asyncio.wait_for` 超时 + 取消检查 | [MODIFY] |
| `govdoc/pipelines/extract_rules.py` | `run_extract`：心跳更新 | [MODIFY] |
| `govdoc/api/routes/audit.py` | 后台任务异常兜底更新 status；新增 cancel 端点 | [MODIFY] |
| `govdoc/api/routes/rules.py` | 后台任务 `except: pass` → 兜底更新 ExtractRun.status | [MODIFY] |
| `govdoc/api/main.py` | startup 事件：扫描孤儿 AuditRun / ExtractRun | [MODIFY] |
| `govdoc/harness/api_eval.py` | L2 评估主逻辑：重写为 per-project 端到端 + 全端点覆盖 | [MODIFY] |
| `scripts/harness_api.sh` | L2 启动脚本：增加 `source activate` 替换 `conda run` | [MODIFY] |
| `tests/unit/test_api_eval.py` | L2 单测：更新以匹配重写后的接口 | [MODIFY] |
| `tests/unit/test_audit_heartbeat.py` | 心跳 + 超时 + 取消的单测 | [NEW] |

---

### Task 1: AuditRun / ExtractRun 增加 heartbeat_at 字段 + Alembic 迁移

**Files:**
- Modify: `govdoc/db/models.py:61-77` (AuditRun), `govdoc/db/models.py:50-58` (ExtractRun)
- Create: `govdoc/db/migrations/versions/xxxx_add_heartbeat_at.py`

- [ ] **Step 1: 修改 AuditRun 模型添加 heartbeat_at**

在 `govdoc/db/models.py` 的 AuditRun 类中，在 `created_at` 后添加：

```python
class AuditRun(SQLModel, table=True):
    """管道 B 的一次整体执行——编排多个 AuditPointRun。"""

    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    tender_doc_id: str = Field(foreign_key="tenderdoc.id")
    supplementary_doc_ids: str | None = None
    checkpoint_final_ids: str
    # pending / running / partial_ready / draft_ready / finalized / failed / waiting_retry / cancelled / interrupted
    status: str = "pending"
    processed_count: int = 0
    total_count: int = 0
    workspace_archive_path: str | None = None
    workspace_failed_path: str | None = None
    total_usage_json: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    heartbeat_at: datetime | None = None
```

- [ ] **Step 2: 修改 ExtractRun 模型添加 heartbeat_at**

```python
class ExtractRun(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    rule_source_id: str = Field(foreign_key="rulesource.id")
    # pending / running / draft_ready / completed / failed / interrupted
    status: str = "pending"
    workspace_archive_path: str | None = None
    workspace_failed_path: str | None = None
    total_usage_json: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    heartbeat_at: datetime | None = None
```

- [ ] **Step 3: 生成 Alembic 迁移**

运行:
```bash
source activate govdoc-auditor-v3 && alembic revision --autogenerate -m "add heartbeat_at to auditrun and extractrun"
```

- [ ] **Step 4: 应用迁移**

运行:
```bash
source activate govdoc-auditor-v3 && alembic upgrade head
```

- [ ] **Step 5: 提交**

```bash
git add govdoc/db/models.py govdoc/db/migrations/versions/
git commit -m "feat(db): AuditRun/ExtractRun 增加 heartbeat_at 字段"
```

---

### Task 2: run_audit 增加心跳更新 + 单点超时 + 取消检查

**Files:**
- Modify: `govdoc/pipelines/audit_tender.py:561-713`
- Test: `tests/unit/test_audit_heartbeat.py`

- [ ] **Step 1: 写失败测试 — 心跳更新**

创建 `tests/unit/test_audit_heartbeat.py`：

```python
"""审核心跳 + 超时 + 取消测试。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from govdoc.pipelines.audit_tender import _update_heartbeat


class TestUpdateHeartbeat:
    """测试心跳更新函数。"""

    def test_updates_heartbeat_at(self) -> None:
        """调用后 audit_run.heartbeat_at 被更新。"""
        audit_run = MagicMock()
        audit_run.heartbeat_at = None
        session = MagicMock()

        _update_heartbeat(audit_run, session)

        assert audit_run.heartbeat_at is not None
        assert isinstance(audit_run.heartbeat_at, datetime)
        session.add.assert_called_once_with(audit_run)
        session.commit.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

运行: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_audit_heartbeat.py -v`
预期: FAIL — `_update_heartbeat` 不存在

- [ ] **Step 3: 实现 _update_heartbeat**

在 `govdoc/pipelines/audit_tender.py` 的 `count_processed_points` 函数后添加：

```python
def _update_heartbeat(audit_run: AuditRun, session: Session) -> None:
    """更新 AuditRun 心跳时间戳。"""
    audit_run.heartbeat_at = datetime.utcnow()
    session.add(audit_run)
    session.commit()
```

- [ ] **Step 4: 运行测试确认通过**

运行: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_audit_heartbeat.py -v`
预期: PASS

- [ ] **Step 5: 修改 run_audit 主循环——加心跳 + 单点超时 + 取消检查**

在 `govdoc/pipelines/audit_tender.py` 的 `run_audit` 函数中，修改主循环（约 line 643-697）：

```python
    POINT_TIMEOUT_S = int(os.environ.get("GOVDOC_POINT_TIMEOUT", "900"))

    try:
        for point_run in point_runs_to_run:
            # 取消检查：每个点开始前刷新 audit_run 状态
            session.refresh(audit_run)
            if audit_run.status == "cancelled":
                logger.info("AuditRun %s 已取消，停止处理", audit_run.id)
                break

            checkpoint_row = session.get(CheckpointFinal, point_run.checkpoint_final_id)
            if checkpoint_row is None:
                point_run.status = "failed"
                point_run.error = f"未找到 CheckpointFinal: {point_run.checkpoint_final_id}"
                session.add(point_run)
                session.commit()
                continue

            checkpoint = GovCheckpoint.model_validate_json(checkpoint_row.payload_json)
            point_run.status = "running"
            session.add(point_run)
            session.commit()

            workspace = None
            result = None

            try:
                workspace, result = await asyncio.wait_for(
                    _run_single_point(
                        point_run,
                        checkpoint,
                        tender_doc,
                        supplementary_docs=supplementary_docs,
                        audit_run=audit_run,
                        tender_collection=tender_collection,
                        manager=manager,
                        store=store,
                        cfg=cfg,
                        repo_root=repo_root,
                        replay_dir=replay_dir,
                    ),
                    timeout=POINT_TIMEOUT_S,
                )

                _persist_point_result(point_run, result, workspace, checkpoint, manager)

            except asyncio.TimeoutError:
                point_run.status = "failed"
                point_run.error = f"单点超时 ({POINT_TIMEOUT_S}s)"
                logger.warning("审核点 %s 超时", point_run.id)

            except Exception as exc:
                point_run.status = "failed"
                point_run.error = str(exc)
                if (
                    workspace is not None
                    and workspace.root_dir.exists()
                    and point_run.workspace_failed_path is None
                ):
                    try:
                        point_run.workspace_failed_path = str(
                            manager.archive(workspace, success=False)
                        )
                    except Exception:
                        pass

            audit_run.processed_count = count_processed_points(session, audit_run.id)
            _update_heartbeat(audit_run, session)
            session.add(point_run)
            session.commit()
```

注意：需要在文件顶部 `import` 部分添加 `import asyncio` 和 `import os`（如果还没有的话）。

- [ ] **Step 6: 运行全量单测确认无回退**

运行: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_audit_tender_helpers.py tests/unit/test_audit_heartbeat.py -v`
预期: 全部 PASS

- [ ] **Step 7: 提交**

```bash
git add govdoc/pipelines/audit_tender.py tests/unit/test_audit_heartbeat.py
git commit -m "feat(pipeline): run_audit 增加心跳更新 + 单点超时 + 取消检查"
```

---

### Task 3: run_extract 增加心跳更新

**Files:**
- Modify: `govdoc/pipelines/extract_rules.py`

- [ ] **Step 1: 在 run_extract 中添加心跳更新**

在 `govdoc/pipelines/extract_rules.py` 的 `run_extract` 函数中，`extract_run.status = "running"` 设置之后、`pes.run()` 之前，以及 `pes.run()` 完成后，添加心跳更新：

```python
    extract_run.status = "running"
    extract_run.heartbeat_at = datetime.utcnow()
    session.add(extract_run)
    session.commit()
```

以及在 `pes.run()` 返回后（结果处理之前）：

```python
    extract_run.heartbeat_at = datetime.utcnow()
    session.add(extract_run)
    session.commit()
```

注意：需要在文件顶部添加 `from datetime import datetime`（如果还没有的话）。

- [ ] **Step 2: 运行全量单测确认无回退**

运行: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v -k "extract or harness"`
预期: 全部 PASS

- [ ] **Step 3: 提交**

```bash
git add govdoc/pipelines/extract_rules.py
git commit -m "feat(pipeline): run_extract 增加心跳更新"
```

---

### Task 4: 修复 rules/upload 异常静默吞掉 + audit 后台任务兜底

**Files:**
- Modify: `govdoc/api/routes/rules.py:77-82`
- Modify: `govdoc/api/routes/audit.py:92-97`

- [ ] **Step 1: 修复 rules.py 的 except: pass**

将 `govdoc/api/routes/rules.py` 中的 `_run_extract` 函数修改为：

```python
    async def _run_extract():
        with get_db_session() as s:
            try:
                await run_extract(rule_source.id, s, extract_run_id=extract_run.id)
            except Exception:
                logger.exception("后台提取执行失败: %s", extract_run.id)
                try:
                    er = s.get(ExtractRun, extract_run.id)
                    if er is not None and er.status not in ("draft_ready", "completed", "failed"):
                        er.status = "failed"
                        er.error = "后台任务异常退出"
                        s.add(er)
                        s.commit()
                except Exception:
                    pass
```

注意：需要在文件顶部添加 `import logging` 和 `logger = logging.getLogger(__name__)`。

- [ ] **Step 2: 修复 audit.py 的后台任务兜底**

将 `govdoc/api/routes/audit.py` 中的 `_run_audit` 函数修改为：

```python
    async def _run_audit():
        with get_db_session() as s:
            try:
                await run_audit(audit_run.id, s)
            except Exception:
                logger.exception("后台审核执行失败: %s", audit_run.id)
                try:
                    ar = s.get(AuditRun, audit_run.id)
                    if ar is not None and ar.status not in ("draft_ready", "completed", "partial_ready", "failed", "waiting_retry"):
                        ar.status = "failed"
                        ar.error = "后台任务异常退出"
                        s.add(ar)
                        s.commit()
                except Exception:
                    pass
```

- [ ] **Step 3: 运行全量单测确认无回退**

运行: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v`
预期: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add govdoc/api/routes/rules.py govdoc/api/routes/audit.py
git commit -m "fix(api): 后台任务异常兜底更新 status，消除 except:pass"
```

---

### Task 5: startup 孤儿扫描 + cancel 端点

**Files:**
- Modify: `govdoc/api/main.py:31-93`
- Modify: `govdoc/api/routes/audit.py` (新增 cancel 端点)

- [ ] **Step 1: 在 main.py 添加 startup 孤儿扫描**

在 `govdoc/api/main.py` 的 `create_app()` 中，`app.include_router(...)` 之前添加：

```python
    @app.on_event("startup")
    def _sweep_orphaned_runs():
        """启动时将无心跳的 running 状态 AuditRun/ExtractRun 标记为 interrupted。"""
        from datetime import datetime, timedelta
        from govdoc.db.models import AuditRun, ExtractRun
        from sqlmodel import select

        _logger.info("扫描孤儿后台任务...")
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        with get_db_session() as session:
            orphan_audits = session.exec(
                select(AuditRun).where(AuditRun.status == "running")
            ).all()
            for ar in orphan_audits:
                if ar.heartbeat_at is None or ar.heartbeat_at < cutoff:
                    ar.status = "interrupted"
                    ar.error = "服务重启时检测到孤儿任务"
                    session.add(ar)
                    _logger.warning("标记孤儿 AuditRun: %s", ar.id)
            orphan_extracts = session.exec(
                select(ExtractRun).where(ExtractRun.status.in_(["pending", "running"]))
            ).all()
            for er in orphan_extracts:
                if er.heartbeat_at is None or er.heartbeat_at < cutoff:
                    er.status = "interrupted"
                    er.error = "服务重启时检测到孤儿任务"
                    session.add(er)
                    _logger.warning("标记孤儿 ExtractRun: %s", er.id)
            session.commit()
```

注意：需要在文件顶部添加 `from govdoc.api.deps import get_db_session`。

- [ ] **Step 2: 在 audit.py 新增 cancel 端点**

在 `govdoc/api/routes/audit.py` 的 `retry_point_run` 之前添加：

```python
@router.post("/runs/{audit_run_id}/cancel", status_code=200)
async def cancel_audit_run(audit_run_id: str):
    """取消一个正在运行的审核。后台任务会在下一个审核点开始前检查并停止。"""
    with get_db_session() as session:
        run = session.get(AuditRun, audit_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="AuditRun 不存在")
        if run.status not in ("pending", "running"):
            raise HTTPException(status_code=400, detail=f"状态 {run.status} 不可取消")
        run.status = "cancelled"
        session.add(run)
        session.commit()
        return {"audit_run_id": run.id, "status": "cancelled"}
```

- [ ] **Step 3: 运行全量单测确认无回退**

运行: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v`
预期: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add govdoc/api/main.py govdoc/api/routes/audit.py
git commit -m "feat(api): startup 孤儿扫描 + POST /audit/runs/{id}/cancel 取消端点"
```

---

### Task 6: 重写 L2 api_eval.py — per-project 端到端 + 全端点覆盖

**Files:**
- Modify: `govdoc/harness/api_eval.py` (整体重写 `run_api_eval`)

- [ ] **Step 1: 重写 run_api_eval**

将 `govdoc/harness/api_eval.py` 中的 `run_api_eval` 函数完全替换为以下实现。保留文件中的 `EndpointSpec`、`record_api_call`、`record_api_contract`、`check_response_schema`、`call_endpoint`、`_poll_until_done` 不变。

```python
async def run_api_eval(
    *,
    base_url: str = "http://localhost:8000",
    manifest_path: str,
    project_root: str,
    rubric_dir: str = "scripts/rubrics",
    db_path: str = "results/harness.db",
    run_id: str | None = None,
) -> str:
    """L2 API 评估主入口：per-project 端到端 + 全端点覆盖。

    参数:
        base_url: FastAPI 服务地址。
        manifest_path: harness_manifest.yaml 路径。
        project_root: 项目根目录。
        rubric_dir: 语义评估 rubrics 目录。
        db_path: harness.db 路径。
        run_id: 可选运行 ID。

    返回:
        本次运行的 run_id。
    """
    import httpx
    from dotenv import load_dotenv

    from govdoc.harness.manifest import load_manifest
    from govdoc.harness.pipeline_eval import (
        _clean_harness_state,
        _run_semantic_evaluations,
        record_audit_results,
        record_extract_results,
        record_pipeline_run,
    )

    load_dotenv()
    run_id = run_id or f"L2-{uuid.uuid4().hex[:8]}"
    manifest = load_manifest(manifest_path, project_root=project_root)
    max_checkpoints = int(os.environ.get("HARNESS_MAX_CHECKPOINTS", "5"))
    pipeline_timeout = float(os.environ.get("HARNESS_PIPELINE_TIMEOUT", "1800"))

    config_snapshot: dict[str, Any] = {
        "base_url": base_url,
        "manifest_path": manifest_path,
        "max_checkpoints": max_checkpoints,
        "pipeline_timeout": pipeline_timeout,
    }

    async with httpx.AsyncClient(base_url=base_url, timeout=600.0) as client:
        with HarnessLog(db_path=db_path, run_id=run_id, config_snapshot=config_snapshot) as log:
            create_all_tables(log)
            log.log_event("api_eval_start", {"base_url": base_url, "config": config_snapshot})

            # ── 清理上次 harness 残留 ──
            from govdoc.db.session import get_session as _get_session
            _sg = _get_session()
            _clean_session = next(_sg)
            try:
                _clean_harness_state(_clean_session)
            finally:
                _sg.close()

            # ── Phase 1: 冒烟端点 ──
            await call_endpoint(client, EndpointSpec(
                method="GET", path="/healthz", expected_status=200, description="健康检查",
            ), log)

            await call_endpoint(client, EndpointSpec(
                method="GET", path="/api/v1/projects", expected_status=200, description="列出项目",
            ), log)

            await call_endpoint(client, EndpointSpec(
                method="GET", path="/api/v1/rules", expected_status=200, description="列出法规",
            ), log)

            await call_endpoint(client, EndpointSpec(
                method="GET", path="/api/v1/checkpoints", expected_status=200, description="列出审核点",
            ), log)

            # ── Phase 2: Pipeline A — per rule ──
            for rule in manifest.rules:
                rule_path = Path(rule.path)
                if not rule_path.exists():
                    logger.warning("法规文件不存在: %s", rule_path)
                    continue

                t0 = time.time()
                status, resp_data = await call_endpoint(client, EndpointSpec(
                    method="POST", path="/api/v1/rules/upload", expected_status=202,
                    description=f"上传法规: {rule.name}",
                    form_data={"title": rule.name},
                    files={"file": (rule_path.name, rule_path.read_bytes())},
                ), log)

                if not resp_data:
                    continue
                rule_source_id = resp_data.get("rule_source_id", "")
                extract_run_id = resp_data.get("extract_run_id", "")
                if not extract_run_id:
                    continue

                poll_path = f"/api/v1/rules/{rule_source_id}/extract-runs/{extract_run_id}/status"
                final = await _poll_until_done(
                    client, poll_path, status_field="status",
                    terminal_statuses={"draft_ready", "completed", "failed", "interrupted"},
                    log=log, poll_interval=10.0, timeout_s=pipeline_timeout,
                )
                pa_status = final["status"] if final else "timeout"
                record_pipeline_run(
                    log, pipeline="A", project_name=rule.name, input_file=rule.path,
                    status=pa_status, duration_s=time.time() - t0, total_tokens=0,
                    error=(final.get("error") if final else "Pipeline A 超时") or None,
                )

                if pa_status in ("draft_ready", "completed"):
                    _, cp_list = await call_endpoint(client, EndpointSpec(
                        method="GET", path="/api/v1/checkpoints", expected_status=200,
                        description="获取抽取审核点",
                    ), log)
                    if cp_list:
                        extract_cps = [
                            json.loads(cp.get("payload_json", "{}"))
                            for cp in cp_list if cp.get("approved_by") == "system:auto-promote"
                        ]
                        if extract_cps:
                            record_extract_results(log, extract_cps)

            # ── Phase 3: 导入金标准审核点 ──
            imported_checkpoint_ids: list[str] = []
            for cp_fixture in manifest.checkpoints:
                cp_path = Path(cp_fixture.path)
                if not cp_path.exists():
                    continue
                status, resp = await call_endpoint(client, EndpointSpec(
                    method="POST", path="/api/v1/checkpoints/import", expected_status=200,
                    description=f"导入审核点: {cp_fixture.name}",
                    files={"file": (cp_path.name, cp_path.read_bytes())},
                ), log)
                if resp:
                    ids = [c["id"] for c in resp.get("checkpoints", []) if c.get("id")]
                    imported_checkpoint_ids.extend(ids)

            # 截断审核点数量
            if max_checkpoints > 0 and len(imported_checkpoint_ids) > max_checkpoints:
                imported_checkpoint_ids = imported_checkpoint_ids[:max_checkpoints]
                logger.info("审核点截断为 %d 个", max_checkpoints)

            # ── Phase 4: Checkpoint CRUD 测试 ──
            if imported_checkpoint_ids:
                test_cp_id = imported_checkpoint_ids[-1]
                await call_endpoint(client, EndpointSpec(
                    method="PUT", path="/api/v1/checkpoints/{checkpoint_id}", expected_status=200,
                    description="更新审核点",
                    path_params={"checkpoint_id": test_cp_id},
                    body={"payload_json": '{"id":"test","category":"测试","title":"CRUD 测试","description":"","legal_basis":[],"severity":"minor","retrieval_hint":""}'},
                ), log)

                # 不真的删除——从列表中移除即可保证审核时不用
                # 但要测试端点可达性：用一个额外导入的审核点做删除测试
                _, extra_resp = await call_endpoint(client, EndpointSpec(
                    method="GET", path="/api/v1/checkpoints", expected_status=200,
                    description="列出审核点（CRUD 后）",
                ), log)
                # 找一个不在 imported 列表中的审核点来删除（避免影响后续审核）
                if extra_resp:
                    all_ids = {c["id"] for c in extra_resp if c.get("id")}
                    deletable = all_ids - set(imported_checkpoint_ids)
                    if deletable:
                        del_id = next(iter(deletable))
                        await call_endpoint(client, EndpointSpec(
                            method="DELETE", path="/api/v1/checkpoints/{checkpoint_id}",
                            expected_status=204, description="删除审核点",
                            path_params={"checkpoint_id": del_id},
                        ), log)

            # ── Phase 5: Per-project 端到端（Pipeline B + workpaper） ──
            audit_terminal = {"draft_ready", "completed", "partial_ready", "failed", "waiting_retry", "cancelled", "interrupted"}
            completed_audit_run_ids: list[str] = []

            for proj in manifest.projects:
                tender_path = Path(proj.tender_doc)
                if not tender_path.exists() or not imported_checkpoint_ids:
                    continue

                # 5a: 创建 Project
                _, proj_resp = await call_endpoint(client, EndpointSpec(
                    method="POST", path="/api/v1/projects", expected_status=201,
                    description=f"创建项目: {proj.name}",
                    body={"name": f"harness-{proj.name}-{run_id}", "created_by": "harness"},
                ), log)
                if not proj_resp:
                    continue
                project_id = proj_resp["id"]

                # 5b: 获取单个 Project
                await call_endpoint(client, EndpointSpec(
                    method="GET", path="/api/v1/projects/{project_id}", expected_status=200,
                    description=f"获取项目: {proj.name}",
                    path_params={"project_id": project_id},
                ), log)

                # 5c: 上传文书
                _, td_resp = await call_endpoint(client, EndpointSpec(
                    method="POST", path="/api/v1/projects/{project_id}/tender-doc",
                    expected_status=201, description=f"上传文书: {proj.name}",
                    path_params={"project_id": project_id},
                    files={"file": (tender_path.name, tender_path.read_bytes())},
                ), log)
                if not td_resp:
                    continue
                tender_doc_id = td_resp["id"]

                # 5d: 列出文书
                await call_endpoint(client, EndpointSpec(
                    method="GET", path="/api/v1/projects/{project_id}/tender-docs",
                    expected_status=200, description=f"列出文书: {proj.name}",
                    path_params={"project_id": project_id},
                ), log)

                # 5e: 创建 Audit Run
                t0 = time.time()
                status, audit_resp = await call_endpoint(client, EndpointSpec(
                    method="POST", path="/api/v1/audit/runs", expected_status=202,
                    description=f"创建审核: {proj.name}",
                    body={
                        "project_id": project_id,
                        "tender_doc_id": tender_doc_id,
                        "checkpoint_ids": imported_checkpoint_ids,
                    },
                ), log)

                if not audit_resp or status != 202:
                    record_pipeline_run(
                        log, pipeline="B", project_name=proj.name,
                        input_file=str(proj.tender_doc), status="create_failed",
                        duration_s=time.time() - t0, total_tokens=0,
                        error=f"创建审核返回 {status}",
                    )
                    continue
                audit_run_id = audit_resp.get("audit_run_id", "")
                if not audit_run_id:
                    continue

                # 5f: 列出 Audit Runs
                await call_endpoint(client, EndpointSpec(
                    method="GET", path="/api/v1/audit/runs", expected_status=200,
                    description="列出审核运行",
                ), log)

                # 5g: 获取单个 Audit Run
                await call_endpoint(client, EndpointSpec(
                    method="GET", path="/api/v1/audit/runs/{audit_run_id}", expected_status=200,
                    description="获取审核运行",
                    path_params={"audit_run_id": audit_run_id},
                ), log)

                # 5h: 轮询等待完成
                final = await _poll_until_done(
                    client, f"/api/v1/audit/runs/{audit_run_id}/progress",
                    status_field="status", terminal_statuses=audit_terminal,
                    log=log, poll_interval=10.0, timeout_s=pipeline_timeout,
                )
                audit_status = final["status"] if final else "timeout"
                record_pipeline_run(
                    log, pipeline="B", project_name=proj.name,
                    input_file=str(proj.tender_doc), status=audit_status,
                    duration_s=time.time() - t0, total_tokens=0,
                    error=None if audit_status in ("draft_ready", "completed", "partial_ready") else audit_status,
                )

                if not final or audit_status not in ("draft_ready", "completed", "partial_ready"):
                    continue
                completed_audit_run_ids.append(audit_run_id)

                # 5i: 记录审核发现
                _, progress = await call_endpoint(client, EndpointSpec(
                    method="GET", path=f"/api/v1/audit/runs/{audit_run_id}/progress",
                    expected_status=200, description="获取审核进度（记录发现）",
                ), log)
                if progress:
                    findings: list[dict[str, Any]] = []
                    for pr in progress.get("point_runs", []):
                        if pr.get("status") != "completed" or not pr.get("finding_json"):
                            continue
                        finding_raw = pr["finding_json"]
                        finding = json.loads(finding_raw) if isinstance(finding_raw, str) else finding_raw
                        finding["point_run_id"] = pr.get("id", "")
                        finding["checkpoint_id"] = pr.get("checkpoint_final_id", "")
                        finding["status"] = pr.get("status", "unknown")
                        finding["duration_s"] = 0.0
                        findings.append(finding)
                    if findings:
                        record_audit_results(log, findings)

                # 5j: 获取工作底稿草稿
                _, draft_resp = await call_endpoint(client, EndpointSpec(
                    method="GET", path=f"/api/v1/audit/runs/{audit_run_id}/workpaper/draft",
                    expected_status=200, description="获取工作底稿草稿",
                ), log)

                # 5k: 定稿（部分定稿 or 完整定稿）
                if audit_status == "partial_ready":
                    await call_endpoint(client, EndpointSpec(
                        method="POST",
                        path=f"/api/v1/audit/runs/{audit_run_id}/workpaper/finalize-partial",
                        expected_status=201, description="部分定稿",
                        body={"approved_by": "harness"},
                    ), log)
                elif audit_status == "draft_ready":
                    await call_endpoint(client, EndpointSpec(
                        method="POST",
                        path=f"/api/v1/audit/runs/{audit_run_id}/workpaper/finalize",
                        expected_status=201, description="完整定稿",
                        body={"approved_by": "harness"},
                    ), log)

                # 定稿是异步的，等一小段时间
                await asyncio.sleep(5)

                # 5l: 下载 DOCX
                await call_endpoint(client, EndpointSpec(
                    method="GET",
                    path=f"/api/v1/audit/runs/{audit_run_id}/workpaper/final/docx",
                    expected_status=200, description="下载 DOCX",
                ), log)

            # ── Phase 6: Retry 测试（使用已完成的 audit run 中的一个失败点） ──
            if completed_audit_run_ids:
                arid = completed_audit_run_ids[0]
                _, progress = await call_endpoint(client, EndpointSpec(
                    method="GET", path=f"/api/v1/audit/runs/{arid}/progress",
                    expected_status=200, description="获取进度（查失败点）",
                ), log)
                if progress:
                    failed_points = [
                        pr for pr in progress.get("point_runs", [])
                        if pr.get("status") == "failed"
                    ]
                    if failed_points:
                        retry_id = failed_points[0]["id"]
                        await call_endpoint(client, EndpointSpec(
                            method="POST",
                            path=f"/api/v1/audit/point-runs/{retry_id}/retry",
                            expected_status=202, description="重试失败点",
                            path_params={},
                        ), log)

            # ── Phase 7: Cancel 测试 ──
            # 创建一个新的 audit run 然后立即取消
            if manifest.projects and imported_checkpoint_ids:
                proj = manifest.projects[0]
                # 复用已创建的 project 和 tender_doc（如果有的话）
                _, all_runs = await call_endpoint(client, EndpointSpec(
                    method="GET", path="/api/v1/audit/runs", expected_status=200,
                    description="列出审核（查项目ID）",
                ), log)
                if all_runs and len(all_runs) > 0:
                    existing_proj_id = all_runs[0].get("project_id", "")
                    existing_td_id = all_runs[0].get("tender_doc_id", "")
                    if existing_proj_id and existing_td_id:
                        _, cancel_resp = await call_endpoint(client, EndpointSpec(
                            method="POST", path="/api/v1/audit/runs", expected_status=202,
                            description="创建审核（取消测试）",
                            body={
                                "project_id": existing_proj_id,
                                "tender_doc_id": existing_td_id,
                                "checkpoint_ids": imported_checkpoint_ids[:1],
                            },
                        ), log)
                        if cancel_resp:
                            cancel_arid = cancel_resp.get("audit_run_id", "")
                            if cancel_arid:
                                await asyncio.sleep(1)
                                await call_endpoint(client, EndpointSpec(
                                    method="POST",
                                    path=f"/api/v1/audit/runs/{cancel_arid}/cancel",
                                    expected_status=200, description="取消审核",
                                ), log)

            # ── Phase 8: Compare 测试 ──
            # 需要两份 DOCX。用 real_data 中的文件
            compare_files = list(Path(project_root).glob("real_data/**/*.docx"))
            if len(compare_files) >= 2:
                f1, f2 = compare_files[0], compare_files[1]
                await call_endpoint(client, EndpointSpec(
                    method="POST", path="/api/v1/compare", expected_status=200,
                    description="文档对比",
                    files={
                        "first_file": (f1.name, f1.read_bytes()),
                        "second_file": (f2.name, f2.read_bytes()),
                    },
                ), log)

            # ── Phase 9: 语义评估 ──
            logger.info("开始语义评估")
            _run_semantic_evaluations(log, rubric_dir, project_root)

            # ── Phase 10: P95 延迟 ──
            sync_calls = log.query(
                "SELECT duration_ms FROM api_calls WHERE run_id=? AND status_code > 0 "
                "ORDER BY duration_ms",
                (run_id,),
            )
            if sync_calls:
                durations = [row["duration_ms"] for row in sync_calls]
                p95_idx = int(len(durations) * 0.95)
                p95 = durations[min(p95_idx, len(durations) - 1)]
                log.log_event("api_latency_p95", {"p95_ms": p95})

            log.log_event("api_eval_complete", {
                "total_calls": len(sync_calls) if sync_calls else 0,
            })

    logger.info("L2 评估完成, run_id=%s", run_id)
    return run_id
```

- [ ] **Step 2: 运行全量单测确认无回退**

运行: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_api_eval.py -v`
预期: 全部 PASS（测试只测 record/call_endpoint 等工具函数，不测 run_api_eval 本身）

- [ ] **Step 3: 提交**

```bash
git add govdoc/harness/api_eval.py
git commit -m "feat(harness): 重写 L2 api_eval — per-project 端到端 + 全端点覆盖"
```

---

### Task 7: L2 CLI main() — 信号处理 + SqliteHandler + 异常恢复

**Files:**
- Modify: `govdoc/harness/api_eval.py:601-621` (替换 `if __name__` 块)

- [ ] **Step 1: 替换 L2 的 CLI 入口为完整 main()**

将 `govdoc/harness/api_eval.py` 末尾的 `if __name__ == "__main__"` 块替换为：

```python
def _parse_args() -> argparse.Namespace:
    """解析 L2 API 评估 CLI 参数。"""
    parser = argparse.ArgumentParser(description="L2 API harness 评估")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--manifest", default="scripts/fixtures/harness_manifest.yaml")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--rubric-dir", default="scripts/rubrics")
    parser.add_argument("--db-path", default="results/harness.db")
    return parser.parse_args()


def main() -> None:
    """运行 L2 API 评估 CLI，并记录致命异常与中断信号。"""
    import signal
    import sys
    from types import FrameType
    from typing import NoReturn

    from govdoc.harness.handler import SqliteHandler
    from govdoc.harness.log import _now_iso

    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    run_id = f"L2-{uuid.uuid4().hex[:8]}"
    root_logger = logging.getLogger()
    sqlite_handler = SqliteHandler(db_path=args.db_path, run_id=run_id)
    root_logger.addHandler(sqlite_handler)

    def _update_run_status(status: str) -> None:
        """确保运行记录存在，并更新最终状态。"""
        import sqlite3
        Path(args.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(args.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _runs (
                    run_id TEXT PRIMARY KEY, git_sha TEXT, started_at TEXT,
                    finished_at TEXT, heartbeat_at TEXT, config JSON,
                    status TEXT DEFAULT 'running'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT,
                    timestamp TEXT, event_type TEXT, payload JSON
                )
            """)
            now = _now_iso()
            conn.execute(
                "INSERT OR IGNORE INTO _runs (run_id, started_at, status) VALUES (?, ?, ?)",
                (run_id, now, "running"),
            )
            conn.execute(
                "UPDATE _runs SET finished_at = ?, status = ? WHERE run_id = ?",
                (now, status, run_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _handle_signal(signum: int, frame: FrameType | None) -> NoReturn:
        del frame
        _update_run_status("interrupted")
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        completed_run_id = asyncio.run(
            run_api_eval(
                base_url=args.base_url,
                manifest_path=args.manifest,
                project_root=args.project_root,
                rubric_dir=args.rubric_dir,
                db_path=args.db_path,
                run_id=run_id,
            )
        )
        logger.info("L2 完成, run_id=%s", completed_run_id)
    except Exception:
        logger.critical("L2 API 评估发生致命异常", exc_info=True)
        _update_run_status("crashed")
        sys.exit(1)
    finally:
        root_logger.removeHandler(sqlite_handler)
        sqlite_handler.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行全量单测确认无回退**

运行: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_api_eval.py -v`
预期: 全部 PASS

- [ ] **Step 3: 提交**

```bash
git add govdoc/harness/api_eval.py
git commit -m "feat(harness): L2 CLI main() — 信号处理 + SqliteHandler + 异常恢复"
```

---

### Task 8: 更新 harness_api.sh + 运行验证

**Files:**
- Modify: `scripts/harness_api.sh`

- [ ] **Step 1: 更新启动脚本**

替换 `scripts/harness_api.sh` 全部内容为：

```bash
#!/usr/bin/env bash
# L2 API harness 评估 — 端到端（含 Pipeline A/B + workpaper + 语义评估）
set -euo pipefail
cd "$(dirname "$0")/.."

BASE_URL="${HARNESS_API_URL:-http://localhost:8000}"
export no_proxy="110.42.53.85,100.81.95.44,localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="110.42.53.85,100.81.95.44,localhost,127.0.0.1,${NO_PROXY:-}"

LOG_DIR="results/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/harness_api_$(date +%Y%m%d_%H%M%S).log"

echo "=== L2 API Eval ===" | tee "$LOG_FILE"
echo "目标: $BASE_URL" | tee -a "$LOG_FILE"
echo "开始时间: $(date)" | tee -a "$LOG_FILE"
echo "HARNESS_MAX_CHECKPOINTS=${HARNESS_MAX_CHECKPOINTS:-5}" | tee -a "$LOG_FILE"

# 检查服务是否可达
if ! curl -sf "${BASE_URL}/healthz" > /dev/null 2>&1; then
    echo "错误: FastAPI 服务不可达 ($BASE_URL/healthz)" | tee -a "$LOG_FILE"
    echo "请先启动: source activate govdoc-auditor-v3 && uvicorn govdoc.api.main:app --port 8000" | tee -a "$LOG_FILE"
    exit 1
fi

source activate govdoc-auditor-v3 && python -m govdoc.harness.api_eval \
    --base-url "$BASE_URL" \
    --manifest scripts/fixtures/harness_manifest.yaml \
    --project-root . \
    --rubric-dir scripts/rubrics \
    --db-path results/harness.db \
    2>&1 | tee -a "$LOG_FILE"

echo "=== L2 完成 ===" | tee -a "$LOG_FILE"
echo "结束时间: $(date)" | tee -a "$LOG_FILE"
echo "日志: $LOG_FILE"
```

- [ ] **Step 2: 提交**

```bash
git add scripts/harness_api.sh
git commit -m "fix(harness): L2 启动脚本改用 source activate，增加 NO_PROXY"
```

---

## 验收标准

1. **API 层（A1-A4）**：
   - `source activate govdoc-auditor-v3 && alembic upgrade head` 成功
   - AuditRun / ExtractRun 有 `heartbeat_at` 字段
   - `run_audit` 每处理完一个点更新 heartbeat；单点超时 15 分钟
   - `POST /rules/upload` 后台任务失败时 ExtractRun.status → "failed"
   - `POST /audit/runs/{id}/cancel` 返回 200，后续审核点不再处理
   - 服务重启后孤儿 AuditRun/ExtractRun 被标记为 "interrupted"

2. **L2 层（B1-B4）**：
   - `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v` 全部通过
   - L2 覆盖 25 个端点中的至少 22 个（compare download 需要真实对比数据，可容忍跳过）
   - L2 per-project 端到端：每个 manifest project 独立走完 创建→上传→审核→底稿→定稿→下载
   - `HARNESS_MAX_CHECKPOINTS=5`（默认），5 点 × 5 分钟 = 25 分钟内可完成单项目审核
   - L2 运行前清理 app.sqlite 中上次 harness 残留
   - Ctrl+C 时 harness.db 中 status 变为 "interrupted"
   - `_runs.config` 包含 config_snapshot

3. **端到端验证**：
   - 启动 FastAPI 后运行 `bash scripts/harness_api.sh`
   - harness.db 中 `_runs` 状态为 `completed`
   - `pipeline_runs` 表有 Pipeline A + Pipeline B 记录
   - `extract_results` / `audit_results` 有数据
   - `quality_scores` 有 19 维语义评估
   - `api_calls` / `api_contracts` 覆盖 22+ 端点
