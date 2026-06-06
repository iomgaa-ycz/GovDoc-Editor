---
type: design
node_id: design:audit-partial-failure-recovery
title: 审核部分失败恢复（残缺底稿+重试/跳过）
date: 2026-06-06
---

# 审核部分失败恢复（残缺底稿+重试/跳过）

**完整设计**：[2026-06-06-audit-partial-failure-recovery-design.md](./2026-06-06-audit-partial-failure-recovery-design.md)

## 选定方案
方案 A：在后端 `_assemble_workpaper_draft` 把"只要有完成点就出底稿"作为单一真相；新增 `excluded` 软剔除状态；新增 `retry-failed`/`exclude-failed` 两个 run 级批量端点（复用 `run_audit` 白名单 + 单点重试清 workspace + WorkpaperDraft 版本机制）；前端加"部分完成"提示条与两按钮；一次性脚本回填历史卡死任务。

## 关键决策
- **有失败也出残缺底稿**（不再卡死）；失败点可重试或跳过，两条路均可达 `draft_ready` 完整底稿。
- **软剔除（excluded）而非硬删**：可逆、留痕，优于事故中手动 `DELETE`。
- **重试/剔除总是生成新版底稿**，不检测律师编辑冲突（MVP 最简）。

## 否决的备选
- 方案 B（前端兜底调 finalize-partial）：业务逻辑外漏前端、有竞态、误用"定稿"语义。
- 方案 C（点级状态机 + 自动重试策略 + 作业队列）：过度工程，违反 MVP。

