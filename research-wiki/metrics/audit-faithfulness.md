---
type: metric
node_id: metric:audit-faithfulness
title: "证据引用忠实度"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 证据引用忠实度 (audit-faithfulness)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 审核发现 + 招标文书原文，验证证据引用准确性
- **Rubric**: `scripts/rubrics/audit_faithfulness.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-audit-results]]
