#!/bin/bash
set -euo pipefail

TARGET=${1:?用法: deploy.sh <stable|testing>}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE=".env.${TARGET}"
[ -f "$ENV_FILE" ] || { echo "错误: 找不到 $ENV_FILE"; exit 1; }
# .env.runtime 查找顺序: deploy/ 目录 → 固定位置 /data/govdoc/.env.runtime
if [ ! -f ".env.runtime" ]; then
    GLOBAL_RUNTIME="/data/govdoc/.env.runtime"
    if [ -f "$GLOBAL_RUNTIME" ]; then
        ln -sf "$GLOBAL_RUNTIME" .env.runtime
        echo ">>> 使用全局 .env.runtime: $GLOBAL_RUNTIME"
    else
        echo "错误: 找不到 .env.runtime"
        echo "  方式1: 复制 .env.runtime.example 到 deploy/.env.runtime"
        echo "  方式2: 放到 $GLOBAL_RUNTIME（推荐，CI/CD 友好）"
        exit 1
    fi
fi

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
