"""
迁移单元测试：20260427_remove_checkpointdraft

测试范围：
- 未 promoted 草稿 → 迁移到 checkpointfinal
- upgrade 后 checkpointdraft 表不存在
- 相同 ID 时不覆盖已有 final 记录（NOT EXISTS 去重）
- status='promoted' 的草稿不被迁移

技术约束：
- 纯 SQLAlchemy 内存 SQLite，不走 Alembic runner
- 不依赖项目模型；手动建表模拟迁移前 schema
"""

import sqlalchemy as sa


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _create_pre_migration_tables(engine: sa.Engine) -> None:
    """建立迁移前的 checkpointfinal + checkpointdraft 表。"""
    with engine.begin() as conn:
        conn.execute(
            sa.text("""
            CREATE TABLE checkpointfinal (
                id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                approved_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )
        conn.execute(
            sa.text("""
            CREATE TABLE checkpointdraft (
                id TEXT PRIMARY KEY,
                rule_source_id TEXT,
                payload_json TEXT NOT NULL,
                extract_run_id TEXT,
                status TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        )


def _run_upgrade(engine: sa.Engine) -> None:
    """执行与迁移 upgrade() 等价的 SQL。"""
    with engine.begin() as conn:
        conn.execute(
            sa.text("""
            INSERT INTO checkpointfinal (id, payload_json, approved_by, approved_at)
            SELECT d.id, d.payload_json, 'migration:checkpoint-draft', CURRENT_TIMESTAMP
            FROM checkpointdraft AS d
            WHERE d.status != 'promoted'
              AND NOT EXISTS (
                SELECT 1 FROM checkpointfinal AS f WHERE f.id = d.id
              )
        """)
        )
        conn.execute(sa.text("DROP TABLE checkpointdraft"))


def _insert_draft(
    conn: sa.Connection,
    id: str,
    payload_json: str = '{"k": "v"}',
    status: str = "pending",
) -> None:
    """向 checkpointdraft 插入一条记录。"""
    conn.execute(
        sa.text(
            "INSERT INTO checkpointdraft (id, rule_source_id, payload_json, extract_run_id, status)"
            " VALUES (:id, NULL, :payload_json, NULL, :status)"
        ),
        {"id": id, "payload_json": payload_json, "status": status},
    )


def _insert_final(
    conn: sa.Connection,
    id: str,
    payload_json: str = '{"existing": true}',
    approved_by: str = "human",
) -> None:
    """向 checkpointfinal 插入一条记录。"""
    conn.execute(
        sa.text(
            "INSERT INTO checkpointfinal (id, payload_json, approved_by, approved_at)"
            " VALUES (:id, :payload_json, :approved_by, CURRENT_TIMESTAMP)"
        ),
        {"id": id, "payload_json": payload_json, "approved_by": approved_by},
    )


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------


class TestMigrationRemoveCheckpointDraft:
    """迁移 remove_checkpointdraft 行为验证。"""

    def test_upgrade_migrates_unpromoted_drafts(self):
        """未 promoted 的草稿应被写入 checkpointfinal，approved_by 为 'migration:checkpoint-draft'。"""
        engine = sa.create_engine("sqlite://")
        _create_pre_migration_tables(engine)

        with engine.begin() as conn:
            _insert_draft(conn, "draft-1", '{"rule": "A"}', status="pending")
            _insert_draft(conn, "draft-2", '{"rule": "B"}', status="rejected")

        _run_upgrade(engine)

        with engine.connect() as conn:
            rows = conn.execute(
                sa.text("SELECT id, payload_json, approved_by FROM checkpointfinal ORDER BY id")
            ).fetchall()

        assert len(rows) == 2
        ids = {r[0] for r in rows}
        assert "draft-1" in ids
        assert "draft-2" in ids
        for row in rows:
            assert row[2] == "migration:checkpoint-draft", (
                f"approved_by 应为 'migration:checkpoint-draft'，实际：{row[2]}"
            )

    def test_upgrade_drops_checkpointdraft_table(self):
        """upgrade 执行后，checkpointdraft 表应不存在。"""
        engine = sa.create_engine("sqlite://")
        _create_pre_migration_tables(engine)

        with engine.begin() as conn:
            _insert_draft(conn, "draft-x", status="pending")

        _run_upgrade(engine)

        with engine.connect() as conn:
            result = conn.execute(
                sa.text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='checkpointdraft'"
                )
            ).fetchone()
        assert result is None, "upgrade 后 checkpointdraft 表应已被删除"

    def test_upgrade_skips_duplicate_ids(self):
        """
        draft 与 final 拥有相同 ID 时，NOT EXISTS 去重保护应生效：
        - final 记录的 approved_by 不被覆盖
        - payload_json 保持原值
        """
        engine = sa.create_engine("sqlite://")
        _create_pre_migration_tables(engine)

        with engine.begin() as conn:
            # checkpointfinal 已有 id='dup-1'
            _insert_final(conn, "dup-1", '{"existing": true}', approved_by="human")
            # checkpointdraft 也有 id='dup-1'（未 promoted）
            _insert_draft(conn, "dup-1", '{"from_draft": true}', status="pending")
            # 无冲突的草稿
            _insert_draft(conn, "new-1", '{"new": true}', status="pending")

        _run_upgrade(engine)

        with engine.connect() as conn:
            rows = {
                r[0]: {"payload_json": r[1], "approved_by": r[2]}
                for r in conn.execute(
                    sa.text("SELECT id, payload_json, approved_by FROM checkpointfinal")
                ).fetchall()
            }

        # dup-1 应保持原值，不被 draft 覆盖
        assert "dup-1" in rows
        assert rows["dup-1"]["approved_by"] == "human", (
            f"dup-1 的 approved_by 不应被覆盖，实际：{rows['dup-1']['approved_by']}"
        )
        assert rows["dup-1"]["payload_json"] == '{"existing": true}', (
            f"dup-1 的 payload_json 不应被覆盖，实际：{rows['dup-1']['payload_json']}"
        )

        # new-1 正常迁移
        assert "new-1" in rows
        assert rows["new-1"]["approved_by"] == "migration:checkpoint-draft"

    def test_upgrade_skips_promoted_drafts(self):
        """
        status='promoted' 的草稿不应被插入 checkpointfinal。

        业务逻辑：promoted 草稿已提升为 final 记录，WHERE status != 'promoted' 应过滤掉它们。
        """
        engine = sa.create_engine("sqlite://")
        _create_pre_migration_tables(engine)

        with engine.begin() as conn:
            _insert_draft(conn, "promoted-1", '{"rule": "P"}', status="promoted")
            _insert_draft(conn, "pending-1", '{"rule": "Q"}', status="pending")

        _run_upgrade(engine)

        with engine.connect() as conn:
            rows = conn.execute(sa.text("SELECT id FROM checkpointfinal")).fetchall()
            ids = {r[0] for r in rows}

        assert "promoted-1" not in ids, "promoted 草稿不应被迁移到 checkpointfinal"
        assert "pending-1" in ids, "pending 草稿应被迁移到 checkpointfinal"
