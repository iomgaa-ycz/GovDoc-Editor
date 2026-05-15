"""L2 API 评估：httpx 调全部端点 + 契约验证 + 性能指标。"""

from __future__ import annotations

import asyncio
import argparse
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Type

from pydantic import BaseModel, ValidationError

from govdoc.harness.log import HarnessLog
from govdoc.harness.schemas import create_all_tables

logger = logging.getLogger(__name__)


@dataclass
class EndpointSpec:
    """单个 API 端点的测试规格。

    参数:
        method: HTTP 方法。
        path: 端点路径（可含 {param} 占位符）。
        expected_status: 预期状态码。
        description: 端点描述。
        body: 请求体 JSON。
        form_data: 表单数据。
        files: 上传文件字典。
        response_model: 响应 Pydantic 模型（可选）。
        is_async: 是否为异步端点。
        path_params: 路径参数替换字典。
    """

    method: str
    path: str
    expected_status: int
    description: str
    body: dict[str, Any] | None = None
    form_data: dict[str, Any] | None = None
    files: dict[str, Any] | None = None
    response_model: Type[BaseModel] | None = None
    is_async: bool = False
    path_params: dict[str, str] = field(default_factory=dict)


def record_api_call(
    log: HarnessLog,
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    request_size: int = 0,
    response_size: int = 0,
    error: str | None = None,
) -> None:
    """记录一次 HTTP 调用到 api_calls 表。"""
    log.insert(
        "api_calls",
        {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "request_size": request_size,
            "response_size": response_size,
            "error": error,
        },
    )


def record_api_contract(
    log: HarnessLog,
    *,
    endpoint: str,
    check_name: str,
    passed: bool,
    detail: str = "",
) -> None:
    """记录一次契约检查到 api_contracts 表。"""
    log.insert(
        "api_contracts",
        {
            "endpoint": endpoint,
            "check_name": check_name,
            "passed": 1 if passed else 0,
            "detail": detail,
        },
    )


def check_response_schema(
    data: dict[str, Any],
    model: Type[BaseModel],
) -> tuple[bool, str]:
    """校验响应 body 是否符合 Pydantic model。

    参数:
        data: 响应数据字典。
        model: Pydantic 模型类。

    返回:
        (passed, detail) 元组。
    """
    try:
        model.model_validate(data)
        return True, ""
    except ValidationError as e:
        return False, str(e)


async def call_endpoint(
    client: Any,
    spec: EndpointSpec,
    log: HarnessLog,
) -> tuple[int, dict[str, Any] | None]:
    """调用单个端点并记录。

    参数:
        client: httpx.AsyncClient 实例。
        spec: 端点规格。
        log: HarnessLog 实例。

    返回:
        (status_code, response_json) 元组。
    """
    path = spec.path
    for key, val in spec.path_params.items():
        path = path.replace(f"{{{key}}}", val)

    t0 = time.time()
    try:
        if spec.method == "GET":
            resp = await client.get(path)
        elif spec.method == "POST":
            if spec.files:
                resp = await client.post(path, files=spec.files, data=spec.form_data or {})
            elif spec.body:
                resp = await client.post(path, json=spec.body)
            else:
                resp = await client.post(path)
        elif spec.method == "PUT":
            resp = await client.put(path, json=spec.body)
        elif spec.method == "DELETE":
            resp = await client.delete(path)
        else:
            raise ValueError(f"不支持的 HTTP 方法: {spec.method}")

        duration_ms = (time.time() - t0) * 1000
        content_type = resp.headers.get("content-type", "")
        response_data = resp.json() if content_type.startswith("application/json") else None

        record_api_call(
            log,
            method=spec.method,
            path=path,
            status_code=resp.status_code,
            duration_ms=duration_ms,
            request_size=len(json.dumps(spec.body).encode()) if spec.body else 0,
            response_size=len(resp.content),
        )

        record_api_contract(
            log,
            endpoint=f"{spec.method} {spec.path}",
            check_name="status_code",
            passed=resp.status_code == spec.expected_status,
            detail=f"expected={spec.expected_status}, actual={resp.status_code}",
        )

        if spec.response_model and response_data:
            passed, detail = check_response_schema(response_data, spec.response_model)
            record_api_contract(
                log,
                endpoint=f"{spec.method} {spec.path}",
                check_name="response_schema",
                passed=passed,
                detail=detail,
            )

        return resp.status_code, response_data

    except Exception as exc:
        duration_ms = (time.time() - t0) * 1000
        record_api_call(
            log,
            method=spec.method,
            path=path,
            status_code=0,
            duration_ms=duration_ms,
            error=str(exc),
        )
        logger.exception("调用 %s %s 失败", spec.method, path)
        return 0, None


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
            poll_t0 = time.time()
            resp = await client.get(path)
            content_type = resp.headers.get("content-type", "")
            data = resp.json() if content_type.startswith("application/json") else None

            record_api_call(
                log,
                method="GET",
                path=path,
                status_code=resp.status_code,
                duration_ms=(time.time() - poll_t0) * 1000,
                response_size=len(resp.content),
            )

            if data and data.get(status_field) in terminal_statuses:
                return data
        except Exception:
            pass

        await asyncio.sleep(poll_interval)

    logger.warning("轮询超时: %s (%.0fs)", path, timeout_s)
    return None


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
    max_checkpoints = int(os.environ.get("HARNESS_MAX_CHECKPOINTS", "0"))
    pipeline_timeout = float(os.environ.get("HARNESS_PIPELINE_TIMEOUT", "7200"))

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
            await call_endpoint(
                client,
                EndpointSpec(
                    method="GET",
                    path="/healthz",
                    expected_status=200,
                    description="健康检查",
                ),
                log,
            )

            await call_endpoint(
                client,
                EndpointSpec(
                    method="GET",
                    path="/api/v1/projects",
                    expected_status=200,
                    description="列出项目",
                ),
                log,
            )

            await call_endpoint(
                client,
                EndpointSpec(
                    method="GET",
                    path="/api/v1/rules",
                    expected_status=200,
                    description="列出法规",
                ),
                log,
            )

            await call_endpoint(
                client,
                EndpointSpec(
                    method="GET",
                    path="/api/v1/checkpoints",
                    expected_status=200,
                    description="列出审核点",
                ),
                log,
            )

            # ── Phase 2: Pipeline A — per rule ──
            for rule in manifest.rules:
                rule_path = Path(rule.path)
                if not rule_path.exists():
                    logger.warning("法规文件不存在: %s", rule_path)
                    continue

                t0 = time.time()
                status, resp_data = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="POST",
                        path="/api/v1/rules/upload",
                        expected_status=202,
                        description=f"上传法规: {rule.name}",
                        form_data={"title": rule.name},
                        files={"file": (rule_path.name, rule_path.read_bytes())},
                    ),
                    log,
                )

                if not resp_data:
                    continue
                rule_source_id = resp_data.get("rule_source_id", "")
                extract_run_id = resp_data.get("extract_run_id", "")
                if not extract_run_id:
                    continue

                poll_path = f"/api/v1/rules/{rule_source_id}/extract-runs/{extract_run_id}/status"
                final = await _poll_until_done(
                    client,
                    poll_path,
                    status_field="status",
                    terminal_statuses={
                        "draft_ready",
                        "completed",
                        "failed",
                        "interrupted",
                        "cancelled",
                    },
                    log=log,
                    poll_interval=10.0,
                    timeout_s=pipeline_timeout,
                )
                pa_status = final["status"] if final else "timeout"
                record_pipeline_run(
                    log,
                    pipeline="A",
                    project_name=rule.name,
                    input_file=rule.path,
                    status=pa_status,
                    duration_s=time.time() - t0,
                    total_tokens=0,
                    error=(final.get("error") if final else "Pipeline A 超时") or None,
                )

                if pa_status in ("draft_ready", "completed"):
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
                        extract_cps = [
                            json.loads(cp.get("payload_json", "{}"))
                            for cp in cp_list
                            if cp.get("approved_by") == "system:auto-promote"
                        ]
                        if extract_cps:
                            record_extract_results(log, extract_cps)
                            # 收集 agent 轨迹证据
                            from govdoc.harness.pipeline_eval import (
                                collect_workspace_evidence,
                                record_agent_trajectory,
                            )

                            ws_evidence = collect_workspace_evidence(
                                workspace_dir=Path(f"data/.govdoc/workspaces/{extract_run_id}"),
                            )
                            if ws_evidence["plan_json"]:
                                record_agent_trajectory(
                                    log,
                                    pipeline="A",
                                    run_id=extract_run_id,
                                    plan_json=ws_evidence["plan_json"],
                                    workspace_files=ws_evidence["workspace_files"],
                                    phase_details=[],
                                )

            # ── Phase 3: 导入金标准审核点 ──
            imported_checkpoint_ids: list[str] = []
            for cp_fixture in manifest.checkpoints:
                cp_path = Path(cp_fixture.path)
                if not cp_path.exists():
                    continue
                status, resp = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="POST",
                        path="/api/v1/checkpoints/import",
                        expected_status=200,
                        description=f"导入审核点: {cp_fixture.name}",
                        files={"file": (cp_path.name, cp_path.read_bytes())},
                    ),
                    log,
                )
                if resp:
                    ids = [c["id"] for c in resp.get("checkpoints", []) if c.get("id")]
                    imported_checkpoint_ids.extend(ids)

            # 截断审核点数量
            if max_checkpoints > 0 and len(imported_checkpoint_ids) > max_checkpoints:
                imported_checkpoint_ids = imported_checkpoint_ids[:max_checkpoints]
                logger.info("审核点截断为 %d 个", max_checkpoints)

            # ── Phase 4: Checkpoint CRUD 测试 ──
            # 用合法数据测试 PUT + DELETE，不影响 imported 列表
            if imported_checkpoint_ids:
                test_cp_id = imported_checkpoint_ids[-1]
                # 先读取原始数据，测试后恢复
                _, original_cp_list = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path="/api/v1/checkpoints",
                        expected_status=200,
                        description="读取审核点（CRUD 前备份）",
                    ),
                    log,
                )
                original_payload = None
                if original_cp_list:
                    for cp in original_cp_list:
                        if cp.get("id") == test_cp_id:
                            original_payload = cp.get("payload_json")
                            break

                # PUT 用合法枚举值
                await call_endpoint(
                    client,
                    EndpointSpec(
                        method="PUT",
                        path="/api/v1/checkpoints/{checkpoint_id}",
                        expected_status=200,
                        description="更新审核点（CRUD 测试）",
                        path_params={"checkpoint_id": test_cp_id},
                        body={
                            "payload_json": '{"id":"crud-test","category":"其他违法违规","title":"CRUD 测试","description":"临时测试数据","legal_basis":[],"severity":"minor","retrieval_hint":""}'
                        },
                    ),
                    log,
                )

                # 恢复原始数据
                if original_payload:
                    await call_endpoint(
                        client,
                        EndpointSpec(
                            method="PUT",
                            path="/api/v1/checkpoints/{checkpoint_id}",
                            expected_status=200,
                            description="恢复审核点原始数据",
                            path_params={"checkpoint_id": test_cp_id},
                            body={"payload_json": original_payload},
                        ),
                        log,
                    )

                # DELETE 测试：找一个不在 imported 列表中的审核点
                _, extra_resp = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path="/api/v1/checkpoints",
                        expected_status=200,
                        description="列出审核点（CRUD 后）",
                    ),
                    log,
                )
                if extra_resp:
                    all_ids = {c["id"] for c in extra_resp if c.get("id")}
                    deletable = all_ids - set(imported_checkpoint_ids)
                    if deletable:
                        del_id = next(iter(deletable))
                        await call_endpoint(
                            client,
                            EndpointSpec(
                                method="DELETE",
                                path="/api/v1/checkpoints/{checkpoint_id}",
                                expected_status=204,
                                description="删除审核点",
                                path_params={"checkpoint_id": del_id},
                            ),
                            log,
                        )

            # ── Phase 5: Per-project 端到端（Pipeline B + workpaper） ──
            audit_terminal = {
                "draft_ready",
                "completed",
                "partial_ready",
                "failed",
                "waiting_retry",
                "cancelled",
                "interrupted",
            }
            completed_audit_run_ids: list[str] = []

            for proj in manifest.projects:
                tender_path = Path(proj.tender_doc)
                if not tender_path.exists() or not imported_checkpoint_ids:
                    continue

                # 5a: 创建 Project
                _, proj_resp = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="POST",
                        path="/api/v1/projects",
                        expected_status=201,
                        description=f"创建项目: {proj.name}",
                        body={"name": f"harness-{proj.name}-{run_id}", "created_by": "harness"},
                    ),
                    log,
                )
                if not proj_resp:
                    continue
                project_id = proj_resp["id"]

                # 5b: 获取单个 Project
                await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path="/api/v1/projects/{project_id}",
                        expected_status=200,
                        description=f"获取项目: {proj.name}",
                        path_params={"project_id": project_id},
                    ),
                    log,
                )

                # 5c: 上传文书
                _, td_resp = await call_endpoint(
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
                if not td_resp:
                    continue
                tender_doc_id = td_resp["id"]

                # 5d: 列出文书
                await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path="/api/v1/projects/{project_id}/tender-docs",
                        expected_status=200,
                        description=f"列出文书: {proj.name}",
                        path_params={"project_id": project_id},
                    ),
                    log,
                )

                # 5e: 创建 Audit Run
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
                            "tender_doc_id": tender_doc_id,
                            "checkpoint_ids": imported_checkpoint_ids,
                        },
                    ),
                    log,
                )

                if not audit_resp or status != 202:
                    record_pipeline_run(
                        log,
                        pipeline="B",
                        project_name=proj.name,
                        input_file=str(proj.tender_doc),
                        status="create_failed",
                        duration_s=time.time() - t0,
                        total_tokens=0,
                        error=f"创建审核返回 {status}",
                    )
                    continue
                audit_run_id = audit_resp.get("audit_run_id", "")
                if not audit_run_id:
                    continue

                # 5f: 列出 Audit Runs
                await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path="/api/v1/audit/runs",
                        expected_status=200,
                        description="列出审核运行",
                    ),
                    log,
                )

                # 5g: 获取单个 Audit Run
                await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path="/api/v1/audit/runs/{audit_run_id}",
                        expected_status=200,
                        description="获取审核运行",
                        path_params={"audit_run_id": audit_run_id},
                    ),
                    log,
                )

                # 5h: 轮询等待完成
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
                    error=None
                    if audit_status in ("draft_ready", "completed", "partial_ready")
                    else audit_status,
                )

                if not final or audit_status not in ("draft_ready", "completed", "partial_ready"):
                    continue
                completed_audit_run_ids.append(audit_run_id)

                # 5i: 记录审核发现
                _, progress = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path=f"/api/v1/audit/runs/{audit_run_id}/progress",
                        expected_status=200,
                        description="获取审核进度（记录发现）",
                    ),
                    log,
                )
                if progress:
                    findings: list[dict[str, Any]] = []
                    for pr in progress.get("point_runs", []):
                        if pr.get("status") != "completed" or not pr.get("finding_json"):
                            continue
                        finding_raw = pr["finding_json"]
                        finding = (
                            json.loads(finding_raw) if isinstance(finding_raw, str) else finding_raw
                        )
                        finding["point_run_id"] = pr.get("id", "")
                        finding["checkpoint_id"] = pr.get("checkpoint_final_id", "")
                        finding["status"] = pr.get("status", "unknown")
                        finding["duration_s"] = 0.0
                        findings.append(finding)
                    if findings:
                        record_audit_results(log, findings)
                        # 收集各 point_run 的 workspace 证据
                        from govdoc.harness.pipeline_eval import (
                            collect_workspace_evidence,
                            record_agent_trajectory,
                        )

                        for pr in progress.get("point_runs", []):
                            pr_id = pr.get("id", "")
                            if not pr_id:
                                continue
                            ws_evidence = collect_workspace_evidence(
                                workspace_dir=Path(f"data/.govdoc/workspaces/{pr_id}"),
                            )
                            if ws_evidence["plan_json"]:
                                record_agent_trajectory(
                                    log,
                                    pipeline="B",
                                    run_id=pr_id,
                                    plan_json=ws_evidence["plan_json"],
                                    workspace_files=ws_evidence["workspace_files"],
                                    phase_details=[],
                                )

                # 5j: 获取工作底稿草稿
                _, draft_resp = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path=f"/api/v1/audit/runs/{audit_run_id}/workpaper/draft",
                        expected_status=200,
                        description="获取工作底稿草稿",
                    ),
                    log,
                )

                # 5k: 定稿（部分定稿 or 完整定稿）
                if audit_status == "partial_ready":
                    await call_endpoint(
                        client,
                        EndpointSpec(
                            method="POST",
                            path=f"/api/v1/audit/runs/{audit_run_id}/workpaper/finalize-partial",
                            expected_status=201,
                            description="部分定稿",
                            body={"approved_by": "harness"},
                        ),
                        log,
                    )
                elif audit_status == "draft_ready":
                    await call_endpoint(
                        client,
                        EndpointSpec(
                            method="POST",
                            path=f"/api/v1/audit/runs/{audit_run_id}/workpaper/finalize",
                            expected_status=201,
                            description="完整定稿",
                            body={"approved_by": "harness"},
                        ),
                        log,
                    )

                # 定稿是异步的，等一小段时间
                await asyncio.sleep(5)

                # 5l: 下载 DOCX
                await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path=f"/api/v1/audit/runs/{audit_run_id}/workpaper/final/docx",
                        expected_status=200,
                        description="下载 DOCX",
                    ),
                    log,
                )

            # ── Phase 6: Retry 测试（使用已完成的 audit run 中的一个失败点） ──
            if completed_audit_run_ids:
                arid = completed_audit_run_ids[0]
                _, progress = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path=f"/api/v1/audit/runs/{arid}/progress",
                        expected_status=200,
                        description="获取进度（查失败点）",
                    ),
                    log,
                )
                if progress:
                    failed_points = [
                        pr for pr in progress.get("point_runs", []) if pr.get("status") == "failed"
                    ]
                    if failed_points:
                        retry_id = failed_points[0]["id"]
                        await call_endpoint(
                            client,
                            EndpointSpec(
                                method="POST",
                                path=f"/api/v1/audit/point-runs/{retry_id}/retry",
                                expected_status=202,
                                description="重试失败点",
                                path_params={},
                            ),
                            log,
                        )

            # ── Phase 7: Cancel 测试 ──
            # 创建一个新的 audit run 然后立即取消
            if manifest.projects and imported_checkpoint_ids:
                proj = manifest.projects[0]
                # 复用已创建的 project 和 tender_doc（如果有的话）
                _, all_runs = await call_endpoint(
                    client,
                    EndpointSpec(
                        method="GET",
                        path="/api/v1/audit/runs",
                        expected_status=200,
                        description="列出审核（查项目ID）",
                    ),
                    log,
                )
                if all_runs and len(all_runs) > 0:
                    existing_proj_id = all_runs[0].get("project_id", "")
                    existing_td_id = all_runs[0].get("tender_doc_id", "")
                    if existing_proj_id and existing_td_id:
                        _, cancel_resp = await call_endpoint(
                            client,
                            EndpointSpec(
                                method="POST",
                                path="/api/v1/audit/runs",
                                expected_status=202,
                                description="创建审核（取消测试）",
                                body={
                                    "project_id": existing_proj_id,
                                    "tender_doc_id": existing_td_id,
                                    "checkpoint_ids": imported_checkpoint_ids[:1],
                                },
                            ),
                            log,
                        )
                        if cancel_resp:
                            cancel_arid = cancel_resp.get("audit_run_id", "")
                            if cancel_arid:
                                await asyncio.sleep(1)
                                await call_endpoint(
                                    client,
                                    EndpointSpec(
                                        method="POST",
                                        path=f"/api/v1/audit/runs/{cancel_arid}/cancel",
                                        expected_status=200,
                                        description="取消审核",
                                    ),
                                    log,
                                )

            # ── Phase 8: Compare 测试 ──
            # 需要两份 DOCX。用 real_data 中的文件
            compare_files = list(Path(project_root).glob("real_data/**/*.docx"))
            if len(compare_files) >= 2:
                f1, f2 = compare_files[0], compare_files[1]
                await call_endpoint(
                    client,
                    EndpointSpec(
                        method="POST",
                        path="/api/v1/compare",
                        expected_status=200,
                        description="文档对比",
                        files={
                            "first_file": (f1.name, f1.read_bytes()),
                            "second_file": (f2.name, f2.read_bytes()),
                        },
                    ),
                    log,
                )

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

            log.log_event(
                "api_eval_complete",
                {
                    "total_calls": len(sync_calls) if sync_calls else 0,
                },
            )

    logger.info("L2 评估完成, run_id=%s", run_id)
    return run_id


def _parse_args() -> argparse.Namespace:
    """解析 L2 API 评估 CLI 参数。"""
    parser = argparse.ArgumentParser(description="L2 API harness 评估")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--manifest", default="scripts/fixtures/harness_manifest.yaml")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--rubric-dir", default="scripts/rubrics")
    parser.add_argument("--db-path", default="results/harness.db")
    return parser.parse_args()


def _update_run_status(db_path: str, run_id: str, status: str) -> None:
    """确保运行记录存在，并更新最终状态。"""
    import sqlite3

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _runs ("
            "run_id TEXT PRIMARY KEY, git_sha TEXT, started_at TEXT, "
            "finished_at TEXT, heartbeat_at TEXT, config JSON, "
            "status TEXT DEFAULT 'running')"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS _events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, "
            "timestamp TEXT, event_type TEXT, payload JSON)"
        )
        from govdoc.harness.log import _now_iso

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


def main() -> None:
    """运行 L2 API 评估 CLI，并记录致命异常与中断信号。"""
    import signal
    import sys
    from types import FrameType
    from typing import NoReturn

    from govdoc.harness.handler import SqliteHandler

    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    run_id = f"L2-{uuid.uuid4().hex[:8]}"
    root_logger = logging.getLogger()
    sqlite_handler = SqliteHandler(db_path=args.db_path, run_id=run_id)
    root_logger.addHandler(sqlite_handler)

    def _handle_signal(signum: int, frame: FrameType | None) -> NoReturn:
        del frame
        _update_run_status(args.db_path, run_id, "interrupted")
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
        _update_run_status(args.db_path, run_id, "crashed")
        sys.exit(1)
    finally:
        root_logger.removeHandler(sqlite_handler)
        sqlite_handler.close()


if __name__ == "__main__":
    main()
