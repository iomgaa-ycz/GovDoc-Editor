#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export no_proxy="110.42.53.85,localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="110.42.53.85,localhost,127.0.0.1,${NO_PROXY:-}"
export HARNESS_MAX_CHECKPOINTS="${HARNESS_MAX_CHECKPOINTS:-2}"

LOG="/tmp/harness_l1_run_$(date +%s).log"
echo "=== L1 Quick Test (max_cp=$HARNESS_MAX_CHECKPOINTS) ===" > "$LOG"
echo "开始时间: $(date)" >> "$LOG"
echo "日志: $LOG"

/home/iomgaa/miniconda3/envs/govdoc-auditor-v3/bin/python -u \
    -m govdoc.harness.pipeline_eval \
    --manifest scripts/fixtures/harness_manifest.yaml \
    --project-root . \
    --rubric-dir scripts/rubrics \
    --db-path results/harness.db \
    >> "$LOG" 2>&1

EXIT_CODE=$?
echo "结束时间: $(date)" >> "$LOG"
echo "退出码: $EXIT_CODE" >> "$LOG"
echo "=== 完成 ===" >> "$LOG"
echo "退出码: $EXIT_CODE, 日志: $LOG"
