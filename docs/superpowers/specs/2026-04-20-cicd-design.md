# CI/CD 设计：双轨自动部署

> **日期**: 2026-04-20
> **状态**: 已确认，待实施
> **范围**: Docker 化 + GitHub Actions + 双环境自动部署

## 1. 目标

后端/前端代码更新后自动部署，支持两条部署轨道：

| 触发 | 目标环境 | 端口（后端/前端） |
|------|---------|-----------------|
| push `master` | 测试版 | 8001 / 5174 |
| push `v*` tag | 稳定版 | 8000 / 5173 |

部署目标为实验室 GPU 服务器（同一台机器），通过 Docker 化预留未来云迁移能力。

## 2. 架构概览

```
GitHub (push/tag)
    ↓
GitHub Actions (self-hosted runner on lab server)
    ↓
deploy.sh <stable|testing>
    ↓
docker compose --env-file .env.<target> build + up -d
    ↓
┌─────────────────────────────────────────┐
│  govdoc-stable (或 govdoc-testing)       │
│  ┌──────────┐     ┌───────────┐         │
│  │ frontend │:80  │  backend  │:8000    │
│  │ (nginx)  │────→│ (uvicorn) │         │
│  └──────────┘     └───────────┘         │
│       ↓ port map       ↓ port map       │
│   5173 (或 5174)   8000 (或 8001)       │
└─────────────────────────────────────────┘
         ↓ volume mount
    /data/govdoc-<target>/
```

## 3. 新增文件清单

```
deploy/
├── Dockerfile.backend       # 后端镜像（nvidia/cuda + Python 3.11）
├── Dockerfile.frontend      # 前端镜像（node 多阶段构建 + nginx）
├── nginx.conf               # 前端 nginx：SPA fallback + /api 反代
├── .env.stable              # 稳定版参数（提交 git）
├── .env.testing             # 测试版参数（提交 git）
├── .env.runtime.example     # 敏感信息模板（提交 git）
├── docker-compose.yml       # 参数化编排模板
└── deploy.sh                # 部署入口脚本
.github/
└── workflows/
    └── deploy.yml           # GitHub Actions workflow
```

## 4. 后端镜像 (`Dockerfile.backend`)

```dockerfile
FROM nvidia/cuda:12.1-runtime-ubuntu22.04

# 系统依赖 + Python 3.11（apt，不用 conda）
RUN apt-get update && apt-get install -y python3.11 python3-pip && \
    ln -s /usr/bin/python3.11 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layer 1: 依赖（变化少，利用缓存）
COPY pyproject.toml .
COPY vendor/scrivai-src/ vendor/scrivai-src/
RUN pip install --no-cache-dir -e vendor/scrivai-src && \
    pip install --no-cache-dir -e .

# Layer 2: 业务代码（变化频繁）
COPY govdoc/ govdoc/
COPY skills/ skills/
COPY agents/ agents/
COPY govdoc.yaml .
COPY templates/ templates/

EXPOSE 8000
CMD ["uvicorn", "govdoc.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**设计决策**:
- 基础镜像 `nvidia/cuda:12.1-runtime`：后端进程内跑 SentenceTransformer embedding，需 GPU
- 不用 conda：Docker 内直接 apt + pip，镜像更轻
- 容器内端口固定 8000：外部端口差异由 docker-compose port mapping 处理
- `./data/` 不打入镜像：通过 volume 挂载持久化

## 5. 前端镜像 (`Dockerfile.frontend`)

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
```

**设计决策**:
- 多阶段构建：最终镜像仅 nginx + 静态文件（约 30MB）
- `VITE_GOVDOC_API_BASE_URL` 保持为空：前端发相对路径 `/api/...`，由 nginx 反代到后端
- 容器内端口固定 80：外部端口差异由 docker-compose port mapping 处理

## 6. nginx 配置 (`nginx.conf`)

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;

    # SPA 路由 fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理到后端容器
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 健康检查代理
    location /healthz {
        proxy_pass http://backend:8000/healthz;
    }
}
```

**说明**: `backend` 是 docker-compose 内部 DNS 名，前端容器通过内部网络直连后端，不走宿主机端口。

## 7. docker-compose 模板

```yaml
# deploy/docker-compose.yml
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
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped

  frontend:
    build:
      context: ..
      dockerfile: deploy/Dockerfile.frontend
    ports:
      - "${FRONTEND_PORT}:80"
    depends_on:
      - backend
    restart: unless-stopped
```

## 8. 环境参数文件

```bash
# deploy/.env.stable
COMPOSE_PROJECT_NAME=govdoc-stable
BACKEND_PORT=8000
FRONTEND_PORT=5173
DATA_DIR=/data/govdoc-stable

# deploy/.env.testing
COMPOSE_PROJECT_NAME=govdoc-testing
BACKEND_PORT=8001
FRONTEND_PORT=5174
DATA_DIR=/data/govdoc-testing

# deploy/.env.runtime.example（敏感信息模板，实际 .env.runtime 不提交）
ANTHROPIC_API_KEY=
LOCAL_RANK=2
```

**`COMPOSE_PROJECT_NAME`** 使两套环境的容器、网络、卷完全命名隔离。

## 9. 部署脚本 (`deploy.sh`)

```bash
#!/bin/bash
set -euo pipefail
TARGET=${1:?用法: deploy.sh <stable|testing>}

ENV_FILE=".env.${TARGET}"
[ -f "$ENV_FILE" ] || { echo "找不到 $ENV_FILE"; exit 1; }

echo ">>> 部署 ${TARGET} 环境..."
docker compose --env-file "$ENV_FILE" build
docker compose --env-file "$ENV_FILE" up -d --force-recreate

# 自动应用数据库迁移
docker compose --env-file "$ENV_FILE" exec -T backend alembic upgrade head

docker image prune -f
echo ">>> ${TARGET} 部署完成"
```

## 10. GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [master]
    tags: ['v*']

jobs:
  deploy:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v4

      - name: 确定环境
        id: env
        run: |
          if [[ "$GITHUB_REF" == refs/tags/v* ]]; then
            echo "target=stable" >> $GITHUB_OUTPUT
          else
            echo "target=testing" >> $GITHUB_OUTPUT
          fi

      - name: 部署
        run: |
          cd deploy
          bash deploy.sh ${{ steps.env.outputs.target }}
```

## 11. 服务器前置条件

| 依赖 | 用途 | 检查命令 |
|------|------|---------|
| Docker Engine | 容器运行 | `docker --version` |
| Docker Compose V2 | 编排 | `docker compose version` |
| nvidia-container-toolkit | GPU 透传 | `nvidia-ctk --version` |
| GitHub Actions Runner | CI 执行 | `systemctl status actions.runner.*` |

### Self-hosted Runner 安装（一次性）

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
# 从 GitHub → Settings → Actions → Runners → New self-hosted runner 获取命令
curl -o actions-runner.tar.gz -L <RUNNER_URL>
tar xzf actions-runner.tar.gz
./config.sh --url https://github.com/iomgaa-ycz/GovDoc-Editor --token <TOKEN>
sudo ./svc.sh install   # systemd 守护，开机自启
sudo ./svc.sh start
```

### 数据目录初始化（一次性）

```bash
sudo mkdir -p /data/govdoc-stable /data/govdoc-testing
sudo chown $(whoami):$(whoami) /data/govdoc-stable /data/govdoc-testing
```

## 12. 回滚策略

| 场景 | 操作 |
|------|------|
| 测试版回滚 | 再次 push master（修复后的 commit） |
| 稳定版回滚 | 推送旧版 tag 或在服务器手动 `cd deploy && bash deploy.sh stable` |
| 数据回滚 | MVP 不做自动备份，SQLite 文件可手动拷贝恢复 |

## 13. 不做的事（MVP 边界）

- 不加 HTTPS（内网环境）
- 不加监控/告警（`docker compose logs -f` 足够）
- 不加统一反向代理入口（直接端口访问）
- 不做自动数据备份
- 不加 CI 测试步骤（后续可在 deploy 前加 test job）

## 14. 未来扩展路径

| 阶段 | 可选增强 |
|------|---------|
| 上云 | docker-compose.yml 几乎不变，改 `.env` 端口 + `DATA_DIR` 即可 |
| HTTPS | 加 nginx/traefik 反向代理 + Let's Encrypt |
| 监控 | 加 Prometheus + Grafana 容器 |
| CI 测试 | 在 deploy job 前加 test job（`pytest` + `ruff check`） |
| 数据备份 | cron 定时 SQLite `.backup` 到对象存储 |
