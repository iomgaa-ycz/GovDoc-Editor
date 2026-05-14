# Harness 健壮性修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 harness 评估系统的 13 个健壮性问题，确保任何运行（成功/失败/被 kill/超时）都在 SQLite 中留下可追踪的日志记录。

**Architecture:** 在入口函数 `main()` 中接管所有异常路径，把已有的 `SqliteHandler`（`handler.py`）接线到 root logger，shell 脚本加 trap。内部循环增加 timeout、session 生命周期管理、heartbeat。judge 加重试。所有改动均在现有文件上修改，不引入新依赖。

**Tech Stack:** Python 3.11 / SQLite / asyncio / logging / bash

---

## File Structure

| 文件 | 职责 | 动作 |
|------|------|------|
| `govdoc/harness/log.py` | HarnessLog SQLite 薄包装 | MODIFY |
| `govdoc/harness/pipeline_eval.py` | L1 管道评估主逻辑 | MODIFY |
| `govdoc/harness/judge.py` | LLM 语义评估 | MODIFY |
| `scripts/harness_pipeline.sh` | L1 shell 入口 | MODIFY |
| `tests/unit/test_harness_resilience.py` | 健壮性专项单测 | CREATE |

---

### Task 1: `HarnessLog.__exit__` 不覆盖原始异常 + heartbeat

**Files:**
- Modify: `govdoc/harness/log.py:63-84,178-189,221-223`
- Create: `tests/unit/test_harness_resilience.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/unit/test_harness_resilience.py`:

```python
"""Harness 健壮性专项单测。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from govdoc.harness.log import HarnessLog
from govdoc.harness.schemas import create_all_tables


class TestExitDoesNotMaskException:
    """P5: __exit__ 中 close() 失败不应覆盖原始异常。"""

    def test_original_exception_propagates(self, tmp_path: Path) -> None:
        """当 with 块内抛异常且 close() 也失败时，原始异常应传播。"""
        db_path = str(tmp_path / "h.db")
        with pytest.raises(RuntimeError, match="原始错误"):
            with HarnessLog(db_path=db_path, run_id="mask-test") as log:
                log._conn.close()
                raise RuntimeError("原始错误")


class TestHeartbeat:
    """P11: heartbeat 更新时间戳。"""

    def test_heartbeat_updates_column(self, tmp_path: Path) -> None:
        """调用 heartbeat() 后 _runs.heartbeat_at 非空。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="hb-test") as log:
            log.heartbeat("pipeline_A")

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT heartbeat_at FROM _runs WHERE run_id='hb-test'"
            ).fetchone()
            conn.close()
            assert row is not None
            assert row[0] is not None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_resilience.py -v
```

预期: 2 FAILED — `heartbeat` 方法不存在 + `__exit__` 覆盖异常。

- [ ] **Step 3: 实现修复**

修改 `govdoc/harness/log.py`:

**3a:** `_init_fixed_tables` 的 `_runs` 表加 `heartbeat_at TEXT` 列（在 `finished_at TEXT,` 之后加一行 `heartbeat_at TEXT,`）:

```python
    def _init_fixed_tables(self) -> None:
        """创建 _runs 和 _events 固定表。"""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS _runs (
                run_id TEXT PRIMARY KEY,
                git_sha TEXT,
                started_at TEXT,
                finished_at TEXT,
                heartbeat_at TEXT,
                config JSON,
                status TEXT DEFAULT 'running'
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS _events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                timestamp TEXT,
                event_type TEXT,
                payload JSON
            )
        """)
        self._conn.commit()
```

**3b:** 在 `log_event` 方法之后（`self._conn.commit()` 那行后面）新增 `heartbeat` 方法:

```python
    def heartbeat(self, phase: str = "") -> None:
        """更新 _runs 行的 heartbeat 时间戳，用于检测 hang。

        参数:
            phase: 当前阶段标识（仅用于诊断）。
        """
        self._conn.execute(
            "UPDATE _runs SET heartbeat_at=? WHERE run_id=?",
            (_now_iso(), self._run_id),
        )
        self._conn.commit()
```

**3c:** 修改 `__exit__` 方法（第 221-223 行），用 try/except 保护 `close()`:

```python
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        status = "failed" if exc_type is not None else "completed"
        try:
            self.close(status=status)
        except Exception:
            if exc_type is None:
                raise
```

- [ ] **Step 4: 运行测试确认通过**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_resilience.py tests/unit/test_harness_log.py tests/unit/test_harness_schemas.py -v
```

预期: 全部 PASSED

- [ ] **Step 5: 提交**

```bash
git add govdoc/harness/log.py tests/unit/test_harness_resilience.py
git commit -m "fix(harness): __exit__ 不覆盖原始异常 + heartbeat 支持"
```

---

### Task 2: `main()` 顶层异常捕获 + SqliteHandler + 信号处理

**Files:**
- Modify: `govdoc/harness/pipeline_eval.py:1-18,189-195,570-588`
- Modify: `tests/unit/test_harness_resilience.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_harness_resilience.py` 追加:

```python
import json
import subprocess
import sys


class TestMainCatchesFatalException:
    """P1+P2: main() 顶层异常必须被捕获并写入 DB。"""

    def test_crash_recorded_in_db(self, tmp_path: Path) -> None:
        """run_pipeline_eval 抛致命异常时，DB 应有 crashed/failed 状态和 CRITICAL 事件。"""
        db_path = str(tmp_path / "crash.db")
        result = subprocess.run(
            [
                sys.executable, "-m", "govdoc.harness.pipeline_eval",
                "--manifest", str(tmp_path / "nonexistent_12345.yaml"),
                "--db-path", db_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0

        conn = sqlite3.connect(db_path)
        runs = conn.execute("SELECT status FROM _runs").fetchall()
        events = conn.execute(
            "SELECT event_type, payload FROM _events WHERE event_type='CRITICAL'"
        ).fetchall()
        conn.close()

        assert len(runs) >= 1
        assert any(r[0] in ("crashed", "failed") for r in runs)
        assert len(events) >= 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_resilience.py::TestMainCatchesFatalException -v
```

预期: FAIL — 当前 `__main__` 无 try/except，进程崩溃后 DB 文件根本不存在。

- [ ] **Step 3: 实现 `main()` 函数**

修改 `govdoc/harness/pipeline_eval.py`:

**3a:** 文件顶部 imports 区域（第 1-17 行之后）新增:

```python
import os
import signal
import sys

from govdoc.harness.handler import SqliteHandler
from govdoc.harness.log import _now_iso
```

**3b:** `run_pipeline_eval` 签名加 `run_id` 参数（第 189-195 行）:

```python
async def run_pipeline_eval(
    *,
    manifest_path: str,
    project_root: str,
    rubric_dir: str,
    db_path: str = "results/harness.db",
    run_id: str | None = None,
) -> str:
```

并删除函数体第一行 `run_id = f"L1-{uuid.uuid4().hex[:8]}"` 改为:

```python
    run_id = run_id or f"L1-{uuid.uuid4().hex[:8]}"
```

**3c:** 替换整个 `if __name__ == "__main__"` 块（第 570-588 行）为:

```python
def main() -> None:
    """L1 管道评估 CLI 入口，带顶层异常捕获和信号处理。"""
    parser = argparse.ArgumentParser(description="L1 管道 harness 评估")
    parser.add_argument("--manifest", default="scripts/fixtures/harness_manifest.yaml")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--rubric-dir", default="scripts/rubrics")
    parser.add_argument("--db-path", default="results/harness.db")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    run_id = f"L1-{uuid.uuid4().hex[:8]}"
    sqlite_handler = SqliteHandler(db_path=args.db_path, run_id=run_id)
    sqlite_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(sqlite_handler)

    def _handle_signal(signum: int, frame: Any) -> None:
        sig_name = signal.Signals(signum).name
        logger.warning("收到信号 %s，正在中断...", sig_name)
        try:
            import sqlite3 as _sql

            _conn = _sql.connect(args.db_path)
            _conn.execute(
                "UPDATE _runs SET status='interrupted', finished_at=? WHERE status='running'",
                (_now_iso(),),
            )
            _conn.commit()
            _conn.close()
        except Exception:
            pass
        sys.exit(128 + signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        actual_run_id = asyncio.run(
            run_pipeline_eval(
                manifest_path=args.manifest,
                project_root=args.project_root,
                rubric_dir=args.rubric_dir,
                db_path=args.db_path,
                run_id=run_id,
            )
        )
        logger.info("L1 完成, run_id=%s", actual_run_id)
    except Exception:
        logger.critical("L1 管道评估致命错误", exc_info=True)
        try:
            import sqlite3 as _sql

            _conn = _sql.connect(args.db_path)
            _conn.execute(
                "UPDATE _runs SET status='crashed', finished_at=? WHERE status='running'",
                (_now_iso(),),
            )
            _conn.commit()
            _conn.close()
        except Exception:
            pass
        sys.exit(1)
    finally:
        sqlite_handler.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_resilience.py tests/unit/test_pipeline_eval.py -v
```

预期: 全部 PASSED

- [ ] **Step 5: 提交**

```bash
git add govdoc/harness/pipeline_eval.py tests/unit/test_harness_resilience.py
git commit -m "fix(harness): main() 顶层异常捕获 + SqliteHandler + 信号处理"
```

---

### Task 3: Manifest 加载移入 HarnessLog 上下文

**Files:**
- Modify: `govdoc/harness/pipeline_eval.py:207-233`

- [ ] **Step 1: 重构 `run_pipeline_eval` 内部**

将 `run_pipeline_eval` 函数中 manifest 加载和 config_snapshot 构建顺序调整。把原来第 207-233 行替换为:

```python
    import os
    from dotenv import load_dotenv
    from govdoc.harness.manifest import load_manifest

    load_dotenv()
    run_id = run_id or f"L1-{uuid.uuid4().hex[:8]}"

    config_snapshot: dict[str, Any] = {
        "manifest_path": manifest_path,
        "project_root": project_root,
        "rubric_dir": rubric_dir,
        "db_path": db_path,
        "judge_model": os.environ.get("HARNESS_JUDGE_MODEL", ""),
        "judge_base_url": os.environ.get("HARNESS_JUDGE_BASE_URL", ""),
    }

    with HarnessLog(db_path=db_path, run_id=run_id, config_snapshot=config_snapshot) as log:
        create_all_tables(log)

        manifest = load_manifest(manifest_path, project_root=project_root)
        config_snapshot["projects"] = [p.name for p in manifest.projects]
        config_snapshot["rules"] = [r.name for r in manifest.rules]
        config_snapshot["checkpoints"] = [c.name for c in manifest.checkpoints]
        log.execute(
            "UPDATE _runs SET config=? WHERE run_id=?",
            (json.dumps(config_snapshot, ensure_ascii=False), run_id),
        )

        log.log_event("pipeline_eval_start", {
            "manifest": manifest_path,
            "config": config_snapshot,
        })

        # ... Phase 1 / Phase 2 / Phase 3 不变 ...
```

- [ ] **Step 2: 运行测试确认通过**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_resilience.py tests/unit/test_pipeline_eval.py -v
```

预期: 全部 PASSED（manifest 不存在时 `_runs.status=failed` 由 `__exit__` 写入，`CRITICAL` 事件由 `main()` 的 SqliteHandler 写入）

- [ ] **Step 3: 提交**

```bash
git add govdoc/harness/pipeline_eval.py
git commit -m "fix(harness): manifest 加载移入 HarnessLog 上下文，错误不再丢失"
```

---

### Task 4: 管道运行 timeout + session generator 修复 + heartbeat 调用

**Files:**
- Modify: `govdoc/harness/pipeline_eval.py:235-353`
- Modify: `tests/unit/test_harness_resilience.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_harness_resilience.py` 追加:

```python
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

from govdoc.harness.pipeline_eval import run_pipeline_eval


class TestPipelineTimeout:
    """P6: 管道运行超时应被捕获并记录。"""

    def test_timeout_recorded_in_pipeline_runs(self, tmp_path: Path) -> None:
        """管道 A 超时时，pipeline_runs 应记录 status=failed + error 含 timeout。"""
        db_path = str(tmp_path / "timeout.db")
        manifest_path = str(tmp_path / "manifest.yaml")
        (tmp_path / "manifest.yaml").write_text(
            "projects: []\nrules:\n  - name: slow\n    path: fake.doc\ncheckpoints: []\n",
            encoding="utf-8",
        )

        async def slow_extract(**kwargs):
            await asyncio.sleep(9999)

        with patch.dict(os.environ, {"HARNESS_PIPELINE_TIMEOUT": "1"}), \
             patch("govdoc.harness.pipeline_eval._ensure_rule_source", return_value="rs-1"), \
             patch("govdoc.pipelines.extract_rules.run_extract", new=slow_extract), \
             patch("govdoc.db.session.get_session", return_value=iter([MagicMock()])), \
             patch("govdoc.runtime.get_trajectory_store", return_value=MagicMock()):
            asyncio.run(
                run_pipeline_eval(
                    manifest_path=manifest_path,
                    project_root=str(tmp_path),
                    rubric_dir=str(tmp_path),
                    db_path=db_path,
                )
            )

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT status, error FROM pipeline_runs").fetchall()
        conn.close()

        assert len(rows) >= 1
        assert rows[0][0] == "failed"
        assert "timeout" in (rows[0][1] or "").lower() or "Timeout" in (rows[0][1] or "")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_resilience.py::TestPipelineTimeout -v --timeout=15
```

预期: FAIL 或 TIMEOUT — 当前无 timeout 包裹，`slow_extract` 永不返回。

- [ ] **Step 3: 实现修复**

修改 `govdoc/harness/pipeline_eval.py` 中管道 A 循环（Phase 1 注释下方）。完整替换:

```python
        pipeline_timeout = int(os.environ.get("HARNESS_PIPELINE_TIMEOUT", "1800"))

        # Phase 1: 管道 A
        for rule in manifest.rules:
            logger.info("管道 A: 处理法规 %s", rule.name)
            log.heartbeat("pipeline_A")
            t0 = time.time()
            session_gen = None
            try:
                from govdoc.pipelines.extract_rules import run_extract
                from govdoc.db.session import get_session
                from govdoc.runtime import get_trajectory_store

                traj_store = get_trajectory_store()
                session_gen = get_session()
                session = next(session_gen)
                extract_run = await asyncio.wait_for(
                    run_extract(
                        rule_source_id=_ensure_rule_source(rule, session),
                        session=session,
                        project_root=project_root,
                        trajectory_store=traj_store,
                    ),
                    timeout=pipeline_timeout,
                )
                duration = time.time() - t0
                usage = json.loads(extract_run.total_usage_json or "{}")
                total_tokens = sum(usage.values()) if usage else 0

                record_pipeline_run(
                    log,
                    pipeline="A",
                    project_name=rule.name,
                    input_file=rule.path,
                    status=extract_run.status,
                    duration_s=duration,
                    total_tokens=total_tokens,
                    error=getattr(extract_run, "error", None),
                )

                if extract_run.status in ("draft_ready", "completed"):
                    checkpoints = _load_extract_output(extract_run, session)
                    record_extract_results(log, checkpoints)
            except Exception as exc:
                import traceback

                duration = time.time() - t0
                tb = traceback.format_exc()
                record_pipeline_run(
                    log,
                    pipeline="A",
                    project_name=rule.name,
                    input_file=rule.path,
                    status="failed",
                    duration_s=duration,
                    total_tokens=0,
                    error=f"{type(exc).__name__}: {exc}",
                )
                log.log_event("pipeline_error", {
                    "pipeline": "A",
                    "project_name": rule.name,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback": tb,
                })
                logger.error("管道 A 失败: %s\n%s", rule.name, tb)
            finally:
                if session_gen is not None:
                    session_gen.close()

        # Phase 2: 管道 B
        for proj in manifest.projects:
            logger.info("管道 B: 处理项目 %s", proj.name)
            log.heartbeat("pipeline_B")
            t0 = time.time()
            session_gen = None
            try:
                from govdoc.pipelines.audit_tender import run_audit
                from govdoc.db.session import get_session
                from govdoc.runtime import get_trajectory_store

                traj_store = get_trajectory_store()
                session_gen = get_session()
                session = next(session_gen)
                audit_run = await asyncio.wait_for(
                    run_audit(
                        audit_run_id=_ensure_audit_run(proj, session, manifest),
                        session=session,
                        project_root=project_root,
                        trajectory_store=traj_store,
                    ),
                    timeout=pipeline_timeout,
                )
                duration = time.time() - t0

                record_pipeline_run(
                    log,
                    pipeline="B",
                    project_name=proj.name,
                    input_file=proj.tender_doc,
                    status=audit_run.status,
                    duration_s=duration,
                    total_tokens=0,
                )

                if audit_run.status in ("draft_ready", "partial_ready", "completed"):
                    findings = _load_audit_findings(audit_run, session)
                    record_audit_results(log, findings)
            except Exception as exc:
                import traceback

                duration = time.time() - t0
                tb = traceback.format_exc()
                record_pipeline_run(
                    log,
                    pipeline="B",
                    project_name=proj.name,
                    input_file=proj.tender_doc,
                    status="failed",
                    duration_s=duration,
                    total_tokens=0,
                    error=f"{type(exc).__name__}: {exc}",
                )
                log.log_event("pipeline_error", {
                    "pipeline": "B",
                    "project_name": proj.name,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback": tb,
                })
                logger.error("管道 B 失败: %s\n%s", proj.name, tb)
            finally:
                if session_gen is not None:
                    session_gen.close()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_resilience.py -v --timeout=30
```

预期: 全部 PASSED

- [ ] **Step 5: 提交**

```bash
git add govdoc/harness/pipeline_eval.py tests/unit/test_harness_resilience.py
git commit -m "fix(harness): 管道运行加 timeout + session generator 正确关闭 + heartbeat"
```

---

### Task 5: judge 初始化失败不崩溃整个 run

**Files:**
- Modify: `govdoc/harness/pipeline_eval.py:472-483`
- Modify: `tests/unit/test_harness_resilience.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_harness_resilience.py` 追加:

```python
from govdoc.harness.pipeline_eval import _run_semantic_evaluations


class TestJudgeInitFailure:
    """P8: judge 初始化失败不应让整个 run 崩溃。"""

    def test_judge_failure_logged_not_raised(self, tmp_path: Path) -> None:
        """HarnessJudge 构造失败时，函数正常返回并在 _events 留记录。"""
        db_path = str(tmp_path / "judge.db")
        with HarnessLog(db_path=db_path, run_id="judge-fail") as log:
            create_all_tables(log)

            with patch("govdoc.harness.pipeline_eval.HarnessJudge", side_effect=ConnectionError("模拟失败")):
                _run_semantic_evaluations(log, str(tmp_path), str(tmp_path))

            events = log.query(
                "SELECT event_type FROM _events WHERE run_id='judge-fail' AND event_type='semantic_eval_fatal'"
            )
            assert len(events) == 1
```

- [ ] **Step 2: 运行测试确认失败**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_resilience.py::TestJudgeInitFailure -v
```

预期: FAIL — 当前 judge 初始化失败直接抛异常。

- [ ] **Step 3: 实现修复**

修改 `govdoc/harness/pipeline_eval.py` 中 `_run_semantic_evaluations` 函数（第 472-483 行），用 try/except 包裹 judge 初始化:

```python
def _run_semantic_evaluations(log: HarnessLog, rubric_dir: str, project_root: str) -> None:
    """运行全部语义评估维度。"""
    import os
    from dotenv import load_dotenv

    load_dotenv()
    try:
        judge = HarnessJudge(
            provider="openai",
            model=os.environ.get("HARNESS_JUDGE_MODEL", "qwen3.6-plus"),
            base_url=os.environ.get("HARNESS_JUDGE_BASE_URL", "http://110.42.53.85:11098"),
            api_key=os.environ.get("HARNESS_JUDGE_API_KEY", ""),
        )
    except Exception as exc:
        import traceback

        tb = traceback.format_exc()
        log.log_event("semantic_eval_fatal", {
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": tb,
        })
        logger.error("HarnessJudge 初始化失败，跳过全部语义评估:\n%s", tb)
        return

    # ... 后续代码（extract_rows / audit_rows / trajectory_evidence / dimensions 循环）保持不变 ...
```

- [ ] **Step 4: 运行测试确认通过**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_resilience.py -v
```

预期: 全部 PASSED

- [ ] **Step 5: 提交**

```bash
git add govdoc/harness/pipeline_eval.py tests/unit/test_harness_resilience.py
git commit -m "fix(harness): judge 初始化失败不崩溃整个 run"
```

---

### Task 6: `_call_llm` 重试

**Files:**
- Modify: `govdoc/harness/judge.py:51-83`
- Modify: `tests/unit/test_harness_resilience.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_harness_resilience.py` 追加:

```python
from govdoc.harness.judge import HarnessJudge


class TestCallLlmRetry:
    """P10: _call_llm 瞬时失败应重试。"""

    def test_retries_on_transient_error(self) -> None:
        """前两次 httpx.post 失败、第三次成功，应返回成功结果。"""
        judge = HarnessJudge(
            provider="openai", model="test", base_url="http://fake", api_key="key",
        )

        call_count = 0

        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError(f"模拟失败 #{call_count}")
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": '{"passed": true, "score": 0.9}'}}]
            }
            resp.raise_for_status = MagicMock()
            return resp

        with patch("httpx.post", side_effect=mock_post), \
             patch("time.sleep"):
            result = judge._call_llm("test prompt")

        assert call_count == 3
        assert "passed" in result

    def test_no_retry_on_value_error(self) -> None:
        """不支持的 provider 应立即抛错，不重试。"""
        judge = HarnessJudge(provider="unknown", model="x")
        with pytest.raises(ValueError, match="不支持的 provider"):
            judge._call_llm("test")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_resilience.py::TestCallLlmRetry -v
```

预期: FAIL — 当前无重试逻辑，第一次 `ConnectionError` 直接抛出。

- [ ] **Step 3: 实现修复**

替换 `govdoc/harness/judge.py` 中 `_call_llm` 方法（第 51-83 行）:

```python
    def _call_llm(self, prompt: str, *, max_retries: int = 2) -> str:
        """调用 LLM API 获取回复，带简单重试。

        参数:
            prompt: 发送给模型的完整 prompt。
            max_retries: 最大重试次数（不含首次）。

        返回:
            模型的文本回复。
        """
        import time as _time

        last_exc: Exception | None = None
        for attempt in range(1 + max_retries):
            try:
                if self._provider == "anthropic":
                    import anthropic

                    client = anthropic.Anthropic(api_key=self._api_key)
                    response = client.messages.create(
                        model=self._model,
                        max_tokens=2048,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    return response.content[0].text
                if self._provider == "openai":
                    import httpx

                    url = f"{self._base_url}/v1/chat/completions"
                    headers = {"Authorization": f"Bearer {self._api_key}"}
                    body = {
                        "model": self._model,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                    resp = httpx.post(url, json=body, headers=headers, timeout=300.0)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                raise ValueError(f"不支持的 provider: {self._provider}")
            except ValueError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries:
                    _time.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_resilience.py::TestCallLlmRetry -v
```

预期: 2 PASSED

- [ ] **Step 5: 提交**

```bash
git add govdoc/harness/judge.py tests/unit/test_harness_resilience.py
git commit -m "fix(harness): _call_llm 增加重试，瞬时网络错误不再立即失败"
```

---

### Task 7: Shell 脚本 trap + 日志持久化

**Files:**
- Modify: `scripts/harness_pipeline.sh`

- [ ] **Step 1: 替换 shell 脚本全部内容**

```bash
#!/usr/bin/env bash
# L1 管道 harness 评估 — 直接调用 run_extract / run_audit + HarnessJudge
set -euo pipefail
cd "$(dirname "$0")/.."

LOG_DIR="results/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/harness_pipeline_$(date +%Y%m%d_%H%M%S).log"

cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "=== L1 失败 (exit=$exit_code) ===" | tee -a "$LOG_FILE"
    fi
    echo "结束时间: $(date)" | tee -a "$LOG_FILE"
    echo "日志文件: $LOG_FILE"
}
trap cleanup EXIT

export no_proxy="110.42.53.85,localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="110.42.53.85,localhost,127.0.0.1,${NO_PROXY:-}"

echo "=== L1 Pipeline Eval ===" | tee "$LOG_FILE"
echo "开始时间: $(date)" | tee -a "$LOG_FILE"

conda run -n govdoc-auditor-v3 python -m govdoc.harness.pipeline_eval \
    --manifest scripts/fixtures/harness_manifest.yaml \
    --project-root . \
    --rubric-dir scripts/rubrics \
    --db-path results/harness.db \
    2>&1 | tee -a "$LOG_FILE"

echo "=== L1 完成 ===" | tee -a "$LOG_FILE"
```

- [ ] **Step 2: 验证语法**

```bash
bash -n scripts/harness_pipeline.sh && echo "语法OK"
```

预期: `语法OK`

- [ ] **Step 3: 提交**

```bash
git add scripts/harness_pipeline.sh
git commit -m "fix(harness): shell 脚本添加 trap + 日志持久化到 results/logs/"
```

---

### Task 8: `session.query()` → `session.exec(select())`

**Files:**
- Modify: `govdoc/harness/pipeline_eval.py:358-469`

- [ ] **Step 1: 修改 `_ensure_rule_source`（第 358-374 行）**

```python
def _ensure_rule_source(rule: Any, session: Any) -> str:
    """确保法规已入库，返回 rule_source_id。"""
    from govdoc.db.models import RuleSource
    from sqlmodel import select

    existing = session.exec(select(RuleSource).where(RuleSource.title == rule.name)).first()
    if existing:
        return existing.id

    rs = RuleSource(
        title=rule.name,
        source_path=str(rule.path),
        rule_library_entry_id="harness-fixture",
    )
    session.add(rs)
    session.commit()
    session.refresh(rs)
    return rs.id
```

- [ ] **Step 2: 修改 `_ensure_audit_run`（第 377-434 行）**

```python
def _ensure_audit_run(proj: Any, session: Any, manifest: Any) -> str:
    """确保审核运行已创建（含金标准审核点导入），返回 audit_run_id。"""
    from govdoc.db.models import AuditRun, CheckpointFinal, Project, TenderDoc
    from govdoc.parsers.checkpoint_import import parse_checkpoint_file
    from sqlmodel import select

    project = session.exec(select(Project).where(Project.name == proj.name)).first()
    if not project:
        project = Project(name=proj.name, created_by="harness")
        session.add(project)
        session.commit()
        session.refresh(project)

    tender_doc = session.exec(select(TenderDoc).where(TenderDoc.project_id == project.id)).first()
    if not tender_doc:
        tender_doc = TenderDoc(
            project_id=project.id,
            filename=Path(proj.tender_doc).name,
            storage_path=str(proj.tender_doc),
            markdown_path="",
            qmd_collection="",
        )
        session.add(tender_doc)
        session.commit()
        session.refresh(tender_doc)

    cp_ids: list[str] = []
    existing_cps = session.exec(select(CheckpointFinal).limit(1)).first()
    if existing_cps:
        all_cps = session.exec(select(CheckpointFinal)).all()
        cp_ids = [c.id for c in all_cps]
    else:
        for cp_fixture in manifest.checkpoints:
            cp_path = Path(cp_fixture.path)
            if not cp_path.exists():
                logger.warning("审核点文件不存在: %s", cp_path)
                continue
            checkpoints, skipped = parse_checkpoint_file(cp_path)
            logger.info("导入审核点: %s → %d 条, 跳过 %d 行", cp_fixture.name, len(checkpoints), len(skipped))
            for gov_cp in checkpoints:
                cf = CheckpointFinal(
                    payload_json=gov_cp.model_dump_json(),
                    approved_by="harness:golden-standard",
                )
                session.add(cf)
                cp_ids.append(cf.id)
            session.commit()

    audit_run = AuditRun(
        project_id=project.id,
        tender_doc_id=tender_doc.id,
        checkpoint_final_ids=json.dumps(cp_ids),
        status="pending",
    )
    session.add(audit_run)
    session.commit()
    session.refresh(audit_run)
    logger.info("AuditRun %s 创建完成, %d 个审核点", audit_run.id, len(cp_ids))
    return audit_run.id
```

- [ ] **Step 3: 修改 `_load_extract_output`（第 437-448 行）**

```python
def _load_extract_output(extract_run: Any, session: Any) -> list[dict[str, Any]]:
    """从 ExtractRun 加载审核点结果为 dict 列表。"""
    from govdoc.db.models import CheckpointFinal
    from sqlmodel import select

    cps = session.exec(
        select(CheckpointFinal).where(CheckpointFinal.rule_source_id == extract_run.rule_source_id)
    ).all()
    results = []
    for cp in cps:
        payload = (
            json.loads(cp.payload_json) if isinstance(cp.payload_json, str) else cp.payload_json
        )
        results.append(payload)
    return results
```

- [ ] **Step 4: 修改 `_load_audit_findings`（第 451-469 行）**

```python
def _load_audit_findings(audit_run: Any, session: Any) -> list[dict[str, Any]]:
    """从 AuditRun 加载审核发现为 dict 列表。"""
    from govdoc.db.models import AuditPointRun
    from sqlmodel import select

    point_runs = session.exec(
        select(AuditPointRun).where(AuditPointRun.audit_run_id == audit_run.id)
    ).all()
    results = []
    for pr in point_runs:
        if pr.finding_json:
            finding = (
                json.loads(pr.finding_json) if isinstance(pr.finding_json, str) else pr.finding_json
            )
            finding["point_run_id"] = pr.id
            finding["checkpoint_id"] = pr.checkpoint_final_id
            finding["duration_s"] = (
                (pr.completed_at - pr.created_at).total_seconds() if pr.completed_at else 0
            )
            finding["status"] = pr.status
            results.append(finding)
    return results
```

- [ ] **Step 5: 运行全部 harness 测试**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_pipeline_eval.py tests/unit/test_harness_resilience.py -v
```

预期: 全部 PASSED

- [ ] **Step 6: 提交**

```bash
git add govdoc/harness/pipeline_eval.py
git commit -m "refactor(harness): session.query() → session.exec(select()) 对齐 SQLModel 2.0"
```

---

### Task 9: 全量回归 + 冒烟测试

- [ ] **Step 1: 运行全部 harness 单测**

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_harness_log.py tests/unit/test_harness_handler.py tests/unit/test_harness_schemas.py tests/unit/test_harness_manifest.py tests/unit/test_pipeline_eval.py tests/unit/test_api_eval.py tests/unit/test_harness_resilience.py -v
```

预期: 全部 PASSED

- [ ] **Step 2: 代码质量检查**

```bash
conda run -n govdoc-auditor-v3 ruff check govdoc/harness/ tests/unit/test_harness_resilience.py --fix
conda run -n govdoc-auditor-v3 ruff format govdoc/harness/ tests/unit/test_harness_resilience.py
```

预期: 无错误

- [ ] **Step 3: 冒烟测试 — 用不存在的 manifest 运行 L1**

```bash
conda run -n govdoc-auditor-v3 python -m govdoc.harness.pipeline_eval \
    --manifest nonexistent_file.yaml \
    --db-path /tmp/smoke_harness.db || true

sqlite3 /tmp/smoke_harness.db "SELECT run_id, status, finished_at FROM _runs;"
sqlite3 /tmp/smoke_harness.db "SELECT event_type, substr(payload, 1, 200) FROM _events ORDER BY id DESC LIMIT 5;"
```

预期:
- `_runs.status` = `failed` 或 `crashed`
- `_events` 有 `CRITICAL` 类型记录

- [ ] **Step 4: 清理**

```bash
rm -f /tmp/smoke_harness.db
```
