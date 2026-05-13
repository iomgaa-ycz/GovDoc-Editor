---
type: metric
node_id: metric:agent-plan-quality
title: "计划质量"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 计划质量 (agent-plan-quality)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: PES Plan 阶段输出的计划文档
- **Rubric**: `scripts/rubrics/agent_plan_quality.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-quality-scores]]
