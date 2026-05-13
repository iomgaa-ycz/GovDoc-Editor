---
type: plan
node_id: plan:alembic-unify
title: "Alembic 统一数据库初始化计划"
date: 2026-05-13
migrated_from: docs/superpowers/plans/2026-04-21-init-db-alembic-unify.md
tags: ["migrated"]
---

# init_db 统一为 Alembic 迁移 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `init_db()` 内部实现从 `create_all()` 改为 `alembic upgrade head`，使数据库 schema 只有一个主人（Alembic），同时清理 deploy.sh 中的冗余迁移步骤。

**Architecture:** `init_db()` 的公共接口不变（调用方 `create_app()` 无需改动），内部实现改为调用 alembic 的 programmatic API。测试中的 `create_all()` 用于临时内存库，不受影响。deploy.sh 不再需要单独的 alembic exec 步骤。

**Tech Stack:** Alembic programmatic API (`alembic.config.Config`, `alembic.command.upgrade`)

**根因文档：** 见本次会话中的根因分析（init_db 与 alembic 双路径冲突）

---

## 文件变更概览

| 文件 | 操作 | 职责 |
|------|------|------|
| `govdoc/db/session.py` | MODIFY | `init_db()` 内部改为调用 alembic |
| `deploy/deploy.sh` | MODIFY | 移除 alembic exec 步骤及其 fallback |
| `tests/unit/test_init_db.py` | CREATE | 验证 `init_db()` 调用 alembic |

不变的文件：
- `govdoc/api/main.py` — 仍调用 `init_db()`，无需改动
- `govdoc/db/__init__.py` — 仍 re-export `init_db`，无需改动
- `govdoc/db/migrations/env.py` — 不变
- `tests/` 中的 `create_all()` — 临时内存库，不受影响

---

### Task 1: 修改 init_db() 实现

**Files:**
- Modify: `govdoc/db/session.py:22-23`
- Test: `tests/unit/test_init_db.py`

- [ ] **Step 1: 创建测试文件 `tests/unit/test_init_db.py`**

```python
"""验证 init_db 通过 alembic 管理 schema。"""

from unittest.mock import MagicMock, patch


def test_init_db_calls_alembic_upgrade():
    """init_db 必须调用 alembic.command.upgrade(cfg, 'head')。"""
    with patch("govdoc.db.session.alembic_command") as mock_cmd:
        from govdoc.db.session import init_db

        init_db()

        mock_cmd.upgrade.assert_called_once()
        args = mock_cmd.upgrade.call_args
        assert args[0][1] == "head"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_init_db.py -v`
Expected: FAIL（`init_db` 内部还未调用 alembic）

- [ ] **Step 3: 修改 `govdoc/db/session.py`**

将文件完整内容替换为：

```python
"""GovDoc 数据库引擎与 Session 依赖。"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlmodel import Session, SQLModel, create_engine

from govdoc.config import load_config

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def get_engine():
    config = load_config()
    connect_args = (
        {"check_same_thread": False} if config.app.database_url.startswith("sqlite") else {}
    )
    return create_engine(config.app.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    """通过 Alembic 迁移初始化/升级数据库 schema。

    幂等：已是最新版本时直接跳过。
    """
    cfg = AlembicConfig(str(_PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", load_config().app.database_url)
    alembic_command.upgrade(cfg, "head")
    logger.info("数据库迁移完成")


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
```

关键点：
- `_PROJECT_ROOT` 确保无论从哪里启动都能找到 `alembic.ini`
- `cfg.set_main_option` 显式传入 database_url，覆盖 alembic.ini 中的默认值，保证与 app 配置一致
- `alembic_command.upgrade(cfg, "head")` 是 alembic 的 programmatic API，等价于命令行 `alembic upgrade head`

- [ ] **Step 4: 运行测试验证通过**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_init_db.py -v`
Expected: PASS

- [ ] **Step 5: 运行全量单元测试确认无回归**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/ -v`
Expected: 全部 PASS（测试中的 `create_all()` 不受影响，它们用的是内存库）

- [ ] **Step 6: 提交**

```bash
git add govdoc/db/session.py tests/unit/test_init_db.py
git commit -m "refactor: init_db 改用 alembic programmatic API 替代 create_all"
```

---

### Task 2: 清理 deploy.sh

**Files:**
- Modify: `deploy/deploy.sh:20-27`

- [ ] **Step 1: 修改 `deploy/deploy.sh`**

移除 alembic 相关步骤（第 20-27 行），因为 app 启动时 `init_db()` 已自动执行 alembic upgrade head。

修改后的完整文件：

```bash
#!/bin/bash
set -euo pipefail

TARGET=${1:?用法: deploy.sh <stable|testing>}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE=".env.${TARGET}"
[ -f "$ENV_FILE" ] || { echo "错误: 找不到 $ENV_FILE"; exit 1; }
[ -f ".env.runtime" ] || { echo "错误: 找不到 .env.runtime（请从 .env.runtime.example 复制并填入密钥）"; exit 1; }

echo ">>> [$(date '+%Y-%m-%d %H:%M:%S')] 开始部署 ${TARGET} 环境..."

echo ">>> 构建镜像..."
docker compose --env-file "$ENV_FILE" build

echo ">>> 启动容器..."
docker compose --env-file "$ENV_FILE" up -d --force-recreate

echo ">>> 清理旧镜像..."
docker image prune -f

echo ">>> [$(date '+%Y-%m-%d %H:%M:%S')] ${TARGET} 部署完成"

# 输出访问信息
source "$ENV_FILE"
echo "    后端: http://localhost:${BACKEND_PORT}/docs"
echo "    前端: http://localhost:${FRONTEND_PORT}"
```

移除内容：
- `echo ">>> 等待后端就绪..."` + `sleep 5`
- `echo ">>> 执行数据库迁移..."` + `docker compose exec alembic` + fallback 逻辑

- [ ] **Step 2: 验证脚本语法**

Run: `bash -n deploy/deploy.sh && echo "syntax ok"`
Expected: `syntax ok`

- [ ] **Step 3: 提交**

```bash
git add deploy/deploy.sh
git commit -m "refactor: deploy.sh 移除 alembic 步骤（已由 app 启动自动执行）"
```

---

### Task 3: 本地验证 init_db 走 alembic 路径

**Files:** 无新增，纯验证

> 此 Task 在本地开发环境（开发机）执行。

- [ ] **Step 1: 删除本地 SQLite 以模拟全新启动**

```bash
rm -f data/app.sqlite
```

- [ ] **Step 2: 启动 FastAPI 确认 alembic 自动建表**

Run: `conda run -n govdoc-auditor-v3 uvicorn govdoc.api.main:app --host 0.0.0.0 --port 8000 &`

观察启动日志，应看到 alembic 迁移输出：
```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial, Initial GovDoc schema.
INFO  [alembic.runtime.migration] Running upgrade 0001_initial -> fd7c32702049, ...
```

- [ ] **Step 3: 验证 healthz 和 alembic_version**

```bash
curl http://localhost:8000/healthz
# Expected: {"status":"ok"}

conda run -n govdoc-auditor-v3 python -c "
import sqlite3
conn = sqlite3.connect('data/app.sqlite')
print('alembic_version:', conn.execute('SELECT version_num FROM alembic_version').fetchall())
print('tables:', [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()])
conn.close()
"
# Expected: alembic_version 有记录，tables 包含 project, auditrun 等
```

- [ ] **Step 4: 停止测试服务器**

```bash
kill %1 2>/dev/null || true
```

- [ ] **Step 5: 推送并通知部署服务器拉取**

```bash
git push origin master
```

部署服务器上执行：
```bash
git pull origin master
bash deploy/deploy.sh testing
```
