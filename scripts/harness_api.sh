#!/usr/bin/env bash
# L2 API harness 评估 — 端到端（含 Pipeline A/B + workpaper + 语义评估）
set -euo pipefail
cd "$(dirname "$0")/.."

BASE_URL="${HARNESS_API_URL:-http://localhost:8000}"
export no_proxy="110.42.53.85,100.81.95.44,localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="110.42.53.85,100.81.95.44,localhost,127.0.0.1,${NO_PROXY:-}"

LOG_DIR="results/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/harness_api_$(date +%Y%m%d_%H%M%S).log"

echo "=== L2 API Eval ===" | tee "$LOG_FILE"
echo "目标: $BASE_URL" | tee -a "$LOG_FILE"
echo "开始时间: $(date)" | tee -a "$LOG_FILE"
echo "HARNESS_MAX_CHECKPOINTS=${HARNESS_MAX_CHECKPOINTS:-0 (全量)}" | tee -a "$LOG_FILE"
echo "HARNESS_PIPELINE_TIMEOUT=${HARNESS_PIPELINE_TIMEOUT:-7200}" | tee -a "$LOG_FILE"

# 检查服务是否可达
if ! curl -sf "${BASE_URL}/healthz" > /dev/null 2>&1; then
    echo "错误: FastAPI 服务不可达 ($BASE_URL/healthz)" | tee -a "$LOG_FILE"
    echo "请先启动: source activate govdoc-auditor-v3 && uvicorn govdoc.api.main:app --port 8000" | tee -a "$LOG_FILE"
    exit 1
fi

source activate govdoc-auditor-v3 && python -m govdoc.harness.api_eval \
    --base-url "$BASE_URL" \
    --manifest scripts/fixtures/harness_manifest.yaml \
    --project-root . \
    --rubric-dir scripts/rubrics \
    --db-path results/harness.db \
    2>&1 | tee -a "$LOG_FILE"

echo "=== L2 完成 ===" | tee -a "$LOG_FILE"
echo "结束时间: $(date)" | tee -a "$LOG_FILE"
echo "日志: $LOG_FILE"
