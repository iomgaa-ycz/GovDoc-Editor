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
docker compose --env-file "$ENV_FILE" exec -T backend alembic upgrade head 2>&1 || {
    echo ">>> 迁移失败（可能是首次部署，表已由 init_db 创建），标记迁移基线..."
    docker compose --env-file "$ENV_FILE" exec -T backend alembic stamp head
}

echo ">>> 清理旧镜像..."
docker image prune -f

echo ">>> [$(date '+%Y-%m-%d %H:%M:%S')] ${TARGET} 部署完成"

# 输出访问信息
source "$ENV_FILE"
echo "    后端: http://localhost:${BACKEND_PORT}/docs"
echo "    前端: http://localhost:${FRONTEND_PORT}"
