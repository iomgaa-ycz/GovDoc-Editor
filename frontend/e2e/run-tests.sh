#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# GovDoc E2E 测试运行器（基于 @playwright/cli）
#
# 用法：
#   bash frontend/e2e/run-tests.sh                    # 运行全部 5 个测试（含 LLM）
#   bash frontend/e2e/run-tests.sh --quick            # 仅运行非 LLM 测试（01-03）
#   bash frontend/e2e/run-tests.sh --only 02          # 只运行指定测试
# ─────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."

export NO_PROXY="100.70.102.30,100.83.164.94,110.42.53.85,localhost,127.0.0.1"
export no_proxy="$NO_PROXY"

BASE_URL="${E2E_BASE_URL:-http://100.70.102.30:8080}"
BACKEND_URL="${E2E_BACKEND_URL:-http://100.83.164.94:8001}"
PROJECT_ROOT="$(cd .. && pwd)"
SCREENSHOT_DIR="e2e/screenshots"
CLI="npx playwright-cli"
SESSION="govdoc-e2e"

PASSED=0
FAILED=0
SKIPPED=0
RESULTS=()

mkdir -p "$SCREENSHOT_DIR"

# ── 参数解析 ──
QUICK=false
ONLY=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --quick) QUICK=true; shift ;;
        --only) ONLY="$2"; shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# ── 测试清单 ──
ALL_TESTS=("01-navigation" "02-import-checkpoints" "03-doc-compare" "04-ai-extract" "05-ai-audit")
QUICK_TESTS=("01-navigation" "02-import-checkpoints" "03-doc-compare")

if [ -n "$ONLY" ]; then
    TESTS=("$ONLY")
elif [ "$QUICK" = true ]; then
    TESTS=("${QUICK_TESTS[@]}")
else
    TESTS=("${ALL_TESTS[@]}")
fi

# ── 工具函数 ──
log() { echo "[$(date '+%H:%M:%S')] $*"; }

run_test() {
    local name="$1"
    local script="e2e/test-${name}.js"

    if [ ! -f "$script" ]; then
        log "⏭ SKIP $name — 脚本不存在: $script"
        SKIPPED=$((SKIPPED + 1))
        RESULTS+=("SKIP $name")
        return
    fi

    log "▶ 开始测试: $name"

    # 关闭旧 session，重新打开（每个测试独立）
    $CLI -s=$SESSION close 2>/dev/null || true

    # 打开浏览器
    $CLI -s=$SESSION open "$BASE_URL" --config=.playwright/cli.config.json > /dev/null 2>&1

    # 运行测试（playwright-cli 即使出错也返回 exit 0，需检查输出）
    local start_time=$(date +%s)
    local output
    output=$($CLI -s=$SESSION run-code --filename="$script" 2>&1)
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    if echo "$output" | grep -q "^### Error"; then
        log "✗ FAIL $name (${duration}s)"
        echo "$output" | grep -A 5 "^### Error" | head -8 | while read -r line; do log "    $line"; done
        $CLI -s=$SESSION screenshot --filename="$SCREENSHOT_DIR/FAIL-${name}.png" 2>/dev/null || true
        FAILED=$((FAILED + 1))
        RESULTS+=("FAIL $name (${duration}s)")
    else
        log "✓ PASS $name (${duration}s)"
        PASSED=$((PASSED + 1))
        RESULTS+=("PASS $name (${duration}s)")
    fi
}

# ── 前置检查 ──
log "========================================="
log "GovDoc E2E 测试"
log "前端: $BASE_URL"
log "后端: $BACKEND_URL"
log "测试: ${TESTS[*]}"
log "========================================="

# 检查前端可达
if ! curl -sf -o /dev/null --connect-timeout 5 "$BASE_URL/"; then
    log "✗ 前端不可达: $BASE_URL"
    exit 1
fi
log "✓ 前端可达"

# 检查后端可达
if ! curl -sf -o /dev/null --connect-timeout 5 "$BACKEND_URL/healthz"; then
    log "✗ 后端不可达: $BACKEND_URL"
    exit 1
fi
log "✓ 后端可达"

# ── 执行测试 ──
for t in "${TESTS[@]}"; do
    run_test "$t"
done

# ── 清理 ──
$CLI -s=$SESSION close 2>/dev/null || true

# ── 报告 ──
echo ""
log "========================================="
log "测试结果: $PASSED passed, $FAILED failed, $SKIPPED skipped"
for r in "${RESULTS[@]}"; do
    log "  $r"
done
log "========================================="

[ "$FAILED" -eq 0 ]
