"""L2 API 评估逻辑单测。"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from govdoc.harness.api_eval import (
    EndpointSpec,
    check_response_schema,
    record_api_call,
    record_api_contract,
)
from govdoc.harness.log import HarnessLog
from govdoc.harness.schemas import create_all_tables


class TestRecordApiCall:
    """测试 api_calls 记录。"""

    def test_record_success(self, tmp_path: Path) -> None:
        """记录一次成功的 API 调用。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="api-1") as log:
            create_all_tables(log)
            record_api_call(
                log,
                method="GET",
                path="/healthz",
                status_code=200,
                duration_ms=15.3,
                request_size=0,
                response_size=28,
            )

            rows = log.query("SELECT * FROM api_calls WHERE run_id='api-1'")
            assert len(rows) == 1
            assert rows[0]["status_code"] == 200
            assert rows[0]["duration_ms"] == 15.3


class TestRecordApiContract:
    """测试 api_contracts 记录。"""

    def test_record_passed(self, tmp_path: Path) -> None:
        """记录通过的契约检查。"""
        db_path = str(tmp_path / "h.db")
        with HarnessLog(db_path=db_path, run_id="api-2") as log:
            create_all_tables(log)
            record_api_contract(
                log,
                endpoint="GET /healthz",
                check_name="status_code",
                passed=True,
                detail="expected=200, actual=200",
            )

            rows = log.query("SELECT * FROM api_contracts WHERE run_id='api-2'")
            assert len(rows) == 1
            assert rows[0]["passed"] == 1


class TestCheckResponseSchema:
    """测试响应 schema 校验。"""

    def test_valid_response(self) -> None:
        """合法响应返回 (True, '')。"""

        class HealthResponse(BaseModel):
            status: str

        passed, detail = check_response_schema({"status": "ok"}, HealthResponse)
        assert passed is True
        assert detail == ""

    def test_invalid_response(self) -> None:
        """不合法响应返回 (False, error_msg)。"""

        class HealthResponse(BaseModel):
            status: str
            version: int

        passed, detail = check_response_schema({"status": "ok"}, HealthResponse)
        assert passed is False
        assert "version" in detail


class TestEndpointSpec:
    """测试端点规格定义。"""

    def test_spec_fields(self) -> None:
        """EndpointSpec 包含必要字段。"""
        spec = EndpointSpec(
            method="POST",
            path="/api/v1/projects",
            expected_status=201,
            description="创建项目",
        )
        assert spec.method == "POST"
        assert spec.expected_status == 201

    def test_spec_defaults(self) -> None:
        """EndpointSpec 默认值正确。"""
        spec = EndpointSpec(
            method="GET",
            path="/healthz",
            expected_status=200,
            description="健康检查",
        )
        assert spec.body is None
        assert spec.files is None
        assert spec.is_async is False
        assert spec.path_params == {}
