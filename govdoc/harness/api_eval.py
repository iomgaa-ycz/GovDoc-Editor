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
from govdoc.harness.manifest import HarnessManifest
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
        files: 上传文件字典或重复字段列表。
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
    files: Any | None = None
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


async def _dispatch_request(client: Any, spec: EndpointSpec, path: str) -> Any:
    """根据 HTTP 方法分发请求。"""
    if spec.method == "GET":
        return await client.get(path)
    if spec.method == "POST":
        if spec.files:
            return await client.post(path, files=spec.files, data=spec.form_data or {})
        if spec.body:
            return await client.post(path, json=spec.body)
        return await client.post(path)
    if spec.method == "PUT":
        return await client.put(path, json=spec.body)
    if spec.method == "DELETE":
        return await client.delete(path)
    raise ValueError(f"不支持的 HTTP 方法: {spec.method}")


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
        resp = await _dispatch_request(client, spec, path)

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
    from dotenv import load_dotenv
    import httpx

    from govdoc.harness.manifest import load_manifest

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
            _init_eval_session(log, base_url, config_snapshot)
            await _run_health_check(client, log)
            await _execute_rule_extraction_specs(client, log, manifest, pipeline_timeout)
            imported_checkpoint_ids = await _prepare_checkpoint_specs(
                client,
                log,
                manifest,
                max_checkpoints,
            )
            completed_audit_run_ids = await _execute_project_audit_specs(
                client,
                log,
                manifest,
                imported_checkpoint_ids,
                run_id,
                pipeline_timeout,
            )
            await _execute_auxiliary_endpoint_specs(
                client,
                log,
                manifest,
                imported_checkpoint_ids,
                completed_audit_run_ids,
                project_root,
            )
            _store_ground_truth(log, manifest)
            _run_semantic_evaluations(log, rubric_dir, project_root)
            _finalize_eval(log, run_id)

    logger.info("L2 评估完成, run_id=%s", run_id)
    return run_id


def _init_eval_session(
    log: HarnessLog,
    base_url: str,
    config_snapshot: dict[str, Any],
) -> None:
    """初始化评估日志表、起始事件，并清理上次 harness 残留状态。"""
    from govdoc.db.session import get_session as _get_session
    from govdoc.harness.pipeline_eval import _clean_harness_state

    create_all_tables(log)
    log.log_event("api_eval_start", {"base_url": base_url, "config": config_snapshot})

    session_gen = _get_session()
    clean_session = next(session_gen)
    try:
        _clean_harness_state(clean_session)
    finally:
        session_gen.close()


async def _run_health_check(client: Any, log: HarnessLog) -> None:
    """执行基础冒烟端点，确认 API 服务和核心列表端点可访问。"""
    health_specs = [
        EndpointSpec("GET", "/healthz", 200, "健康检查"),
        EndpointSpec("GET", "/api/v1/projects", 200, "列出项目"),
        EndpointSpec("GET", "/api/v1/rules", 200, "列出法规"),
        EndpointSpec("GET", "/api/v1/checkpoints", 200, "列出审核点"),
    ]
    for spec in health_specs:
        await call_endpoint(client, spec, log)


async def _execute_rule_extraction_specs(
    client: Any,
    log: HarnessLog,
    manifest: HarnessManifest,
    pipeline_timeout: float,
) -> None:
    """逐个上传法规文件并记录 Pipeline A 抽取结果与 agent 轨迹。"""
    for rule in manifest.rules:
        await _execute_single_rule_extraction(client, log, rule.name, rule.path, pipeline_timeout)


async def _execute_single_rule_extraction(
    client: Any,
    log: HarnessLog,
    rule_name: str,
    rule_path: Path,
    pipeline_timeout: float,
) -> None:
    """执行单个法规文件的上传、抽取轮询和结果落库。"""
    from govdoc.harness.pipeline_eval import record_pipeline_run

    if not rule_path.exists():
        logger.warning("法规文件不存在: %s", rule_path)
        return

    t0 = time.time()
    _, resp_data = await call_endpoint(
        client,
        EndpointSpec(
            method="POST",
            path="/api/v1/rules/upload",
            expected_status=202,
            description=f"上传法规: {rule_name}",
            form_data={"title": rule_name},
            files={"file": (rule_path.name, rule_path.read_bytes())},
        ),
        log,
    )

    if not resp_data:
        return
    rule_source_id = resp_data.get("rule_source_id", "")
    extract_run_id = resp_data.get("extract_run_id", "")
    if not extract_run_id:
        return

    final = await _poll_until_done(
        client,
        f"/api/v1/rules/{rule_source_id}/extract-runs/{extract_run_id}/status",
        status_field="status",
        terminal_statuses={"draft_ready", "completed", "failed", "interrupted", "cancelled"},
        log=log,
        poll_interval=10.0,
        timeout_s=pipeline_timeout,
    )
    pa_status = final["status"] if final else "timeout"
    record_pipeline_run(
        log,
        pipeline="A",
        project_name=rule_name,
        input_file=rule_path,
        status=pa_status,
        duration_s=time.time() - t0,
        total_tokens=0,
        error=(final.get("error") if final else "Pipeline A 超时") or None,
    )

    if pa_status in ("draft_ready", "completed"):
        await _record_rule_extraction_outputs(client, log, extract_run_id)


async def _record_rule_extraction_outputs(
    client: Any,
    log: HarnessLog,
    extract_run_id: str,
) -> None:
    """记录 Pipeline A 自动提升的审核点和对应 workspace 轨迹。"""
    from govdoc.harness.pipeline_eval import (
        collect_workspace_evidence,
        record_agent_trajectory,
        record_extract_results,
    )

    _, cp_list = await call_endpoint(
        client,
        EndpointSpec("GET", "/api/v1/checkpoints", 200, "获取抽取审核点"),
        log,
    )
    if not cp_list:
        return

    extract_cps = [
        json.loads(cp.get("payload_json", "{}"))
        for cp in cp_list
        if cp.get("approved_by") == "system:auto-promote"
    ]
    if not extract_cps:
        return

    record_extract_results(log, extract_cps)
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


async def _prepare_checkpoint_specs(
    client: Any,
    log: HarnessLog,
    manifest: HarnessManifest,
    max_checkpoints: int,
) -> list[str]:
    """导入金标准审核点，按需截断数量，并执行审核点 CRUD 契约检查。"""
    imported_checkpoint_ids = await _import_checkpoint_fixtures(
        client,
        log,
        manifest,
        max_checkpoints,
    )
    await _run_checkpoint_crud_checks(client, log, imported_checkpoint_ids)
    return imported_checkpoint_ids


async def _import_checkpoint_fixtures(
    client: Any,
    log: HarnessLog,
    manifest: HarnessManifest,
    max_checkpoints: int,
) -> list[str]:
    """导入 manifest 中的审核点 fixture，并返回参与后续审核的 ID 列表。"""
    imported_checkpoint_ids: list[str] = []
    for cp_fixture in manifest.checkpoints:
        cp_path = cp_fixture.path
        if not cp_path.exists():
            continue
        _, resp = await call_endpoint(
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
            imported_checkpoint_ids.extend(
                c["id"] for c in resp.get("checkpoints", []) if c.get("id")
            )

    if max_checkpoints > 0 and len(imported_checkpoint_ids) > max_checkpoints:
        imported_checkpoint_ids = imported_checkpoint_ids[:max_checkpoints]
        logger.info("审核点截断为 %d 个", max_checkpoints)
    return imported_checkpoint_ids


async def _run_checkpoint_crud_checks(
    client: Any,
    log: HarnessLog,
    imported_checkpoint_ids: list[str],
) -> None:
    """用不影响 imported 列表的临时数据执行审核点 PUT/DELETE 检查。"""
    if not imported_checkpoint_ids:
        return

    test_cp_id = imported_checkpoint_ids[-1]
    _, original_cp_list = await call_endpoint(
        client,
        EndpointSpec("GET", "/api/v1/checkpoints", 200, "读取审核点（CRUD 前备份）"),
        log,
    )
    original_payload = _find_checkpoint_payload(original_cp_list, test_cp_id)

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

    await _delete_extra_checkpoint(client, log, imported_checkpoint_ids)


def _find_checkpoint_payload(
    checkpoint_list: Any,
    checkpoint_id: str,
) -> str | None:
    """从审核点列表中查找指定 ID 的原始 payload_json。"""
    if not checkpoint_list:
        return None
    for checkpoint in checkpoint_list:
        if checkpoint.get("id") == checkpoint_id:
            return checkpoint.get("payload_json")
    return None


async def _delete_extra_checkpoint(
    client: Any,
    log: HarnessLog,
    imported_checkpoint_ids: list[str],
) -> None:
    """删除一个非 imported 列表中的审核点以覆盖 DELETE 端点。"""
    _, extra_resp = await call_endpoint(
        client,
        EndpointSpec("GET", "/api/v1/checkpoints", 200, "列出审核点（CRUD 后）"),
        log,
    )
    if not extra_resp:
        return

    all_ids = {c["id"] for c in extra_resp if c.get("id")}
    deletable = all_ids - set(imported_checkpoint_ids)
    if not deletable:
        return

    await call_endpoint(
        client,
        EndpointSpec(
            method="DELETE",
            path="/api/v1/checkpoints/{checkpoint_id}",
            expected_status=204,
            description="删除审核点",
            path_params={"checkpoint_id": next(iter(deletable))},
        ),
        log,
    )


async def _execute_project_audit_specs(
    client: Any,
    log: HarnessLog,
    manifest: HarnessManifest,
    imported_checkpoint_ids: list[str],
    run_id: str,
    pipeline_timeout: float,
) -> list[str]:
    """逐项目执行 Pipeline B、工作底稿生成和下载端点检查。"""
    completed_audit_run_ids: list[str] = []
    for project in manifest.projects:
        audit_run_id = await _execute_single_project_audit(
            client,
            log,
            project.name,
            project.tender_doc,
            imported_checkpoint_ids,
            run_id,
            pipeline_timeout,
        )
        if audit_run_id:
            completed_audit_run_ids.append(audit_run_id)
    return completed_audit_run_ids


async def _execute_single_project_audit(
    client: Any,
    log: HarnessLog,
    project_name: str,
    tender_path: Path,
    imported_checkpoint_ids: list[str],
    run_id: str,
    pipeline_timeout: float,
) -> str | None:
    """执行单个项目的创建、文书上传、审核运行、结果记录和定稿下载。"""
    from govdoc.harness.pipeline_eval import record_pipeline_run

    if not tender_path.exists() or not imported_checkpoint_ids:
        return None

    project_id = await _create_project(client, log, project_name, run_id)
    if not project_id:
        return None

    tender_doc_id = await _upload_tender_doc(client, log, project_name, project_id, tender_path)
    if not tender_doc_id:
        return None

    t0 = time.time()
    status, audit_resp = await call_endpoint(
        client,
        EndpointSpec(
            method="POST",
            path="/api/v1/audit/runs",
            expected_status=202,
            description=f"创建审核: {project_name}",
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
            project_name=project_name,
            input_file=str(tender_path),
            status="create_failed",
            duration_s=time.time() - t0,
            total_tokens=0,
            error=f"创建审核返回 {status}",
        )
        return None

    audit_run_id = audit_resp.get("audit_run_id", "")
    if not audit_run_id:
        return None

    await _read_audit_run_endpoints(client, log, audit_run_id)
    audit_status = await _poll_and_record_audit_run(
        client,
        log,
        audit_run_id,
        project_name,
        tender_path,
        t0,
        pipeline_timeout,
    )
    if audit_status not in ("draft_ready", "completed", "partial_ready"):
        return None

    await _record_completed_audit_details(client, log, audit_run_id, audit_status)
    return audit_run_id


async def _create_project(
    client: Any,
    log: HarnessLog,
    project_name: str,
    run_id: str,
) -> str | None:
    """创建项目并读取一次项目详情，返回项目 ID。"""
    _, proj_resp = await call_endpoint(
        client,
        EndpointSpec(
            method="POST",
            path="/api/v1/projects",
            expected_status=201,
            description=f"创建项目: {project_name}",
            body={"name": f"harness-{project_name}-{run_id}", "created_by": "harness"},
        ),
        log,
    )
    if not proj_resp:
        return None

    project_id = proj_resp["id"]
    await call_endpoint(
        client,
        EndpointSpec(
            method="GET",
            path="/api/v1/projects/{project_id}",
            expected_status=200,
            description=f"获取项目: {project_name}",
            path_params={"project_id": project_id},
        ),
        log,
    )
    return project_id


async def _upload_tender_doc(
    client: Any,
    log: HarnessLog,
    project_name: str,
    project_id: str,
    tender_path: Path,
) -> str | None:
    """上传项目招标文件并读取文书列表，返回文书 ID。"""
    _, td_resp = await call_endpoint(
        client,
        EndpointSpec(
            method="POST",
            path="/api/v1/projects/{project_id}/tender-doc",
            expected_status=201,
            description=f"上传文书: {project_name}",
            path_params={"project_id": project_id},
            files={"file": (tender_path.name, tender_path.read_bytes())},
        ),
        log,
    )
    if not td_resp:
        return None

    tender_doc_id = td_resp["id"]
    await call_endpoint(
        client,
        EndpointSpec(
            method="GET",
            path="/api/v1/projects/{project_id}/tender-docs",
            expected_status=200,
            description=f"列出文书: {project_name}",
            path_params={"project_id": project_id},
        ),
        log,
    )
    return tender_doc_id


async def _read_audit_run_endpoints(client: Any, log: HarnessLog, audit_run_id: str) -> None:
    """读取审核运行列表和单个审核运行，覆盖查询端点契约。"""
    await call_endpoint(
        client,
        EndpointSpec("GET", "/api/v1/audit/runs", 200, "列出审核运行"),
        log,
    )
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


async def _poll_and_record_audit_run(
    client: Any,
    log: HarnessLog,
    audit_run_id: str,
    project_name: str,
    tender_path: Path,
    start_time: float,
    pipeline_timeout: float,
) -> str:
    """轮询 Pipeline B 至终态并记录 pipeline_runs 汇总。"""
    from govdoc.harness.pipeline_eval import record_pipeline_run

    final = await _poll_until_done(
        client,
        f"/api/v1/audit/runs/{audit_run_id}/progress",
        status_field="status",
        terminal_statuses={
            "draft_ready",
            "completed",
            "partial_ready",
            "failed",
            "waiting_retry",
            "cancelled",
            "interrupted",
        },
        log=log,
        poll_interval=10.0,
        timeout_s=pipeline_timeout,
    )
    audit_status = final["status"] if final else "timeout"
    record_pipeline_run(
        log,
        pipeline="B",
        project_name=project_name,
        input_file=str(tender_path),
        status=audit_status,
        duration_s=time.time() - start_time,
        total_tokens=0,
        error=None
        if audit_status in ("draft_ready", "completed", "partial_ready")
        else audit_status,
    )
    return audit_status


async def _record_completed_audit_details(
    client: Any,
    log: HarnessLog,
    audit_run_id: str,
    audit_status: str,
) -> None:
    """记录已完成审核运行的发现、轨迹、草稿、定稿和 DOCX 下载结果。"""
    await _record_audit_progress_outputs(client, log, audit_run_id)
    await _record_workpaper_draft(client, log, audit_run_id)
    await _finalize_workpaper(client, log, audit_run_id, audit_status)
    await asyncio.sleep(5)
    await call_endpoint(
        client,
        EndpointSpec(
            "GET",
            f"/api/v1/audit/runs/{audit_run_id}/workpaper/final/docx",
            200,
            "下载 DOCX",
        ),
        log,
    )


async def _record_audit_progress_outputs(
    client: Any,
    log: HarnessLog,
    audit_run_id: str,
) -> None:
    """读取审核进度，记录审核发现和每个 point_run 的 workspace 证据。"""
    from govdoc.harness.pipeline_eval import record_audit_results

    _, progress = await call_endpoint(
        client,
        EndpointSpec(
            "GET",
            f"/api/v1/audit/runs/{audit_run_id}/progress",
            200,
            "获取审核进度（记录发现）",
        ),
        log,
    )
    if not progress:
        return

    findings = _build_audit_findings(progress)
    if findings:
        record_audit_results(log, findings)
        _record_point_run_trajectories(log, progress)


def _build_audit_findings(progress: dict[str, Any]) -> list[dict[str, Any]]:
    """从审核进度响应中转换 harness 需要落库的 finding 结构。"""
    findings: list[dict[str, Any]] = []
    for point_run in progress.get("point_runs", []):
        if point_run.get("status") == "completed" and point_run.get("finding_json"):
            finding_raw = point_run["finding_json"]
            finding = json.loads(finding_raw) if isinstance(finding_raw, str) else finding_raw
            finding["point_run_id"] = point_run.get("id", "")
            finding["checkpoint_id"] = point_run.get("checkpoint_final_id", "")
            finding["status"] = point_run.get("status", "unknown")
            finding["duration_s"] = 0.0
            findings.append(finding)
        else:
            findings.append(_build_incomplete_finding(point_run))
    return findings


def _build_incomplete_finding(point_run: dict[str, Any]) -> dict[str, Any]:
    """为未完成的 point_run 构造占位 finding，保留原始行为字段。"""
    status = point_run.get("status", "unknown")
    return {
        "point_run_id": point_run.get("id", ""),
        "checkpoint_id": point_run.get("checkpoint_final_id", ""),
        "status": point_run.get("status", "pending"),
        "duration_s": 0.0,
        "verdict": {
            "verdict": "未完成",
            "rationale": f"审核执行状态: {status}",
            "evidence_quotes": [],
        },
        "evidence_refs": [],
        "case_refs": [],
    }


def _record_point_run_trajectories(log: HarnessLog, progress: dict[str, Any]) -> None:
    """收集并记录 Pipeline B 每个 point_run 对应的 workspace 轨迹。"""
    from govdoc.harness.pipeline_eval import collect_workspace_evidence, record_agent_trajectory

    for point_run in progress.get("point_runs", []):
        point_run_id = point_run.get("id", "")
        if not point_run_id:
            continue
        ws_dir = Path(f"data/.govdoc/workspaces/{point_run_id}")
        archive = Path(f"data/.govdoc/archives/{point_run_id}.tar.gz")
        ws_evidence = collect_workspace_evidence(
            workspace_dir=ws_dir if ws_dir.exists() else None,
            archive_path=archive if archive.exists() else None,
        )
        if ws_evidence["plan_json"]:
            record_agent_trajectory(
                log,
                pipeline="B",
                run_id=point_run_id,
                plan_json=ws_evidence["plan_json"],
                workspace_files=ws_evidence["workspace_files"],
                phase_details=[],
            )


async def _record_workpaper_draft(client: Any, log: HarnessLog, audit_run_id: str) -> None:
    """读取工作底稿草稿并记录摘要、发现数量和结论分布。"""
    _, draft_resp = await call_endpoint(
        client,
        EndpointSpec(
            "GET",
            f"/api/v1/audit/runs/{audit_run_id}/workpaper/draft",
            200,
            "获取工作底稿草稿",
        ),
        log,
    )
    if draft_resp and isinstance(draft_resp, dict):
        log.log_event(
            "workpaper_draft",
            {
                "audit_run_id": audit_run_id,
                "summary": draft_resp.get("summary", ""),
                "findings_count": len(draft_resp.get("findings", [])),
                "findings_verdicts": [
                    f.get("verdict", {}).get("verdict", "") for f in draft_resp.get("findings", [])
                ],
            },
        )


async def _finalize_workpaper(
    client: Any,
    log: HarnessLog,
    audit_run_id: str,
    audit_status: str,
) -> None:
    """按审核状态触发部分定稿或完整定稿端点。"""
    if audit_status == "partial_ready":
        path = f"/api/v1/audit/runs/{audit_run_id}/workpaper/finalize-partial"
        description = "部分定稿"
    elif audit_status == "draft_ready":
        path = f"/api/v1/audit/runs/{audit_run_id}/workpaper/finalize"
        description = "完整定稿"
    else:
        return

    await call_endpoint(
        client,
        EndpointSpec(
            method="POST",
            path=path,
            expected_status=201,
            description=description,
            body={"approved_by": "harness"},
        ),
        log,
    )


async def _execute_auxiliary_endpoint_specs(
    client: Any,
    log: HarnessLog,
    manifest: HarnessManifest,
    imported_checkpoint_ids: list[str],
    completed_audit_run_ids: list[str],
    project_root: str,
) -> None:
    """执行重试、取消、文档对比等附加端点检查。"""
    await _run_retry_check(client, log, completed_audit_run_ids)
    await _run_cancel_check(client, log, manifest, imported_checkpoint_ids)
    await _run_compare_check(client, log, project_root)


async def _run_retry_check(
    client: Any,
    log: HarnessLog,
    completed_audit_run_ids: list[str],
) -> None:
    """在已完成审核中查找失败点并覆盖 retry 端点。"""
    if not completed_audit_run_ids:
        return

    audit_run_id = completed_audit_run_ids[0]
    _, progress = await call_endpoint(
        client,
        EndpointSpec(
            "GET",
            f"/api/v1/audit/runs/{audit_run_id}/progress",
            200,
            "获取进度（查失败点）",
        ),
        log,
    )
    if not progress:
        return

    failed_points = [pr for pr in progress.get("point_runs", []) if pr.get("status") == "failed"]
    if not failed_points:
        return

    await call_endpoint(
        client,
        EndpointSpec(
            method="POST",
            path=f"/api/v1/audit/point-runs/{failed_points[0]['id']}/retry",
            expected_status=202,
            description="重试失败点",
            path_params={},
        ),
        log,
    )


async def _run_cancel_check(
    client: Any,
    log: HarnessLog,
    manifest: HarnessManifest,
    imported_checkpoint_ids: list[str],
) -> None:
    """复用已有项目和文书创建新审核并立即取消，覆盖 cancel 端点。"""
    if not manifest.projects or not imported_checkpoint_ids:
        return

    _, all_runs = await call_endpoint(
        client,
        EndpointSpec("GET", "/api/v1/audit/runs", 200, "列出审核（查项目ID）"),
        log,
    )
    if not all_runs:
        return

    existing_proj_id = all_runs[0].get("project_id", "")
    existing_td_id = all_runs[0].get("tender_doc_id", "")
    if not existing_proj_id or not existing_td_id:
        return

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
    if not cancel_resp:
        return

    cancel_audit_run_id = cancel_resp.get("audit_run_id", "")
    if not cancel_audit_run_id:
        return

    await asyncio.sleep(1)
    await call_endpoint(
        client,
        EndpointSpec(
            "POST",
            f"/api/v1/audit/runs/{cancel_audit_run_id}/cancel",
            200,
            "取消审核",
        ),
        log,
    )


async def _run_compare_check(client: Any, log: HarnessLog, project_root: str) -> None:
    """查找 real_data 下两份 DOCX 并覆盖文档对比端点。"""
    compare_files = list(Path(project_root).glob("real_data/**/*.docx"))
    if len(compare_files) < 2:
        return

    first_file, second_file = compare_files[0], compare_files[1]
    await call_endpoint(
        client,
        EndpointSpec(
            method="POST",
            path="/api/v1/compare",
            expected_status=200,
            description="文档对比",
            files=[
                ("files", (first_file.name, first_file.read_bytes())),
                ("files", (second_file.name, second_file.read_bytes())),
            ],
        ),
        log,
    )


def _store_ground_truth(log: HarnessLog, manifest: HarnessManifest) -> None:
    """解析并记录 manifest 中配置的金标准审核点和人工工作底稿。"""
    from govdoc.harness.ground_truth import parse_gold_checkpoints, parse_human_workpaper

    if not manifest.ground_truth:
        return

    ground_truth = manifest.ground_truth
    if ground_truth.gold_checkpoints and ground_truth.gold_checkpoints.exists():
        gold_items = parse_gold_checkpoints(ground_truth.gold_checkpoints)
        log.log_event("ground_truth_checkpoints", {"count": len(gold_items), "items": gold_items})
        logger.info("已加载金标准审核点: %d 项", len(gold_items))

    for wp_fixture in ground_truth.human_workpapers:
        if wp_fixture.path.exists():
            wp_data = parse_human_workpaper(wp_fixture.path)
            wp_data["fixture_project_name"] = wp_fixture.project_name
            log.log_event("ground_truth_workpaper", wp_data)
            logger.info(
                "已加载人类工作底稿: %s (%d 个发现)",
                wp_fixture.project_name,
                len(wp_data.get("findings_text", [])),
            )


def _run_semantic_evaluations(
    log: HarnessLog,
    rubric_dir: str,
    project_root: str,
) -> None:
    """调用 pipeline 语义评估逻辑，记录 rubric 维度的质量指标。"""
    from govdoc.harness.pipeline_eval import _run_semantic_evaluations as run_semantic_evals

    logger.info("开始语义评估")
    run_semantic_evals(log, rubric_dir, project_root)


def _finalize_eval(log: HarnessLog, run_id: str) -> None:
    """计算 P95 延迟并写入 API 评估完成事件。"""
    sync_calls = log.query(
        "SELECT duration_ms FROM api_calls WHERE run_id=? AND status_code > 0 ORDER BY duration_ms",
        (run_id,),
    )
    if sync_calls:
        durations = [row["duration_ms"] for row in sync_calls]
        p95_idx = int(len(durations) * 0.95)
        p95 = durations[min(p95_idx, len(durations) - 1)]
        log.log_event("api_latency_p95", {"p95_ms": p95})

    log.log_event("api_eval_complete", {"total_calls": len(sync_calls) if sync_calls else 0})


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
    import sys

    from govdoc.harness.cli_common import setup_harness_cli, update_run_status

    args = _parse_args()
    run_id, sqlite_handler = setup_harness_cli(args.db_path, "L2")

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
        update_run_status(args.db_path, run_id, "crashed")
        sys.exit(1)
    finally:
        logging.getLogger().removeHandler(sqlite_handler)
        sqlite_handler.close()


if __name__ == "__main__":
    main()
