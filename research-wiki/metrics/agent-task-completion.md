---
type: metric
node_id: metric:agent-task-completion
title: "任务完成度"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 任务完成度 (agent-task-completion)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 最终输出 vs 任务目标要求的完成程度
- **Rubric**: `scripts/rubrics/agent_task_completion.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-quality-scores]]
