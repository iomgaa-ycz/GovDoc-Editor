#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# GovDoc E2E 测试运行器（基于 @playwright/cli）
#
# 用法：
#   bash frontend/e2e/run-tests.sh                    # 运行全部测试
#   bash frontend/e2e/run-tests.sh --only files-F1    # 只运行指定测试
#   bash frontend/e2e/run-tests.sh --page files       # 运行某页面全部测试
# ─────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."

export NO_PROXY="175.178.131.134,100.70.102.30,100.82.33.121,110.42.53.85,localhost,127.0.0.1,${NO_PROXY:-}"
export no_proxy="$NO_PROXY"

BASE_URL="${E2E_BASE_URL:-http://175.178.131.134:8080}"
BACKEND_URL="${E2E_BACKEND_URL:-http://localhost:8000}"
SCREENSHOT_DIR="e2e/screenshots"
CLI="npx playwright-cli"
SESSION="govdoc-e2e"

PASSED=0
FAILED=0
SKIPPED=0
RESULTS=()

mkdir -p "$SCREENSHOT_DIR"

# ── 参数解析 ──
ONLY=""
PAGE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --only) ONLY="$2"; shift 2 ;;
        --page) PAGE="$2"; shift 2 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

# ── 测试清单（按页面分组） ──
FILES_TESTS=("files-F1-skeleton" "files-F2-upload" "files-F3-search-filter" "files-F4-tags" "files-F5-delete" "files-F6-reconvert" "files-F7-empty-state")
COMPARE_TESTS=("compare-C1-skeleton" "compare-C2-file-picker" "compare-C3-selection-manage" "compare-C4-submit-progress" "compare-C5-history" "compare-C6-result-view" "compare-C7-result-interact" "compare-C8-empty-error")
AUDIT_TESTS=("audit-AL1-skeleton" "audit-AL2-import" "audit-AL3-search-filter" "audit-AL4-library-crud" "audit-AL5-checkpoint-edit-delete" "audit-AL6-library-membership" "audit-AL7-empty-state" "audit-AL8-ai-extract" "audit-AL9-checkpoint-archive" "audit-AL10-upload-dragdrop")
REVIEW_TESTS=("review-R1-skeleton" "review-R2-drawer" "review-R3-create-run" "review-R4-progress" "review-R5-workpaper" "review-R6-cancel-retry" "review-R7-finalize-export" "review-R8-form-validation")
CROSS_TESTS=("cross-X1-file-to-review" "cross-X2-delete-cp-to-review" "cross-X3-edit-cp-to-review" "cross-X4-dashboard-sync")
DASHBOARD_TESTS=("dashboard-D1-skeleton" "dashboard-D2-stats" "dashboard-D3-navigation" "dashboard-D4-sidebar-nav")

ALL_TESTS=("${FILES_TESTS[@]}" "${COMPARE_TESTS[@]}" "${AUDIT_TESTS[@]}" "${REVIEW_TESTS[@]}" "${CROSS_TESTS[@]}" "${DASHBOARD_TESTS[@]}")

if [ -n "$ONLY" ]; then
    TESTS=("$ONLY")
elif [ -n "$PAGE" ]; then
    case "$PAGE" in
        files) TESTS=("${FILES_TESTS[@]}") ;;
        compare) TESTS=("${COMPARE_TESTS[@]}") ;;
        audit) TESTS=("${AUDIT_TESTS[@]}") ;;
        dashboard) TESTS=("${DASHBOARD_TESTS[@]}") ;;
        *) echo "未知页面: $PAGE（可选: files, compare, audit, dashboard）"; exit 1 ;;
    esac
else
    TESTS=("${ALL_TESTS[@]}")
fi

# ── 工具函数 ──
log() { echo "[$(date '+%H:%M:%S')] $*"; }

run_test() {
    local name="$1"
    local script="e2e/${name}.js"

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

    # 运行测试
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

# ── 生成 e2e fixture ──
if [ ! -d "e2e/.test-data" ]; then
    log "▶ 生成 e2e 测试 fixture..."
    source activate govdoc-auditor-v3 && python3 e2e/generate-test-data.py
    log "✓ fixture 生成完成"
fi

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
