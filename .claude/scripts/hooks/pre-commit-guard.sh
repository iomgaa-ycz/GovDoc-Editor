#!/usr/bin/env bash
# ============================================================
# pre-commit-guard.sh
# Claude Code PreToolUse hook — 拦截 git commit，执行全量检查
#
# 触发时机：Claude 尝试执行 git commit 之前
# 作用：阻塞提交直到所有质量门禁通过
# 退出码：0 = 放行，2 = 阻塞（Claude 必须先修复问题）
#
# 配置方法：在 .claude/settings.local.json 中注册：
# "hooks": {
#   "PreToolUse": [
#     { "matcher": "Bash", "command": "bash scripts/hooks/pre-commit-guard.sh" }
#   ]
# }
# ============================================================
set -euo pipefail

PROJ_ENV="/home/iomgaa/miniconda3/envs/govdoc-auditor-v3/bin"
RUFF="$PROJ_ENV/ruff"
RADON="$PROJ_ENV/radon"
PYTEST="$PROJ_ENV/pytest"

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# 只拦截 git commit 命令
if ! echo "$COMMAND" | grep -qE '^\s*git\s+commit'; then
    exit 0
fi

ERRORS=""
WARNINGS=""

# <填写: 核心代码目录，如 core/>
CODE_DIR="govdoc"

# ── 1. 项目结构检查（按需取消注释） ──
# 检查根目录是否有不该存在的 .py
# for pyfile in *.py; do
#     [[ "$pyfile" == "*.py" ]] && break
#     if [[ "$pyfile" != "main.py" && "$pyfile" != "conftest.py" ]]; then
#         ERRORS+="[结构] 根目录不该有: $pyfile（应移至 $CODE_DIR/）\n"
#     fi
# done

# ── 2. 全量代码质量检查 ──
if [[ -d "$CODE_DIR" ]] && [[ -x "$RUFF" ]]; then
    if ! "$RUFF" check "$CODE_DIR" > /dev/null 2>&1; then
        RUFF_OUTPUT=$("$RUFF" check "$CODE_DIR" 2>&1 || true)
        ERROR_COUNT=$(echo "$RUFF_OUTPUT" | wc -l)
        ERRORS+="[ruff] $CODE_DIR/ 中有 ${ERROR_COUNT} 个问题。运行 ruff check $CODE_DIR/ 查看详情。\n"
    fi
fi

if [[ -d "$CODE_DIR" ]] && [[ -x "$RADON" ]]; then
    RADON_OUTPUT=$("$RADON" cc "$CODE_DIR" -n C -s 2>&1 || true)
    if echo "$RADON_OUTPUT" | grep -qE '^\s+[FMC]\s'; then
        ERRORS+="[radon] 存在圈复杂度 ≥ C 的函数：\n$RADON_OUTPUT\n"
    fi
fi

# ── 3. 文件行数检查 ──
if [[ -d "$CODE_DIR" ]]; then
    while IFS= read -r pyfile; do
        lines=$(wc -l < "$pyfile")
        if [[ "$lines" -gt 200 ]]; then
            WARNINGS+="[行数] $pyfile 有 ${lines} 行，超过 200 行建议上限。\n"
        fi
    done < <(find "$CODE_DIR" -name "*.py" 2>/dev/null || true)
fi

# ── 4. 测试检查 ──
if [[ -x "$PYTEST" ]] && [[ -d "tests" ]]; then
    TEST_OUTPUT=$("$PYTEST" tests/unit/ tests/contract/ --tb=line -q 2>&1 || true)
    if echo "$TEST_OUTPUT" | grep -qE 'failed|error'; then
        FAILED=$(echo "$TEST_OUTPUT" | tail -1)
        ERRORS+="[测试] 有测试未通过：$FAILED\n"
    fi
fi

# ── 判定结果 ──
if [[ -n "$WARNINGS" ]]; then
    echo -e "⚠️  Warnings（不阻塞）：\n" >&2
    echo -e "$WARNINGS" >&2
fi

if [[ -n "$ERRORS" ]]; then
    echo -e "❌ 提交被阻塞 — 请先修复以下问题：\n" >&2
    echo -e "$ERRORS" >&2
    echo -e "修复完成后重新执行 git commit。" >&2
    exit 2
fi

echo "✅ 所有检查通过，允许提交。"
exit 0
