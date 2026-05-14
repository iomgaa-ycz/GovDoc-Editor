#!/usr/bin/env bash
# WorktreeCreate hook — 自动适配 worktree 环境
# 1. symlink 未跟踪大文件/目录到主仓库
# 2. 重新注册 editable install 到 worktree 路径
set -euo pipefail

MAIN_REPO="$(git worktree list | head -1 | awk '{print $1}')"
WORKTREE_DIR="$(pwd)"

if [ "$WORKTREE_DIR" = "$MAIN_REPO" ]; then
    exit 0
fi

for item in real_data data .env; do
    src="$MAIN_REPO/$item"
    dst="$WORKTREE_DIR/$item"
    if [ -e "$src" ] && [ ! -e "$dst" ]; then
        ln -s "$src" "$dst"
        echo "[worktree-setup] symlink: $item"
    fi
done

if [ -d "$WORKTREE_DIR/vendor/scrivai-src" ]; then
    conda run -n govdoc-auditor-v3 pip install -e "$WORKTREE_DIR/vendor/scrivai-src" --quiet 2>/dev/null || true
fi
conda run -n govdoc-auditor-v3 pip install -e "$WORKTREE_DIR" --quiet 2>/dev/null || true
echo "[worktree-setup] editable install 已重指向 $WORKTREE_DIR"
