---
type: metric
node_id: metric:audit-relevancy
title: "发现相关性"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 发现相关性 (audit-relevancy)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 审核发现 vs 审核点要求，验证发现与审核点的相关性
- **Rubric**: `scripts/rubrics/audit_relevancy.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-audit-results]]
