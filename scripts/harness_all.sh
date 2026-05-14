#!/usr/bin/env bash
# Harness 总入口：串行执行 L1 + L2
set -euo pipefail
cd "$(dirname "$0")/.."

export no_proxy="110.42.53.85,localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="110.42.53.85,localhost,127.0.0.1,${NO_PROXY:-}"

echo "========================================="
echo "  GovDoc Harness 端到端评估"
echo "  $(date)"
echo "========================================="

echo ""
echo "[1/2] L1 管道评估..."
bash scripts/harness_pipeline.sh

echo ""
echo "[2/2] L2 API 评估..."
bash scripts/harness_api.sh

echo ""
echo "========================================="
echo "  全部完成！结果: results/harness.db"
echo "  $(date)"
echo "========================================="
