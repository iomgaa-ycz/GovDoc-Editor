---
type: metric
node_id: metric:audit-verdict-reasoning
title: "判定推理自洽性"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 判定推理自洽性 (audit-verdict-reasoning)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: verdict + evidence + reasoning 三者逻辑一致性
- **Rubric**: `scripts/rubrics/audit_verdict_reasoning.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-audit-results]]
