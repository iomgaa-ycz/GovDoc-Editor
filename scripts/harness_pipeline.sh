#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

LOG_DIR="results/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/harness_pipeline_$(date +%Y%m%d_%H%M%S).log"

cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "=== L1 失败 (exit=$exit_code) ===" | tee -a "$LOG_FILE"
    fi
    echo "结束时间: $(date)" | tee -a "$LOG_FILE"
    echo "日志文件: $LOG_FILE"
}
trap cleanup EXIT

export no_proxy="110.42.53.85,localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="110.42.53.85,localhost,127.0.0.1,${NO_PROXY:-}"

echo "=== L1 Pipeline Eval ===" | tee "$LOG_FILE"
echo "开始时间: $(date)" | tee -a "$LOG_FILE"

conda run -n govdoc-auditor-v3 python -m govdoc.harness.pipeline_eval \
    --manifest scripts/fixtures/harness_manifest.yaml \
    --project-root . \
    --rubric-dir scripts/rubrics \
    --db-path results/harness.db \
    2>&1 | tee -a "$LOG_FILE"

echo "=== L1 完成 ===" | tee -a "$LOG_FILE"
