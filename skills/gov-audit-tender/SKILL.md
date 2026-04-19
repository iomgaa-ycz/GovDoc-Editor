---
name: gov-audit-tender
description: |
  Use when auditing a tender document against finalized government procurement
  checkpoints.
---

# 招标文书审核

## 任务目标
- 逐条审核 `checkpoints.json`
- 对每条审核点产出 `GovFinding`
- 结论必须能回溯到招标文书原文

## 执行原则
1. 先读审核点定义，再定位文书证据。
2. 优先给出证据，再下结论。
3. 发现证据不足时，结论应为“存疑”而不是猜测。

