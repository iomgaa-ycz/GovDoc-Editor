# GovDoc_AuditorV3 技术债整理 Implementation Plan · Umbrella Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement sub-plans task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 协调 5 份子项目 plan 的依赖顺序、分支拓扑、回滚演练与最终合回 master 的验收门。

**Architecture:** Umbrella 分支 `feat/tech-debt-cleanup` 作为集成点，5 个子分支各开一份独立 PR 合入 umbrella；最后 umbrella 以 merge commit 合回 master。

**Tech Stack:**
- 后端 conda env: `govdoc-auditor-v3`
- 前端: Vite + React 18 + TS + vitest (P1c 引入) + MSW (P1c 引入)
- CI 命令: `conda run -n govdoc-auditor-v3 ...` + `npm test`（P1c 后）

**Spec 引用:** `docs/superpowers/specs/2026-04-19-govdoc-tech-debt-cleanup-design.md`

---

## 子 Plan 清单

| 波次 | 子项目 | Plan 文件 | 预估任务数 | 依赖 |
|---|---|---|---|---|
| 1 | P0 run_audit 拆分 | `2026-04-19-p0-run-audit-split.md` | ~12 | 仅依赖 umbrella 分支就位 |
| 1 | P1b output_utils.py 混合重构 | `2026-04-19-p1b-output-utils-json5.md` | ~10 | 同上 |
| 1 | P1c v3.ts 契约测试 + 前端测试基建 | `2026-04-19-p1c-v3-contract-tests.md` | ~9 | 同上 |
| 2 | P1a AIReviewPage 拆分 | `2026-04-19-p1a-aireview-split.md` | ~11 | P1c 已合入 umbrella |
| 3 | P2 孤立节点审查 | `2026-04-19-p2-isolated-nodes-audit.md` | ~6 | P0/P1a/P1b/P1c 已合入 umbrella |

---

## Prelude · 建立 umbrella 分支

按 spec §2.1 分支拓扑：

- [ ] **Step 1: 确认工作区干净**

Run: `git status`
Expected: master 分支，无 uncommitted changes（graphify-out/ 的变动属 skill 产出，可不在此处理）

- [ ] **Step 2: 拉最新 master**

Run:
```bash
git checkout master
git pull --ff-only origin master 2>/dev/null || true
```

- [ ] **Step 3: 建立 umbrella 集成分支**

Run:
```bash
git checkout -b feat/tech-debt-cleanup
git push -u origin feat/tech-debt-cleanup 2>/dev/null || true
```

Expected: 新分支 `feat/tech-debt-cleanup` 从 master 切出

- [ ] **Step 4: 验证分支状态**

Run: `git branch --show-current`
Expected: `feat/tech-debt-cleanup`

---

## 实施顺序

```
Prelude        → 建立 umbrella 分支
Wave 1 (并行)  → P0 + P1b + P1c   （三个子分支从 umbrella 切出）
Wave 2         → P1a              （P1c merge 入 umbrella 后才启动）
Wave 3         → P2               （P0/P1a/P1b/P1c 全部 merge 入 umbrella 后启动）
Final          → umbrella → master (merge commit，保留子 PR 历史)
```

执行者必须严格按此顺序。每个 Wave 内部，建议用 `subagent-driven-development` 同时分派多个 subagent 并行跑子 plan。

---

## 子 PR Merge 守则

每个子 PR 合入 umbrella 前必须满足：

- [ ] Sub-plan 内全部 task 已完成并 check 掉
- [ ] Sub-plan 定义的 DoD 全部满足（见各子 plan 末尾）
- [ ] `conda run -n govdoc-auditor-v3 ruff check .` 零新增 warning
- [ ] `conda run -n govdoc-auditor-v3 ruff format --check .` 无格式差异
- [ ] 后端测试：`conda run -n govdoc-auditor-v3 python -m pytest tests/` 全绿
- [ ] 前端测试（若 P1c 已合入）：`cd frontend && npm test` 全绿
- [ ] 前端类型检查（若有 .ts/.tsx 改动）：`cd frontend && tsc -b` 零新增 error
- [ ] 子 PR 的 commit history 清晰：`test:` 先、`refactor:` 后（适用于 P0/P1a/P1b）

---

## 回滚演练 · I3 不变式验证

**目的：** 验证任一子 PR revert 后，umbrella 分支仍能通过全部现有测试。

在每个子 PR merge 进 umbrella 后，立即做一次 revert 演练：

- [ ] **演练 Step 1: 记录当前 HEAD**

Run:
```bash
git log -1 --format='%H %s' > /tmp/umbrella_head.txt
cat /tmp/umbrella_head.txt
```

- [ ] **演练 Step 2: Revert 该子 PR 的 merge commit**

Run:
```bash
git revert --no-edit HEAD
```

- [ ] **演练 Step 3: 跑全量测试**

Run:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/ -v
cd frontend && npm test 2>/dev/null || echo "前端测试跳过（P1c 未合入）"
cd ..
```

Expected: 全绿

- [ ] **演练 Step 4: 恢复 revert**

Run: `git revert --no-edit HEAD`

Expected: 重新应用被 revert 的内容

- [ ] **演练 Step 5: 确认 HEAD 回到演练前**

Run: `git log -2 --format='%H %s'`
Expected: 最新两条都是 revert commits（互相抵消），工作树内容与演练前一致

- [ ] **演练 Step 6: （可选）清理演练产生的 2 个 revert commits**

如果介意 commit history 有两条互相抵消的 revert commit，可以：
```bash
git reset --hard <演练前 HEAD hash>
```

⚠️ 若已 push，此步跳过（不做 force push），保留演练 commits。

---

## Final · Umbrella 合回 master

当 5 个子 PR 全部 merge 进 umbrella 且回滚演练都通过后：

- [ ] **Step 1: umbrella 分支 rebase 最新 master**

Run:
```bash
git checkout feat/tech-debt-cleanup
git fetch origin master
git rebase origin/master
```

若有冲突，**先解决冲突，不要 drop commits**。

- [ ] **Step 2: 跑全量验收**

Run:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/ -v
conda run -n govdoc-auditor-v3 ruff check .
conda run -n govdoc-auditor-v3 ruff format --check .
cd frontend && npm test && tsc -b
cd ..
```

Expected: 全绿

- [ ] **Step 3: 手工端到端 smoke**

Run（两个终端）:
```bash
# 终端 1: 后端
conda run -n govdoc-auditor-v3 uvicorn govdoc.api.main:app --host 0.0.0.0 --port 8000

# 终端 2: 前端
cd frontend && npm run dev
```

操作：
1. 浏览器开 http://localhost:5173
2. 创建项目 → 上传招标文书 → 勾选 3 个审核点 → 启动审计
3. 观察无 console.error、审计完成、工作底稿可下载

- [ ] **Step 4: 合回 master（merge commit，保留子 PR 历史）**

Run:
```bash
git checkout master
git merge --no-ff feat/tech-debt-cleanup -m "$(cat <<'EOF'
chore: 合入 5 项技术债整理（P0 run_audit 拆分 + P1a AIReviewPage 拆分 + P1b output_utils 混合重构 + P1c 前端测试基建 + P2 孤立节点审查）

详见 docs/superpowers/specs/2026-04-19-govdoc-tech-debt-cleanup-design.md
EOF
)"
```

- [ ] **Step 5: （可选）推到远端**

⚠️ **不得直接 push 到 master**。按团队流程开 PR 或让用户审核后推。

```bash
# 由用户决定
# git push origin master
```

- [ ] **Step 6: 归档 umbrella 分支**

```bash
git branch -d feat/tech-debt-cleanup  # 本地删除
# git push origin :feat/tech-debt-cleanup  # 远端删除，由用户决定
```

---

## 完成标志

本 umbrella 实施完成的最终验收：

- [ ] 5 个子 plan 全部 task 完成
- [ ] 5 次回滚演练全部通过
- [ ] Umbrella → master 的 merge commit 已打
- [ ] 手工 smoke 通过
- [ ] 本 index plan 所有 checkbox 打勾
- [ ] 用图谱重跑 `graphify --update`，孤立节点数应下降，`run_audit` 不应再出现在 god nodes 列表

---

## 附录 · 失败恢复矩阵

| 场景 | 处理 |
|---|---|
| 某子 plan 执行到一半卡死 | 该子分支 `git stash` 保留进度；回到 umbrella，先跑完其他 Wave 1 子项目；回头续做 |
| 某子 PR merge 到 umbrella 后回滚演练失败 | 说明 I3 违反。立即 `git revert HEAD`，在子分支上补测试、修依赖，重新开 PR |
| Umbrella rebase master 冲突太大 | 冲突分析：若来自 spec 外 scope，阻塞实施，升级到 spec 讨论；若是 spec 内 scope，在 umbrella 上解决冲突并跑全量验收 |
| 合回 master 后发现回归 | `git revert <umbrella-merge-commit>` 整体回滚，然后在 umbrella 分支上修复后重新合入 |
