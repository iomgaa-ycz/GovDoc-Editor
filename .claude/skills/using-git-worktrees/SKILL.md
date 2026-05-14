---
name: using-git-worktrees
description: "Worktree 使用指南。WorktreeCreate hook 自动执行 symlink + pip install -e 适配。"
---

# Git Worktree 使用指南

本项目支持 git worktree，通过 `WorktreeCreate` hook 自动处理两个兼容性问题：

1. **editable install 重指向**：自动执行 `pip install -e .` + `pip install -e ./vendor/scrivai-src`
2. **未跟踪大文件 symlink**：自动链接 `real_data/`、`data/`、`.env` 到主仓库
