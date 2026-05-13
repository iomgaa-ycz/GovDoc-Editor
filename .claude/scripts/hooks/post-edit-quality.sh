#!/usr/bin/env bash
# ============================================================
# post-edit-quality.sh
# Claude Code PostToolUse hook — 每次编辑 .py 文件后自动检查
#
# 触发时机：Claude 每次执行 Write/Edit 后
# 作用：对被修改的文件执行复杂度和风格检查
# 退出码：0 = 通过，非0 = 报告问题（非阻塞，Claude 会看到反馈）
#
# 配置方法：在 .claude/settings.local.json 中注册：
# "hooks": {
#   "PostToolUse": [
#     { "matcher": "Write|Edit", "command": "bash scripts/hooks/post-edit-quality.sh" }
#   ]
# }
# ============================================================
set -euo pipefail

PROJ_ENV="/home/iomgaa/miniconda3/envs/govdoc-auditor-v3/bin"
RUFF="$PROJ_ENV/ruff"
RADON="$PROJ_ENV/radon"

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""')

# 只检查 .py 文件
if [[ ! "$FILE_PATH" == *.py ]]; then
    exit 0
fi

# 只检查存在的文件
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

ERRORS=""
WARNINGS=""

# ── 1. Ruff 格式 + lint 检查 ──
if [[ -x "$RUFF" ]]; then
    RUFF_OUTPUT=$("$RUFF" check "$FILE_PATH" 2>&1 || true)
    if [[ -n "$RUFF_OUTPUT" ]]; then
        ERRORS+="[ruff] 风格/lint 问题：\n$RUFF_OUTPUT\n\n"
    fi
fi

# ── 2. Radon 圈复杂度（只报告 C 级及以下） ──
if [[ -x "$RADON" ]]; then
    RADON_OUTPUT=$("$RADON" cc "$FILE_PATH" -n C -s 2>&1 || true)
    if echo "$RADON_OUTPUT" | grep -qE '^\s+[FMC]\s'; then
        ERRORS+="[radon] 圈复杂度过高（≥C）：\n$RADON_OUTPUT\n\n"
    fi
fi

# ── 3. 文件行数检查（warning，不阻塞）──
LINE_COUNT=$(wc -l < "$FILE_PATH")
if [[ "$LINE_COUNT" -gt 200 ]]; then
    WARNINGS+="[行数] $FILE_PATH 有 ${LINE_COUNT} 行，超过 200 行建议上限。\n\n"
fi

# ── 4. 禁止裸 except ──
if grep -nE '^\s*except\s*:\s*$|^\s*except\s+Exception\s*:\s*pass' "$FILE_PATH" 2>/dev/null; then
    ERRORS+="[安全] 检测到裸 except 或 except Exception: pass，请捕获具体异常类型。\n\n"
fi

# ── 5. 禁止硬编码敏感信息 ──
if grep -nEi "(api_key|secret|password|token)\s*=\s*[\"'][^\"']+[\"']" "$FILE_PATH" 2>/dev/null; then
    ERRORS+="[安全] 疑似硬编码敏感信息，请使用环境变量或 .env 文件。\n\n"
fi

# ── 输出结果 ──
if [[ -n "$WARNINGS" ]]; then
    echo -e "⚠️  Warnings（$FILE_PATH，不阻塞）：\n" >&2
    echo -e "$WARNINGS" >&2
fi

if [[ -n "$ERRORS" ]]; then
    echo -e "❌ 代码质量检查发现问题（$FILE_PATH）：\n" >&2
    echo -e "$ERRORS" >&2
    exit 1
fi

exit 0
