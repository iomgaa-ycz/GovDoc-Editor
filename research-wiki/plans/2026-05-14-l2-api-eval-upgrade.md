# L2 API 评估升级：Bug 修复 + L1 记录功能迁移

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 L2 api_eval.py 中的 bug，并将 L1 的所有记录能力（pipeline_runs / extract_results / audit_results / quality_scores）迁移到 L2，使 L2 成为完整的端到端评估，未来可替代 L1。

**Architecture:** L2 通过 HTTP API 触发 pipeline，轮询等待异步完成，然后通过 API 查询结果并记录到 harness.db 的同一套表。语义评估（quality_scores）复用 L1 已有的 `_run_semantic_evaluations`。新增 `_poll_until_done` 通用轮询函数处理所有异步端点。

**Tech Stack:** Python 3.11 / httpx / FastAPI / SQLite / HarnessLog / HarnessJudge

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `govdoc/harness/api_eval.py` | L2 主模块 | 大幅修改 |
| `govdoc/harness/pipeline_eval.py` | L1 模块 — 提取 `record_*` 和 `_run_semantic_evaluations` 供 L2 复用 | 不修改（直接 import） |
| `tests/unit/test_api_eval.py` | L2 单测 | 修改：新增 `call_endpoint` 混合表单测试 + `_poll_until_done` 测试 |
| `scripts/harness_api.sh` | L2 启动脚本 | 修改：增加超时和环境变量 |

**关键设计决策：**
- `record_pipeline_run` / `record_extract_results` / `record_audit_results` / `record_quality_score` / `evaluate_dimension` / `_run_semantic_evaluations` / `load_rubric` 已在 `pipeline_eval.py` 中定义，L2 直接 `from govdoc.harness.pipeline_eval import ...` 复用，不复制代码。
- `EndpointSpec` 新增 `form_data: dict` 字段，区分 JSON body 和 multipart form data。
- `call_endpoint` 修改：当 `spec.files` 和 `spec.form_data` 同时存在时，用 `data=` + `files=` 发送混合 multipart 请求。
- 新增 `_poll_until_done` 函数：通用轮询，给定 URL + 终态字段 + 终态值集合 + 超时。
- L2 的完整流程新增 Phase 5（等待 Pipeline A）、Phase 7（创建+等待 Audit Run）、Phase 8（记录审核结果）、Phase 9（语义评估）。

---

### Task 1: 修复 `EndpointSpec` 和 `call_endpoint` — 支持 files + form_data 混合发送

**Files:**
- Modify: `govdoc/harness/api_eval.py:23-48` (EndpointSpec dataclass)
- Modify: `govdoc/harness/api_eval.py:116-196` (call_endpoint function)
- Test: `tests/unit/test_api_eval.py`

- [ ] **Step 1: 写失败测试 — `call_endpoint` 发送 files + form_data**

在 `tests/unit/test_api_eval.py` 末尾添加：

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestCallEndpointMixedForm:
    """测试 call_endpoint 同时发送 files + form_data。"""

    def test_mixed_form_data_and_files(self, tmp_path: Path) -> None:
        """files + form_data 应使用 data= 和 files= 参数。"""
        db_path = str(tmp_path / "h.db")

        mock_resp = MagicMock()
        mock_resp.status_code = 202
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"rule_source_id": "rs1", "extract_run_id": "er1"}
        mock_resp.content = b'{"rule_source_id":"rs1"}'

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        spec = EndpointSpec(
            method="POST",
            path="/api/v1/rules/upload",
            expected_status=202,
            description="上传法规",
            form_data={"title": "测试法规"},
            files={"file": ("test.doc", b"fake content")},
        )

        with HarnessLog(db_path=db_path, run_id="mix-1") as log:
            create_all_tables(log)
            status, data = asyncio.run(
                call_endpoint(mock_client, spec, log)
            )

        assert status == 202
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "data" in call_kwargs.kwargs
        assert "files" in call_kwargs.kwargs
        assert call_kwargs.kwargs["data"]["title"] == "测试法规"
```

- [ ] **Step 2: 运行测试确认失败**

运行: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_api_eval.py::TestCallEndpointMixedForm -v`
预期: FAIL — `EndpointSpec` 没有 `form_data` 字段

- [ ] **Step 3: 修改 `EndpointSpec` 添加 `form_data` 字段**

修改 `govdoc/harness/api_eval.py`，在 `EndpointSpec` dataclass 中添加：

```python
@dataclass
class EndpointSpec:
    # ... 现有字段不变 ...
    method: str
    path: str
    expected_status: int
    description: str
    body: dict[str, Any] | None = None
    form_data: dict[str, Any] | None = None  # 新增：multipart form 字段
    files: dict[str, Any] | None = None
    response_model: Type[BaseModel] | None = None
    is_async: bool = False
    path_params: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: 修改 `call_endpoint` 支持混合发送**

修改 `govdoc/harness/api_eval.py` 中 `call_endpoint` 函数的 POST 分支（约 line 139-143）：

```python
        elif spec.method == "POST":
            if spec.files:
                resp = await client.post(
                    path, files=spec.files, data=spec.form_data or {}
                )
            elif spec.body:
                resp = await client.post(path, json=spec.body)
            else:
                resp = await client.post(path)
```

- [ ] **Step 5: 运行测试确认通过**

运行: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_api_eval.py -v`
预期: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add govdoc/harness/api_eval.py tests/unit/test_api_eval.py
git commit -m "fix(harness): EndpointSpec 支持 form_data + files 混合发送"
```

---

### Task 2: 修复 `/rules/upload` 调用 — 补充 title 字段

**Files:**
- Modify: `govdoc/harness/api_eval.py:292-307` (rule upload phase)

- [ ] **Step 1: 修改 rule upload 的 EndpointSpec**

在 `run_api_eval` 的 Phase 4（规则上传）中，修改 EndpointSpec：

```python
            # Phase 4: 规则上传
            rule_upload_results: list[dict[str, Any]] = []
            for rule in manifest.rules:
                rule_path = Path(rule.path)
                if rule_path.exists():
                    status, resp_data = await call_endpoint(
                        client,
                        EndpointSpec(
                            method="POST",
                            path="/api/v1/rules/upload",
                            expected_status=202,
                            description=f"上传法规: {rule.name}",
                            form_data={"title": rule.name},
                            files={"file": (rule_path.name, rule_path.read_bytes())},
                            is_async=True,
                        ),
                        log,
                    )
                    if resp_data:
                        rule_upload_results.append(resp_data)
```

- [ ] **Step 2: 运行全量单测确认无回退**

运行: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_api_eval.py -v`
预期: 全部 PASS

- [ ] **Step 3: 提交**

```bash
git add govdoc/harness/api_eval.py
git commit -m "fix(harness): L2 rules/upload 补充 title 表单字段"
```

---

### Task 3: 新增 `_poll_until_done` 通用轮询函数

**Files:**
- Modify: `govdoc/harness/api_eval.py` (新增函数)
- Test: `tests/unit/test_api_eval.py`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_api_eval.py` 末尾添加：

```python
from govdoc.harness.api_eval import _poll_until_done


class TestPollUntilDone:
    """测试通用轮询。"""

    def test_polls_until_terminal(self, tmp_path: Path) -> None:
        """轮询直到状态变为终态。"""
        db_path = str(tmp_path / "h.db")
        call_count = 0

        async def mock_get(path: str):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.headers = {"content-type": "application/json"}
            resp.content = b'{}'
            if call_count < 3:
                resp.status_code = 200
                resp.json.return_value = {"status": "running"}
            else:
                resp.status_code = 200
                resp.json.return_value = {"status": "draft_ready", "id": "run1"}
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get

        with HarnessLog(db_path=db_path, run_id="poll-1") as log:
            create_all_tables(log)
            result = asyncio.run(
                _poll_until_done(
                    mock_client,
                    "/api/v1/audit/runs/run1",
                    status_field="status",
                    terminal_statuses={"draft_ready", "completed", "failed", "waiting_retry"},
                    log=log,
                    poll_interval=0.01,
                    timeout_s=5.0,
                )
            )

        assert result is not None
        assert result["status"] == "draft_ready"
        assert call_count == 3

    def test_returns_none_on_timeout(self, tmp_path: Path) -> None:
        """超时返回 None。"""
        db_path = str(tmp_path / "h.db")

        async def mock_get(path: str):
            resp = MagicMock()
            resp.status_code = 200
            resp.headers = {"content-type": "application/json"}
            resp.content = b'{}'
            resp.json.return_value = {"status": "running"}
            return resp

        mock_client = AsyncMock()
        mock_client.get = mock_get

        with HarnessLog(db_path=db_path, run_id="poll-2") as log:
            create_all_tables(log)
            result = asyncio.run(
                _poll_until_done(
                    mock_client,
                    "/some/path",
                    status_field="status",
                    terminal_statuses={"done"},
                    log=log,
                    poll_interval=0.01,
                    timeout_s=0.05,
                )
            )

        assert result is None
```

- [ ] **Step 2: 运行测试确认失败**

运行: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_api_eval.py::TestPollUntilDone -v`
预期: FAIL — `_poll_until_done` 不存在

- [ ] **Step 3: 实现 `_poll_until_done`**

在 `govdoc/harness/api_eval.py` 中（`call_endpoint` 之后）添加：

```python
async def _poll_until_done(
    client: Any,
    path: str,
    *,
    status_field: str = "status",
    terminal_statuses: set[str],
    log: HarnessLog,
    poll_interval: float = 5.0,
    timeout_s: float = 600.0,
) -> dict[str, Any] | None:
    """轮询 GET 端点直到状态进入终态或超时。

    参数:
        client: httpx.AsyncClient。
        path: 轮询的 GET 路径。
        status_field: 响应 JSON 中的状态字段名。
        terminal_statuses: 终态值集合。
        log: HarnessLog（记录每次轮询到 api_calls）。
        poll_interval: 轮询间隔秒数。
        timeout_s: 超时秒数。

    返回:
        终态响应 JSON，超时返回 None。
    """
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            resp = await client.get(path)
            content_type = resp.headers.get("content-type", "")
            data = resp.json() if content_type.startswith("application/json") else None

            record_api_call(
                log,
                method="GET",
                path=path,
                status_code=resp.status_code,
                duration_ms=(time.time() - t0) * 1000,
                response_size=len(resp.content),
            )

            if data and data.get(status_field) in terminal_statuses:
                return data
        except Exception:
            pass

        await asyncio.sleep(poll_interval)

    logger.warning("轮询超时: %s (%.0fs)", path, timeout_s)
    return None
```

- [ ] **Step 4: 运行测试确认通过**

运行: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_api_eval.py -v`
预期: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add govdoc/harness/api_eval.py tests/unit/test_api_eval.py
git commit -m "feat(harness): L2 新增 _poll_until_done 通用异步轮询"
```

---

### Task 4: Pipeline A 端到端 — 等待 extract run 完成 + 记录 extract_results

**Files:**
- Modify: `govdoc/harness/api_eval.py` — `run_api_eval` Phase 4 之后新增 Phase 5

- [ ] **Step 1: 在 Phase 4（rule upload）之后添加 Phase 5（等待 Pipeline A + 记录）**

```python
            # Phase 5: 等待 Pipeline A 完成 + 记录
            from govdoc.harness.pipeline_eval import record_pipeline_run, record_extract_results

            pipeline_timeout = float(os.environ.get("HARNESS_PIPELINE_TIMEOUT", "1800"))
            for upload_resp in rule_upload_results:
                rule_source_id = upload_resp.get("rule_source_id", "")
                extract_run_id = upload_resp.get("extract_run_id", "")
                if not extract_run_id:
                    continue

                t0 = time.time()
                poll_path = f"/api/v1/rules/{rule_source_id}/extract-runs/{extract_run_id}/status"
                final = await _poll_until_done(
                    client,
                    poll_path,
                    status_field="status",
                    terminal_statuses={"draft_ready", "completed", "failed"},
                    log=log,
                    poll_interval=10.0,
                    timeout_s=pipeline_timeout,
                )

                status = final["status"] if final else "timeout"
                error = (final.get("error") if final else "Pipeline A 超时") or None
                record_pipeline_run(
                    log,
                    pipeline="A",
                    project_name=upload_resp.get("rule_source_id", ""),
                    input_file="via API",
                    status=status,
                    duration_s=time.time() - t0,
                    total_tokens=0,
                    error=error,
                )

                # 通过 checkpoints API 获取 auto-promote 的审核点
                if status in ("draft_ready", "completed"):
                    _, cp_list = await call_endpoint(
                        client,
                        EndpointSpec(
                            method="GET",
                            path="/api/v1/checkpoints",
                            expected_status=200,
                            description="获取抽取审核点",
                        ),
                        log,
                    )
                    if cp_list:
                        extract_cps = []
                        for cp in cp_list:
                            if cp.get("approved_by") == "system:auto-promote":
                                payload = json.loads(cp.get("payload_json", "{}"))
                                extract_cps.append(payload)
                        if extract_cps:
                            record_extract_results(log, extract_cps)
```

- [ ] **Step 2: 在文件顶部添加 `import os`**（如果还没有的话）

- [ ] **Step 3: 运行全量单测确认无回退**

运行: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_api_eval.py -v`
预期: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add govdoc/harness/api_eval.py
git commit -m "feat(harness): L2 等待 Pipeline A 完成并记录 extract_results"
```

---

### Task 5: Pipeline B 端到端 — 创建 Audit Run + 等待完成 + 记录 audit_results

**Files:**
- Modify: `govdoc/harness/api_eval.py` — 新增 Phase 7（创建 audit run）+ Phase 8（记录结果）

- [ ] **Step 1: 在 Phase 6（list 端点）之后添加 Phase 7 + Phase 8**

需要从前面的 phase 收集 `project_id`、`tender_doc_id`、`checkpoint_ids`。修改 Phase 3（tender upload）和 Phase 6（checkpoint import）保存响应数据。

在 Phase 3 tender upload 部分，保存 `tender_doc_id`：

```python
            # Phase 3: 文书上传（修改：保存 tender_doc_id）
            tender_doc_ids: list[str] = []
            for proj in manifest.projects:
                tender_path = Path(proj.tender_doc)
                if tender_path.exists():
                    status, resp = await call_endpoint(
                        client,
                        EndpointSpec(
                            method="POST",
                            path="/api/v1/projects/{project_id}/tender-doc",
                            expected_status=201,
                            description=f"上传文书: {proj.name}",
                            path_params={"project_id": project_id},
                            files={"file": (tender_path.name, tender_path.read_bytes())},
                        ),
                        log,
                    )
                    if resp:
                        tender_doc_ids.append(resp.get("id", ""))
```

在 Phase 5 checkpoint import 部分，保存 `checkpoint_ids`：

```python
            # Phase 5: 审核点导入（修改：保存 checkpoint_ids）
            imported_checkpoint_ids: list[str] = []
            for cp in manifest.checkpoints:
                cp_path = Path(cp.path)
                if cp_path.exists():
                    status, resp = await call_endpoint(
                        client,
                        EndpointSpec(
                            method="POST",
                            path="/api/v1/checkpoints/import",
                            expected_status=200,
                            description=f"导入审核点: {cp.name}",
                            files={"file": (cp_path.name, cp_path.read_bytes())},
                        ),
                        log,
                    )
                    if resp:
                        max_cp = int(os.environ.get("HARNESS_MAX_CHECKPOINTS", "0"))
                        cps = resp.get("checkpoints", [])
                        ids = [c["id"] for c in cps if c.get("id")]
                        if max_cp > 0:
                            ids = ids[:max_cp]
                        imported_checkpoint_ids.extend(ids)
```

然后添加 Phase 7 + Phase 8：

```python
            # Phase 7: 创建 Audit Run + 等待 Pipeline B 完成
            from govdoc.harness.pipeline_eval import record_audit_results

            audit_terminal = {"draft_ready", "completed", "partial_ready", "failed", "waiting_retry"}
            completed_audit_run_ids: list[str] = []

            for idx, proj in enumerate(manifest.projects):
                if idx >= len(tender_doc_ids) or not imported_checkpoint_ids:
                    continue

                t0 = time.time()
                status, audit_resp = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="POST",
                        path="/api/v1/audit/runs",
                        expected_status=202,
                        description=f"创建审核: {proj.name}",
                        body={
                            "project_id": project_id,
                            "tender_doc_id": tender_doc_ids[idx],
                            "checkpoint_ids": imported_checkpoint_ids,
                        },
                    ),
                    log,
                )

                if not audit_resp:
                    continue
                audit_run_id = audit_resp.get("audit_run_id", "")

                # 轮询等待审核完成
                final = await _poll_until_done(
                    client,
                    f"/api/v1/audit/runs/{audit_run_id}/progress",
                    status_field="status",
                    terminal_statuses=audit_terminal,
                    log=log,
                    poll_interval=10.0,
                    timeout_s=pipeline_timeout,
                )

                audit_status = final["status"] if final else "timeout"
                record_pipeline_run(
                    log,
                    pipeline="B",
                    project_name=proj.name,
                    input_file=str(proj.tender_doc),
                    status=audit_status,
                    duration_s=time.time() - t0,
                    total_tokens=0,
                    error=None if audit_status in ("draft_ready", "completed") else audit_status,
                )

                if final and audit_status in ("draft_ready", "completed", "partial_ready"):
                    completed_audit_run_ids.append(audit_run_id)

            # Phase 8: 记录审核发现
            for arid in completed_audit_run_ids:
                _, progress = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path=f"/api/v1/audit/runs/{arid}/progress",
                        expected_status=200,
                        description="获取审核进度",
                    ),
                    log,
                )
                if not progress:
                    continue
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
```

- [ ] **Step 2: 运行全量单测确认无回退**

运行: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_api_eval.py -v`
预期: 全部 PASS

- [ ] **Step 3: 提交**

```bash
git add govdoc/harness/api_eval.py
git commit -m "feat(harness): L2 端到端 Pipeline B — 创建 audit run + 轮询 + 记录 audit_results"
```

---

### Task 6: 语义评估迁移 — 复用 L1 的 `_run_semantic_evaluations`

**Files:**
- Modify: `govdoc/harness/api_eval.py` — 新增 Phase 9

- [ ] **Step 1: 在 Phase 8 之后添加 Phase 9（语义评估）**

```python
            # Phase 9: 语义评估（复用 L1）
            rubric_dir = os.environ.get("HARNESS_RUBRIC_DIR", "scripts/rubrics")
            from govdoc.harness.pipeline_eval import _run_semantic_evaluations
            logger.info("开始语义评估")
            _run_semantic_evaluations(log, rubric_dir, project_root)
```

- [ ] **Step 2: 给 `run_api_eval` 添加 `rubric_dir` 参数**

修改函数签名：

```python
async def run_api_eval(
    *,
    base_url: str = "http://localhost:8000",
    manifest_path: str,
    project_root: str,
    rubric_dir: str = "scripts/rubrics",
    db_path: str = "results/harness.db",
) -> str:
```

修改 CLI argparse（文件末尾）：

```python
    parser.add_argument("--rubric-dir", default="scripts/rubrics")
```

以及调用处：

```python
    run_id = asyncio.run(
        run_api_eval(
            base_url=args.base_url,
            manifest_path=args.manifest,
            project_root=args.project_root,
            rubric_dir=args.rubric_dir,
            db_path=args.db_path,
        )
    )
```

- [ ] **Step 3: 运行全量单测确认无回退**

运行: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/ -v`
预期: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add govdoc/harness/api_eval.py
git commit -m "feat(harness): L2 语义评估 — 复用 L1 的 _run_semantic_evaluations"
```

---

### Task 7: 更新 `scripts/harness_api.sh` + 清理

**Files:**
- Modify: `scripts/harness_api.sh`

- [ ] **Step 1: 更新启动脚本**

```bash
#!/usr/bin/env bash
# L2 API harness 评估 — 端到端（含 Pipeline A/B + 语义评估）
set -euo pipefail
cd "$(dirname "$0")/.."

BASE_URL="${HARNESS_API_URL:-http://localhost:8000}"
export no_proxy="110.42.53.85,localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="110.42.53.85,localhost,127.0.0.1,${NO_PROXY:-}"

LOG_DIR="results/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/harness_api_$(date +%Y%m%d_%H%M%S).log"

echo "=== L2 API Eval ===" | tee "$LOG_FILE"
echo "目标: $BASE_URL" | tee -a "$LOG_FILE"
echo "开始时间: $(date)" | tee -a "$LOG_FILE"

# 检查服务是否可达
if ! curl -sf "${BASE_URL}/healthz" > /dev/null 2>&1; then
    echo "错误: FastAPI 服务不可达 ($BASE_URL/healthz)" | tee -a "$LOG_FILE"
    echo "请先启动: conda run -n govdoc-auditor-v3 uvicorn govdoc.api.main:app --port 8000" | tee -a "$LOG_FILE"
    exit 1
fi

conda run -n govdoc-auditor-v3 python -m govdoc.harness.api_eval \
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
git commit -m "docs(harness): 更新 L2 启动脚本，增加 rubric-dir + 日志"
```

---

## 验收标准

1. `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/ -v` 全部通过
2. 启动 FastAPI 后运行 `scripts/harness_api.sh`，L2 完整跑通：
   - `pipeline_runs` 表有 Pipeline A + Pipeline B 的记录
   - `extract_results` 表有抽取的审核点
   - `audit_results` 表有审核发现
   - `quality_scores` 表有 19 维语义评估
   - `api_calls` + `api_contracts` 表有 HTTP 调用和契约验证
3. L2 的 `_runs` 状态为 `completed`，无 ERROR 事件
