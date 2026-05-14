"""L2 API 评估逻辑单测。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from pydantic import BaseModel

from govdoc.harness.api_eval import (
    EndpointSpec,
    call_endpoint,
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
        assert spec.form_data is None
        assert spec.files is None
        assert spec.is_async is False
        assert spec.path_params == {}


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
            status, data = asyncio.run(call_endpoint(mock_client, spec, log))

        assert status == 202
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "data" in call_kwargs.kwargs
        assert "files" in call_kwargs.kwargs
        assert call_kwargs.kwargs["data"]["title"] == "测试法规"
