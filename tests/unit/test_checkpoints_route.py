"""checkpoints API 路由单元测试。

覆盖范围：
- GET  /api/v1/checkpoints        — 空列表 + 有数据返回
- POST /api/v1/checkpoints/import — 拒绝非法格式 + CSV 导入成功
- PUT  /api/v1/checkpoints/{id}   — 更新成功 + 不存在 404
- DELETE /api/v1/checkpoints/{id} — 删除成功 + 不存在 404

技术说明：
- `sqlite:///:memory:` 每条连接看到不同空库，需用命名共享内存 URI
  `sqlite:///file:<name>?mode=memory&cache=shared&uri=true`
  保证 create_all 与路由 Session 共享同一内存实例。
- 每个 fixture 生成唯一 db_name，避免测试间污染。
- monkeypatch 替换路由模块内的绑定名
  `govdoc.api.routes.checkpoints.get_db_session`。
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from govdoc.api.routes.checkpoints import router
from govdoc.db.models import CheckpointFinal


# ────────────────────────────────────────────────
# 辅助：按唯一名称创建共享内存引擎
# ────────────────────────────────────────────────


def _make_memory_engine(db_name: str):
    """返回命名共享内存 SQLite 引擎。

    使用 URI 形式确保同名连接共享同一 in-memory 实例：
    sqlite:///file:<name>?mode=memory&cache=shared&uri=true
    """
    url = f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"
    return create_engine(url, connect_args={"check_same_thread": False})


# ────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────


@pytest.fixture()
def engine():
    """每个测试函数独立的命名共享内存 SQLite 引擎。"""
    db_name = f"test_checkpoints_{uuid.uuid4().hex}"
    eng = _make_memory_engine(db_name)
    SQLModel.metadata.create_all(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def client(engine, monkeypatch):
    """TestClient，已将路由模块的 get_db_session 替换为内存 DB。"""

    @contextmanager
    def _fake_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    # 路由代码做了 `from govdoc.api.deps import get_db_session`，
    # 需要 patch 路由模块内的绑定名，而非 deps 模块本身。
    monkeypatch.setattr("govdoc.api.routes.checkpoints.get_db_session", _fake_session)

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def seed_checkpoint(engine) -> CheckpointFinal:
    """向 DB 中插入一条 CheckpointFinal，返回该实例。"""
    with Session(engine) as session:
        cp = CheckpointFinal(
            payload_json='{"title": "测试审核点"}',
            approved_by="tester",
        )
        session.add(cp)
        session.commit()
        session.refresh(cp)
        return cp


# ────────────────────────────────────────────────
# GET /api/v1/checkpoints
# ────────────────────────────────────────────────


class TestListCheckpoints:
    def test_empty_db_returns_empty_list(self, client):
        """数据库为空时应返回空列表。"""
        resp = client.get("/api/v1/checkpoints")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_all_checkpoints(self, client, engine):
        """插入 2 条记录后应全量返回。"""
        with Session(engine) as session:
            for i in range(2):
                session.add(
                    CheckpointFinal(
                        payload_json=f'{{"title": "cp{i}"}}',
                        approved_by="tester",
                    )
                )
            session.commit()

        resp = client.get("/api/v1/checkpoints")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_response_shape(self, client, seed_checkpoint):
        """每条记录必须包含 id / kind / status / payload_json / approved_by 字段。"""
        resp = client.get("/api/v1/checkpoints")
        assert resp.status_code == 200
        item = resp.json()[0]
        assert set(item.keys()) >= {"id", "kind", "status", "payload_json", "approved_by"}
        assert item["kind"] == "final"
        assert item["status"] == "final"

    def test_sorted_by_id(self, client, engine):
        """结果应按 id 字母顺序排列。"""
        with Session(engine) as session:
            for i in range(3):
                session.add(
                    CheckpointFinal(
                        payload_json=f'{{"seq": {i}}}',
                        approved_by="tester",
                    )
                )
            session.commit()

        resp = client.get("/api/v1/checkpoints")
        ids = [item["id"] for item in resp.json()]
        assert ids == sorted(ids)


# ────────────────────────────────────────────────
# POST /api/v1/checkpoints/import
# ────────────────────────────────────────────────


class TestImportCheckpoints:
    def test_reject_unsupported_extension(self, client):
        """上传 .txt 文件应返回 400。"""
        resp = client.post(
            "/api/v1/checkpoints/import",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400
        assert "不支持" in resp.json()["detail"]

    def test_reject_pdf_extension(self, client):
        """上传 .pdf 文件应返回 400。"""
        resp = client.post(
            "/api/v1/checkpoints/import",
            files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
        )
        assert resp.status_code == 400

    def test_import_csv_success(self, client, engine):
        """合法 CSV 导入后应写入 DB 并返回正确摘要。"""
        csv_content = (
            "大类,违法违规问题,表现形式,处理依据,处罚依据,处理建议,责任主体\n"
            "一、限制条款,1.直接限制,设置供应商注册地限制,政府采购法第5条,,给予警告,采购人\n"
            ",2.限定行业,将特定行业作为条件,政府采购法第22条,,责令整改,代理机构\n"
        ).encode("utf-8")

        resp = client.post(
            "/api/v1/checkpoints/import",
            files={"file": ("checkpoints.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["imported_count"] == 2
        assert body["skipped_count"] == 0
        assert len(body["checkpoints"]) == 2

        # 验证 DB 实际写入
        with Session(engine) as session:
            finals = session.exec(select(CheckpointFinal)).all()
        assert len(finals) == 2

    def test_import_csv_approved_by_system(self, client, engine):
        """导入的审核点 approved_by 应为 'system:import'。"""
        csv_content = (
            "大类,违法违规问题,表现形式,处理依据,处罚依据,处理建议,责任主体\n"
            "一、限制条款,1.问题,有效表现形式,法条,,建议,主体\n"
        ).encode("utf-8")

        client.post(
            "/api/v1/checkpoints/import",
            files={"file": ("checkpoints.csv", csv_content, "text/csv")},
        )

        with Session(engine) as session:
            final = session.exec(select(CheckpointFinal)).first()
        assert final is not None
        assert final.approved_by == "system:import"

    def test_import_csv_skipped_rows(self, client, engine):
        """表现形式为空的行应被跳过并记录在 skipped_reasons。"""
        csv_content = (
            "大类,违法违规问题,表现形式,处理依据,处罚依据,处理建议,责任主体\n"
            "一、限制条款,1.问题,,法条,,建议,主体\n"
            "一、限制条款,2.问题,有效表现形式,法条,,建议,主体\n"
        ).encode("utf-8")

        resp = client.post(
            "/api/v1/checkpoints/import",
            files={"file": ("checkpoints.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["imported_count"] == 1
        assert body["skipped_count"] == 1
        assert len(body["skipped_reasons"]) == 1

    def test_import_response_checkpoint_shape(self, client):
        """返回的 checkpoints 每项应包含 id / kind / status / payload_json / approved_by。"""
        csv_content = (
            "大类,违法违规问题,表现形式,处理依据,处罚依据,处理建议,责任主体\n"
            "一、限制条款,1.问题,有效表现形式,法条,,建议,主体\n"
        ).encode("utf-8")

        resp = client.post(
            "/api/v1/checkpoints/import",
            files={"file": ("checkpoints.csv", csv_content, "text/csv")},
        )
        item = resp.json()["checkpoints"][0]
        assert set(item.keys()) >= {"id", "kind", "status", "payload_json", "approved_by"}
        assert item["approved_by"] == "system:import"


# ────────────────────────────────────────────────
# PUT /api/v1/checkpoints/{id}
# ────────────────────────────────────────────────


class TestUpdateCheckpoint:
    def test_update_existing(self, client, seed_checkpoint):
        """更新存在的审核点，应返回更新后内容。"""
        new_payload = '{"title": "已更新"}'
        resp = client.put(
            f"/api/v1/checkpoints/{seed_checkpoint.id}",
            json={"payload_json": new_payload},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == seed_checkpoint.id
        assert data["payload_json"] == new_payload

    def test_update_persists_to_db(self, client, seed_checkpoint, engine):
        """更新后 DB 中的记录应同步修改。"""
        new_payload = '{"title": "持久化验证"}'
        client.put(
            f"/api/v1/checkpoints/{seed_checkpoint.id}",
            json={"payload_json": new_payload},
        )
        with Session(engine) as session:
            final = session.get(CheckpointFinal, seed_checkpoint.id)
        assert final is not None
        assert final.payload_json == new_payload

    def test_update_nonexistent_returns_404(self, client):
        """更新不存在的 ID 应返回 404。"""
        resp = client.put(
            "/api/v1/checkpoints/nonexistent_id",
            json={"payload_json": '{"title": "任意"}'},
        )
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]


# ────────────────────────────────────────────────
# DELETE /api/v1/checkpoints/{id}
# ────────────────────────────────────────────────


class TestDeleteCheckpoint:
    def test_delete_existing(self, client, seed_checkpoint):
        """删除存在的审核点，应返回 204 No Content。"""
        resp = client.delete(f"/api/v1/checkpoints/{seed_checkpoint.id}")
        assert resp.status_code == 204
        assert resp.content == b""

    def test_delete_removes_from_db(self, client, seed_checkpoint, engine):
        """删除后 DB 中不应再有该记录。"""
        client.delete(f"/api/v1/checkpoints/{seed_checkpoint.id}")
        with Session(engine) as session:
            final = session.get(CheckpointFinal, seed_checkpoint.id)
        assert final is None

    def test_delete_nonexistent_returns_404(self, client):
        """删除不存在的 ID 应返回 404。"""
        resp = client.delete("/api/v1/checkpoints/nonexistent_id")
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]

    def test_list_after_delete_is_empty(self, client, seed_checkpoint):
        """删除唯一记录后 GET 应返回空列表。"""
        client.delete(f"/api/v1/checkpoints/{seed_checkpoint.id}")
        resp = client.get("/api/v1/checkpoints")
        assert resp.json() == []
