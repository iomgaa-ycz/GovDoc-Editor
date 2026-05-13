---
type: metric
node_id: metric:agent-step-efficiency
title: "步骤效率"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 步骤效率 (agent-step-efficiency)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: Execute 阶段步骤数 + 每步的有效产出
- **Rubric**: `scripts/rubrics/agent_step_efficiency.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-quality-scores]]
