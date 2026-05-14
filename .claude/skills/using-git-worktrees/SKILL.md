---
name: using-git-worktrees
description: "⛔ 已废弃。本项目禁止使用 git worktree（pip editable install 不兼容）。所有开发直接在主分支进行。"
---

# ⛔ 已废弃

本项目**禁止使用 git worktree**。

原因：`pip install -e .` 的 editable finder 硬编码主仓库路径 `MAPPING = {'govdoc': '/path/to/main/govdoc'}`，worktree 中的代码修改不会被 Python 加载。

所有开发直接在 master 分支进行。
