"""L2 API 评估：httpx 调全部端点 + 契约验证 + 性能指标。"""

from __future__ import annotations

import asyncio
import argparse
import json
import logging
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


async def run_api_eval(
    *,
    base_url: str = "http://localhost:8000",
    manifest_path: str,
    project_root: str,
    db_path: str = "results/harness.db",
) -> str:
    """L2 API 评估主入口。

    参数:
        base_url: FastAPI 服务地址。
        manifest_path: harness_manifest.yaml 路径。
        project_root: 项目根目录。
        db_path: harness.db 路径。

    返回:
        本次运行的 run_id。
    """
    import httpx

    from govdoc.harness.manifest import load_manifest

    run_id = f"L2-{uuid.uuid4().hex[:8]}"
    manifest = load_manifest(manifest_path, project_root=project_root)

    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
        with HarnessLog(db_path=db_path, run_id=run_id) as log:
            create_all_tables(log)
            log.log_event("api_eval_start", {"base_url": base_url})

            # Phase 1: 健康检查
            await call_endpoint(
                client,
                EndpointSpec(
                    method="GET", path="/healthz", expected_status=200, description="健康检查"
                ),
                log,
            )

            # Phase 2: 项目 CRUD
            status, proj_data = await call_endpoint(
                client,
                EndpointSpec(
                    method="POST",
                    path="/api/v1/projects",
                    expected_status=201,
                    description="创建项目",
                    body={"name": f"harness-test-{run_id}", "created_by": "harness"},
                ),
                log,
            )
            project_id = proj_data.get("id", "unknown") if proj_data else "unknown"

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
                    path="/api/v1/projects/{project_id}",
                    expected_status=200,
                    description="获取项目",
                    path_params={"project_id": project_id},
                ),
                log,
            )

            # Phase 3: 文书上传
            for proj in manifest.projects:
                tender_path = Path(proj.tender_doc)
                if tender_path.exists():
                    await call_endpoint(
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

            # Phase 5: 审核点导入
            for cp in manifest.checkpoints:
                cp_path = Path(cp.path)
                if cp_path.exists():
                    await call_endpoint(
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

            # Phase 6: 列出端点
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

            # Phase 7: P95 延迟
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
                {"total_calls": len(sync_calls) if sync_calls else 0},
            )

    logger.info("L2 评估完成, run_id=%s", run_id)
    return run_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="L2 API harness 评估")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--manifest", default="scripts/fixtures/harness_manifest.yaml")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--db-path", default="results/harness.db")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    run_id = asyncio.run(
        run_api_eval(
            base_url=args.base_url,
            manifest_path=args.manifest,
            project_root=args.project_root,
            db_path=args.db_path,
        )
    )
    logger.info("L2 完成, run_id=%s", run_id)
