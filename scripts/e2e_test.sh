#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# GovDoc Auditor 前后端 E2E 测试
#
# 使用方式：
#   bash scripts/e2e_test.sh              # 跑全部 3 轮（含 LLM）
#   bash scripts/e2e_test.sh --quick      # 只跑 Round 1+2（无 LLM，< 1 分钟）
#   bash scripts/e2e_test.sh --round 1    # 只跑指定轮次
#
# 前置条件：
#   - conda 环境 govdoc-auditor-v3 可用
#   - npm 依赖已安装（frontend/node_modules 存在）
#   - real_data/ 目录包含测试数据（Round 2+3 需要）
#   - .env 文件包含 LLM API Key（Round 3 需要）
# ─────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."

# ── 配置 ──
LAN_IP="${E2E_LAN_IP:-100.97.33.50}"
BACKEND_PORT="${E2E_BACKEND_PORT:-8000}"
FRONTEND_PORT="${E2E_FRONTEND_PORT:-5173}"
BASE_URL="http://${LAN_IP}:${FRONTEND_PORT}"

export no_proxy="${LAN_IP},110.42.53.85,100.81.95.44,localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="${LAN_IP},110.42.53.85,100.81.95.44,localhost,127.0.0.1,${NO_PROXY:-}"

# ── 参数解析 ──
QUICK=false
ROUND=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --quick) QUICK=true; shift ;;
        --round) ROUND="$2"; shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

LOG_DIR="results/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/e2e_$(date +%Y%m%d_%H%M%S).log"

echo "=========================================" | tee "$LOG_FILE"
echo "  GovDoc E2E 测试" | tee -a "$LOG_FILE"
echo "  $(date)" | tee -a "$LOG_FILE"
echo "  目标: ${BASE_URL}" | tee -a "$LOG_FILE"
echo "  模式: ${QUICK:+快速（Round 1+2）}${ROUND:+Round ${ROUND}}${QUICK:-${ROUND:-全量（Round 1+2+3）}}" | tee -a "$LOG_FILE"
echo "=========================================" | tee -a "$LOG_FILE"

# ── Phase 0: 重置数据库 ──
echo "" | tee -a "$LOG_FILE"
echo "[Phase 0] 重置数据库..." | tee -a "$LOG_FILE"
rm -f data/app.sqlite
eval "$(conda shell.bash hook)" && conda activate govdoc-auditor-v3
alembic upgrade head >> "$LOG_FILE" 2>&1
echo "  ✓ 数据库已重置" | tee -a "$LOG_FILE"

# ── Phase 1: 启动服务 ──
echo "" | tee -a "$LOG_FILE"
echo "[Phase 1] 启动后端和前端..." | tee -a "$LOG_FILE"

# 清理旧进程
tmux kill-session -t govdoc-backend 2>/dev/null || true
tmux kill-session -t govdoc-frontend 2>/dev/null || true
kill $(lsof -t -i :"${BACKEND_PORT}") 2>/dev/null || true
kill $(lsof -t -i :"${FRONTEND_PORT}") 2>/dev/null || true
sleep 2

# 启动后端
tmux new-session -d -s govdoc-backend \
    "eval \"\$(conda shell.bash hook)\" && conda activate govdoc-auditor-v3 && \
     export no_proxy='${no_proxy}' && export NO_PROXY='${NO_PROXY}' && \
     uvicorn govdoc.api.main:app --host 0.0.0.0 --port ${BACKEND_PORT}; \
     echo '=== BACKEND STOPPED ==='; sleep 86400"

# 启动前端
tmux new-session -d -s govdoc-frontend \
    "cd $(pwd)/frontend && npx vite --host 0.0.0.0 --port ${FRONTEND_PORT}; \
     echo '=== FRONTEND STOPPED ==='; sleep 86400"

# 等待服务就绪
echo "  等待服务启动..." | tee -a "$LOG_FILE"
for i in $(seq 1 30); do
    if curl -sf "http://${LAN_IP}:${BACKEND_PORT}/healthz" > /dev/null 2>&1 && \
       curl -sf -o /dev/null "http://${LAN_IP}:${FRONTEND_PORT}/" 2>&1; then
        echo "  ✓ 后端: http://${LAN_IP}:${BACKEND_PORT}" | tee -a "$LOG_FILE"
        echo "  ✓ 前端: http://${LAN_IP}:${FRONTEND_PORT}" | tee -a "$LOG_FILE"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  ✗ 服务启动超时" | tee -a "$LOG_FILE"
        exit 1
    fi
    sleep 2
done

# ── Phase 2: 运行 Playwright 测试 ──
cd frontend
PLAYWRIGHT_CMD="npx playwright test --reporter=list"
EXIT_CODE=0

run_round() {
    local round=$1
    local spec=$2
    local desc=$3
    echo "" | tee -a "../$LOG_FILE"
    echo "[Round ${round}] ${desc}..." | tee -a "../$LOG_FILE"
    if NO_PROXY="${NO_PROXY}" $PLAYWRIGHT_CMD "e2e/${spec}" 2>&1 | tee -a "../$LOG_FILE"; then
        echo "  ✓ Round ${round} 通过" | tee -a "../$LOG_FILE"
    else
        echo "  ✗ Round ${round} 失败" | tee -a "../$LOG_FILE"
        EXIT_CODE=1
    fi
}

if [ -n "$ROUND" ]; then
    case "$ROUND" in
        1) run_round 1 "round1-smoke.spec.ts" "烟雾测试（6 页面 + 导航）" ;;
        2) run_round 2 "round2-no-llm.spec.ts" "非 LLM 功能（导入审核点 + 文件对比）" ;;
        3) run_round 3 "round3-llm.spec.ts" "LLM 功能（AI 提取 + AI 审核）" ;;
        *) echo "无效轮次: $ROUND（可选 1/2/3）"; exit 1 ;;
    esac
elif [ "$QUICK" = true ]; then
    run_round 1 "round1-smoke.spec.ts" "烟雾测试（6 页面 + 导航）"
    run_round 2 "round2-no-llm.spec.ts" "非 LLM 功能（导入审核点 + 文件对比）"
else
    run_round 1 "round1-smoke.spec.ts" "烟雾测试（6 页面 + 导航）"
    run_round 2 "round2-no-llm.spec.ts" "非 LLM 功能（导入审核点 + 文件对比）"
    run_round 3 "round3-llm.spec.ts" "LLM 功能（AI 提取 + AI 审核）"
fi

cd ..

# ── Phase 3: 清理 ──
echo "" | tee -a "$LOG_FILE"
echo "=========================================" | tee -a "$LOG_FILE"
if [ $EXIT_CODE -eq 0 ]; then
    echo "  ✓ 全部测试通过" | tee -a "$LOG_FILE"
else
    echo "  ✗ 存在失败的测试" | tee -a "$LOG_FILE"
fi
echo "  日志: $LOG_FILE" | tee -a "$LOG_FILE"
echo "  报告: frontend/playwright-report/index.html" | tee -a "$LOG_FILE"
echo "  $(date)" | tee -a "$LOG_FILE"
echo "=========================================" | tee -a "$LOG_FILE"

# 保留服务运行（方便调试），若需停止可执行：
# tmux kill-session -t govdoc-backend && tmux kill-session -t govdoc-frontend

exit $EXIT_CODE
