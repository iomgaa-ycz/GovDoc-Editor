---
type: plan
node_id: plan:cicd-deploy
title: "CI/CD Docker 部署计划"
date: 2026-05-13
migrated_from: docs/superpowers/plans/2026-04-20-cicd-deploy.md
tags: ["migrated"]
---

# CI/CD 双轨自动部署 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Docker 化双轨自动部署 — push master 部署测试版，push tag 部署稳定版。

**Architecture:** 前后端各一个 Docker 镜像，单 docker-compose.yml 通过 env 文件参数化两套环境，GitHub Actions self-hosted runner 在服务器本地构建并部署。

**Tech Stack:** Docker, Docker Compose, nginx, GitHub Actions, nvidia-container-toolkit

**Design Spec:** `docs/superpowers/specs/2026-04-20-cicd-design.md`

**设计修正（相对 spec 的发现）：**
- `vendor/scrivai-src/` 在磁盘上不存在（`.gitignore` 已忽略 `vendor/`），scrivai 是 PyPI 依赖，Dockerfile 无需 COPY vendor
- 模板路径为 `govdoc/templates/workpaper.docx`，非 `templates/`
- `.gitignore` 含 `.env.*` 全局规则，需加 `!deploy/.env.*` 排除

---

### Task 1: .dockerignore 与 .gitignore 更新

**Files:**
- Create: `.dockerignore`
- Modify: `.gitignore`

- [ ] **Step 1: 创建 `.dockerignore`**

Docker build context 是项目根目录（docker-compose 中 `context: ..`），需排除无关文件以加速构建。

```
# .dockerignore
.git/
.github/
.claude/
.graphify_python/
.playwright/
.playwright-cli/
graphify-out/
docs/
tests/
data/
node_modules/
frontend/node_modules/
frontend/dist/
frontend/coverage/
*.sqlite
*.sqlite3
*.log
__pycache__/
*.py[cod]
*.egg-info/
.env
.env.*
.ruff_cache/
.pytest_cache/
.mypy_cache/
.vscode/
.idea/
```

- [ ] **Step 2: 更新 `.gitignore` 放行 deploy env 文件**

在 `.gitignore` 末尾添加：

```gitignore
# deploy 环境参数（非敏感，允许提交）
!deploy/.env.stable
!deploy/.env.testing
!deploy/.env.runtime.example
```

- [ ] **Step 3: 验证 gitignore 规则生效**

Run: `git check-ignore -v deploy/.env.stable`
Expected: 无输出（表示不被忽略）

如果仍被忽略，需要在 `.env.*` 规则前加更精确的路径。

- [ ] **Step 4: 提交**

```bash
git add .dockerignore .gitignore
git commit -m "build: 添加 .dockerignore，放行 deploy env 文件"
```

---

### Task 2: 后端 Dockerfile

**Files:**
- Create: `deploy/Dockerfile.backend`

- [ ] **Step 1: 创建 `deploy/Dockerfile.backend`**

```dockerfile
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3.11-dev python3-pip && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layer 1: 依赖（变化少，利用 Docker 缓存）
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Layer 2: 业务代码（变化频繁）
COPY govdoc/ govdoc/
COPY skills/ skills/
COPY agents/ agents/
COPY govdoc.yaml .
COPY alembic.ini .

EXPOSE 8000
CMD ["uvicorn", "govdoc.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

注意点：
- Ubuntu 22.04 默认 Python 3.10，需 `deadsnakes` PPA 安装 3.11
- `alembic.ini` 需打入镜像（deploy.sh 中 exec alembic 需要）
- 模板 `govdoc/templates/workpaper.docx` 已随 `COPY govdoc/ govdoc/` 一并打入
- scrivai 作为 PyPI 依赖由 `pip install -e .` 自动拉取

- [ ] **Step 2: 验证镜像构建**

Run: `docker build -f deploy/Dockerfile.backend -t govdoc-backend:test .`
Expected: 构建成功，无错误

- [ ] **Step 3: 验证镜像能启动（不挂 GPU 和数据卷，仅测语法）**

Run: `docker run --rm govdoc-backend:test python -c "import govdoc; print('ok')"`
Expected: 输出 `ok`

- [ ] **Step 4: 清理测试镜像并提交**

```bash
docker rmi govdoc-backend:test 2>/dev/null || true
git add deploy/Dockerfile.backend
git commit -m "build: 添加后端 Dockerfile（nvidia/cuda + Python 3.11）"
```

---

### Task 3: 前端 Dockerfile 与 nginx 配置

**Files:**
- Create: `deploy/Dockerfile.frontend`
- Create: `deploy/nginx.conf`

- [ ] **Step 1: 创建 `deploy/nginx.conf`**

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # SPA 路由 fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理到后端容器
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 健康检查代理
    location /healthz {
        proxy_pass http://backend:8000/healthz;
    }

    # 运行时诊断代理
    location /runtime/ {
        proxy_pass http://backend:8000/runtime/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

- [ ] **Step 2: 创建 `deploy/Dockerfile.frontend`**

```dockerfile
# Stage 1: 构建
FROM node:20-alpine AS builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: 运行
FROM nginx:alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist/ /usr/share/nginx/html/
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 3: 验证前端镜像构建**

Run: `docker build -f deploy/Dockerfile.frontend -t govdoc-frontend:test .`
Expected: 构建成功（包含 tsc 编译 + vite build）

- [ ] **Step 4: 验证 nginx 配置语法**

Run: `docker run --rm govdoc-frontend:test nginx -t`
Expected: `nginx: configuration file /etc/nginx/nginx.conf syntax is ok`

- [ ] **Step 5: 清理测试镜像并提交**

```bash
docker rmi govdoc-frontend:test 2>/dev/null || true
git add deploy/Dockerfile.frontend deploy/nginx.conf
git commit -m "build: 添加前端 Dockerfile（多阶段构建）与 nginx 配置"
```

---

### Task 4: docker-compose 与环境参数文件

**Files:**
- Create: `deploy/docker-compose.yml`
- Create: `deploy/.env.stable`
- Create: `deploy/.env.testing`
- Create: `deploy/.env.runtime.example`

- [ ] **Step 1: 创建 `deploy/docker-compose.yml`**

```yaml
services:
  backend:
    build:
      context: ..
      dockerfile: deploy/Dockerfile.backend
    ports:
      - "${BACKEND_PORT}:8000"
    volumes:
      - ${DATA_DIR}:/app/data
    env_file:
      - .env.runtime
    environment:
      - GOVDOC_CONFIG_PATH=/app/govdoc.yaml
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  frontend:
    build:
      context: ..
      dockerfile: deploy/Dockerfile.frontend
    ports:
      - "${FRONTEND_PORT}:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
```

- [ ] **Step 2: 创建 `deploy/.env.stable`**

```bash
COMPOSE_PROJECT_NAME=govdoc-stable
BACKEND_PORT=8000
FRONTEND_PORT=5173
DATA_DIR=/data/govdoc-stable
```

- [ ] **Step 3: 创建 `deploy/.env.testing`**

```bash
COMPOSE_PROJECT_NAME=govdoc-testing
BACKEND_PORT=8001
FRONTEND_PORT=5174
DATA_DIR=/data/govdoc-testing
```

- [ ] **Step 4: 创建 `deploy/.env.runtime.example`**

```bash
# 敏感信息 — 实际 .env.runtime 不提交 git
# 复制此文件为 .env.runtime 并填入真实值
ANTHROPIC_API_KEY=
LOCAL_RANK=2
```

- [ ] **Step 5: 验证 compose 配置语法**

Run: `cd deploy && docker compose --env-file .env.testing config --quiet && echo "syntax ok"`
Expected: `syntax ok`（忽略 GPU 相关警告，仅验证 YAML 语法）

- [ ] **Step 6: 提交**

```bash
git add deploy/docker-compose.yml deploy/.env.stable deploy/.env.testing deploy/.env.runtime.example
git commit -m "build: 添加 docker-compose 模板与双环境参数文件"
```

---

### Task 5: 部署脚本

**Files:**
- Create: `deploy/deploy.sh`

- [ ] **Step 1: 创建 `deploy/deploy.sh`**

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

echo ">>> 等待后端就绪..."
sleep 5

echo ">>> 执行数据库迁移..."
docker compose --env-file "$ENV_FILE" exec -T backend alembic upgrade head

echo ">>> 清理旧镜像..."
docker image prune -f

echo ">>> [$(date '+%Y-%m-%d %H:%M:%S')] ${TARGET} 部署完成"

# 输出访问信息
source "$ENV_FILE"
echo "    后端: http://localhost:${BACKEND_PORT}/docs"
echo "    前端: http://localhost:${FRONTEND_PORT}"
```

- [ ] **Step 2: 设置可执行权限**

Run: `chmod +x deploy/deploy.sh`

- [ ] **Step 3: 验证脚本语法**

Run: `bash -n deploy/deploy.sh && echo "syntax ok"`
Expected: `syntax ok`

- [ ] **Step 4: 提交**

```bash
git add deploy/deploy.sh
git commit -m "build: 添加部署入口脚本 deploy.sh"
```

---

### Task 6: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: 创建目录**

Run: `mkdir -p .github/workflows`

- [ ] **Step 2: 创建 `.github/workflows/deploy.yml`**

```yaml
name: Deploy

on:
  push:
    branches: [master]
    tags: ['v*']

# 同一时间只允许一个部署任务运行，后来的取消前面排队的
concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: self-hosted
    timeout-minutes: 15
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: 确定部署环境
        id: env
        run: |
          if [[ "$GITHUB_REF" == refs/tags/v* ]]; then
            echo "target=stable" >> "$GITHUB_OUTPUT"
            echo ">>> 部署目标: 稳定版 (tag: $GITHUB_REF_NAME)"
          else
            echo "target=testing" >> "$GITHUB_OUTPUT"
            echo ">>> 部署目标: 测试版 (commit: ${GITHUB_SHA::8})"
          fi

      - name: 执行部署
        run: bash deploy/deploy.sh ${{ steps.env.outputs.target }}

      - name: 健康检查
        run: |
          if [ "${{ steps.env.outputs.target }}" = "stable" ]; then
            PORT=8000
          else
            PORT=8001
          fi
          echo ">>> 检查 http://localhost:${PORT}/healthz ..."
          for i in $(seq 1 10); do
            if curl -sf "http://localhost:${PORT}/healthz" > /dev/null 2>&1; then
              echo ">>> 健康检查通过"
              exit 0
            fi
            echo "    等待后端启动... ($i/10)"
            sleep 3
          done
          echo ">>> 健康检查失败"
          exit 1
```

- [ ] **Step 3: 验证 YAML 语法**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml')); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 4: 提交**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: 添加 GitHub Actions 双轨部署 workflow"
```

---

### Task 7: 端到端本地验证

**Files:** 无新增文件，纯验证

> 此 Task 需要在部署目标服务器上执行（需要 Docker + GPU）。
> 如果当前开发机不是部署服务器，可以跳过 GPU 相关验证，仅验证构建。

- [ ] **Step 1: 确认前置条件**

```bash
docker --version
docker compose version
nvidia-smi  # 确认 GPU 可用
```

- [ ] **Step 2: 创建 `.env.runtime`**

```bash
cp deploy/.env.runtime.example deploy/.env.runtime
# 编辑 deploy/.env.runtime 填入真实的 ANTHROPIC_API_KEY
```

- [ ] **Step 3: 创建数据目录**

```bash
sudo mkdir -p /data/govdoc-testing
sudo chown $(whoami):$(whoami) /data/govdoc-testing
```

- [ ] **Step 4: 部署测试版**

Run: `bash deploy/deploy.sh testing`
Expected: 构建成功，容器启动，迁移执行，输出访问地址

- [ ] **Step 5: 验证服务**

```bash
# 后端健康检查
curl -s http://localhost:8001/healthz
# Expected: {"status":"ok"}

# 前端页面
curl -s http://localhost:5174/ | head -5
# Expected: HTML 内容（含 <div id="root">）

# 前端 → nginx → 后端 反代链路
curl -s http://localhost:5174/healthz
# Expected: {"status":"ok"}（通过 nginx 代理到后端）
```

- [ ] **Step 6: 查看日志确认无报错**

```bash
cd deploy
docker compose --env-file .env.testing logs --tail=20
```

- [ ] **Step 7: 清理测试环境（可选）**

```bash
cd deploy
docker compose --env-file .env.testing down
```

---

### Task 8: Self-hosted Runner 安装（服务器一次性操作）

**Files:** 无项目文件变更，纯服务器配置

> 此 Task 在部署目标服务器上手动执行，不由 CI 自动化。

- [ ] **Step 1: 在 GitHub 获取 runner token**

浏览器打开: `https://github.com/iomgaa-ycz/GovDoc-Editor/settings/actions/runners/new`
选择 Linux x64，复制安装命令中的 token。

- [ ] **Step 2: 安装 runner**

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -o actions-runner-linux-x64-2.321.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz
tar xzf actions-runner-linux-x64-2.321.0.tar.gz
./config.sh --url https://github.com/iomgaa-ycz/GovDoc-Editor --token <你的TOKEN>
```

配置时选择默认标签 `self-hosted, Linux, X64`。

- [ ] **Step 3: 注册为 systemd 服务**

```bash
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

Expected: `Active: active (running)`

- [ ] **Step 4: 创建稳定版数据目录**

```bash
sudo mkdir -p /data/govdoc-stable
sudo chown $(whoami):$(whoami) /data/govdoc-stable
```

- [ ] **Step 5: 验证 runner 在线**

浏览器打开: `https://github.com/iomgaa-ycz/GovDoc-Editor/settings/actions/runners`
Expected: 看到 runner 状态为 `Idle`（绿色）

- [ ] **Step 6: 端到端测试 — push master 触发自动部署**

```bash
# 在开发机上推送一个测试 commit
git push origin master
```

浏览器打开: `https://github.com/iomgaa-ycz/GovDoc-Editor/actions`
Expected: 看到 Deploy workflow 运行中，target=testing，最终成功。

- [ ] **Step 7: 端到端测试 — push tag 触发稳定版部署**

```bash
git tag v0.1.0
git push origin v0.1.0
```

Expected: Deploy workflow 运行，target=stable，稳定版在 :8000/:5173 启动。
