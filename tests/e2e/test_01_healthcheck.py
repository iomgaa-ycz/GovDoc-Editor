"""E2E: 基础连通性验证。"""

from __future__ import annotations

import httpx


def test_backend_healthz(api: httpx.Client):
    """B01: /healthz 返回 ok。"""
    resp = api.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_swagger_docs_accessible(api: httpx.Client):
    """Swagger UI 可访问。"""
    resp = api.get("/docs")
    assert resp.status_code == 200
    assert "swagger" in resp.text.lower() or "openapi" in resp.text.lower()
