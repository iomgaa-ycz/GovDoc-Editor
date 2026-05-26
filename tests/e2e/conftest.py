"""E2E 测试共享 fixture — 打向真实部署的 testing 环境。"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any
from pathlib import Path

import httpx
import pytest

REAL_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "real_data"
E2E_REPORTS_DIR = Path(__file__).parent / "reports"

BACKEND_BASE = os.environ.get("E2E_BACKEND_URL", "http://100.82.33.121:8001")
FRONTEND_BASE = os.environ.get("E2E_FRONTEND_URL", "http://100.82.33.121:5174")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: 涉及真实 LLM 调用，耗时较长")


@pytest.fixture(scope="session")
def backend_url() -> str:
    return BACKEND_BASE


@pytest.fixture(scope="session")
def frontend_url() -> str:
    return FRONTEND_BASE


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


@pytest.fixture(scope="session")
def api_long(backend_url: str) -> httpx.Client:
    """长超时客户端，用于 LLM 相关的轮询（最长 10 分钟）。"""
    transport = httpx.HTTPTransport(proxy=None)
    client = httpx.Client(
        base_url=backend_url,
        timeout=httpx.Timeout(30.0, read=600.0),
        transport=transport,
    )
    yield client
    client.close()


@pytest.fixture(scope="session")
def tender_docx_path() -> Path:
    """从化区中医医院招标文书 DOCX。"""
    p = (
        REAL_DATA_DIR
        / "从化区中医医院手术室设备及附件、病房护理及医院设备采购"
        / "从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx"
    )
    assert p.exists(), f"测试文件不存在: {p}"
    return p


@pytest.fixture(scope="session")
def tender_pdf_path() -> Path:
    """从化区中医医院招标文书 PDF。"""
    p = (
        REAL_DATA_DIR
        / "从化区中医医院手术室设备及附件、病房护理及医院设备采购"
        / "3、从化区中医医院手术室设备及附件、病房护理及医院设备采购"
        / "从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件（2024040902）.pdf.pdf"
    )
    assert p.exists(), f"测试文件不存在: {p}"
    return p


@pytest.fixture(scope="session")
def guide_docx_path() -> Path:
    """2025 年专项整治工作指引。"""
    p = REAL_DATA_DIR / "2025年政府采购领域“四类”违法违规行为专项整治工作指引.doc"
    assert p.exists(), f"测试文件不存在: {p}"
    return p


@pytest.fixture(scope="session")
def checkpoint_xls_path() -> Path:
    """处理处罚标准 XLS（用于审核点批量导入）。"""
    p = REAL_DATA_DIR / "附件9 处理处罚标准.xls"
    assert p.exists(), f"测试文件不存在: {p}"
    return p


@pytest.fixture(scope="session")
def wait_for_document_ready(api: httpx.Client) -> Callable[[str], dict[str, Any]]:
    """轮询 Document 转换状态，直到 ready 或失败。

    返回值:
        可接收 doc_id 的闭包，成功时返回最新文档详情。
    """

    def _wait(doc_id: str, timeout_seconds: int = 300, interval_seconds: int = 5) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        last_data: dict[str, Any] = {}

        while time.monotonic() < deadline:
            resp = api.get(f"/api/v1/documents/{doc_id}")
            assert resp.status_code == 200, resp.text
            last_data = resp.json()
            status = last_data.get("status")

            if status == "ready":
                return last_data
            if status == "failed":
                pytest.fail(f"文档转换失败: {doc_id}, error={last_data.get('error_message')}")

            time.sleep(interval_seconds)

        pytest.fail(f"等待文档 ready 超时: {doc_id}, last={last_data}")

    return _wait


@pytest.fixture(scope="session")
def test_pdf_paths() -> list[Path]:
    """三个轻量测试用 PDF 文件。"""
    names = [
        "1广东宏业建设工程有限公司.pdf",
        "2清远市创和建筑工程有限公司.pdf",
        "3阳山县腾晖建筑工程有限公司.pdf",
    ]
    paths = [REAL_DATA_DIR / n for n in names]
    for p in paths:
        assert p.exists(), f"测试文件不存在: {p}"
    return paths


@pytest.fixture(scope="session")
def upload_document(
    api: httpx.Client,
    wait_for_document_ready: Callable[[str], dict[str, Any]],
) -> Callable[[Path, bool], dict[str, Any]]:
    """上传单个文档到文件管理中心，并可选择等待转换完成。

    返回值:
        可接收文件路径和 wait_ready 标志的闭包，返回文档详情。
    """

    def _upload(path: Path, wait_ready: bool = True) -> dict[str, Any]:
        with path.open("rb") as file_obj:
            resp = api.post(
                "/api/v1/documents/upload",
                files=[("files", (path.name, file_obj, "application/octet-stream"))],
            )
        assert resp.status_code == 201, resp.text
        payload = resp.json()
        assert isinstance(payload, list)
        assert len(payload) == 1
        document = payload[0]
        assert "id" in document
        assert "filename" in document
        assert "status" in document

        if wait_ready:
            return wait_for_document_ready(document["id"])
        return document

    return _upload
