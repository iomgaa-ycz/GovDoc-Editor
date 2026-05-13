---
type: metric
node_id: metric:agent-plan-adherence
title: "计划遵循度"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 计划遵循度 (agent-plan-adherence)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: Plan 阶段计划 vs Execute 阶段实际执行步骤
- **Rubric**: `scripts/rubrics/agent_plan_adherence.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-quality-scores]]
