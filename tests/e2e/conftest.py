"""E2E 测试共享 fixture — 打向真实部署的 testing 环境。"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

REAL_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "real_data"
E2E_REPORTS_DIR = Path(__file__).parent / "reports"

BACKEND_BASE = os.environ.get("E2E_BACKEND_URL", "http://100.83.164.94:8001")
FRONTEND_BASE = os.environ.get("E2E_FRONTEND_URL", "http://100.83.164.94:5174")


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
    p = REAL_DATA_DIR / "从化区中医医院手术室设备及附件、病房护理及医院设备采购" / "从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx"
    assert p.exists(), f"测试文件不存在: {p}"
    return p


@pytest.fixture(scope="session")
def tender_pdf_path() -> Path:
    """从化区中医医院招标文书 PDF。"""
    p = REAL_DATA_DIR / "从化区中医医院手术室设备及附件、病房护理及医院设备采购" / "3、从化区中医医院手术室设备及附件、病房护理及医院设备采购" / "从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件（2024040902）.pdf.pdf"
    assert p.exists(), f"测试文件不存在: {p}"
    return p


@pytest.fixture(scope="session")
def guide_docx_path() -> Path:
    """2025 年专项整治工作指引。"""
    p = REAL_DATA_DIR / '2025年政府采购领域“四类”违法违规行为专项整治工作指引.doc'
    assert p.exists(), f"测试文件不存在: {p}"
    return p


@pytest.fixture(scope="session")
def checkpoint_xls_path() -> Path:
    """处理处罚标准 XLS（用于审核点批量导入）。"""
    p = REAL_DATA_DIR / "附件9 处理处罚标准.xls"
    assert p.exists(), f"测试文件不存在: {p}"
    return p
