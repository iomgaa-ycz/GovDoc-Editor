#!/usr/bin/env bash
# L1 管道 harness 评估 — 直接调用 run_extract / run_audit + HarnessJudge
set -euo pipefail
cd "$(dirname "$0")/.."

export no_proxy="110.42.53.85,localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="110.42.53.85,localhost,127.0.0.1,${NO_PROXY:-}"

echo "=== L1 Pipeline Eval ==="
echo "开始时间: $(date)"

conda run -n govdoc-auditor-v3 python -m govdoc.harness.pipeline_eval \
    --manifest scripts/fixtures/harness_manifest.yaml \
    --project-root . \
    --rubric-dir scripts/rubrics \
    --db-path results/harness.db

echo "=== L1 完成 ==="
echo "结束时间: $(date)"
