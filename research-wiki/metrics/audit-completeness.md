---
type: metric
node_id: metric:audit-completeness
title: "审核覆盖完整性"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 审核覆盖完整性 (audit-completeness)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 审核发现覆盖的文书章节 vs 审核点要求覆盖的章节
- **Rubric**: `scripts/rubrics/audit_completeness.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-audit-results]]
