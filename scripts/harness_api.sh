#!/usr/bin/env bash
# L2 API harness 评估 — httpx 全端点冒烟 + 契约验证
set -euo pipefail
cd "$(dirname "$0")/.."

BASE_URL="${HARNESS_API_URL:-http://localhost:8000}"
export no_proxy="110.42.53.85,localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="110.42.53.85,localhost,127.0.0.1,${NO_PROXY:-}"

echo "=== L2 API Eval ==="
echo "目标: $BASE_URL"
echo "开始时间: $(date)"

# 检查服务是否可达
if ! curl -sf "${BASE_URL}/healthz" > /dev/null 2>&1; then
    echo "错误: FastAPI 服务不可达 ($BASE_URL/healthz)"
    echo "请先启动: conda run -n govdoc-auditor-v3 uvicorn govdoc.api.main:app --port 8000"
    exit 1
fi

conda run -n govdoc-auditor-v3 python -m govdoc.harness.api_eval \
    --base-url "$BASE_URL" \
    --manifest scripts/fixtures/harness_manifest.yaml \
    --project-root . \
    --db-path results/harness.db

echo "=== L2 完成 ==="
echo "结束时间: $(date)"
