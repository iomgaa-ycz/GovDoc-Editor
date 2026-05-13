---
type: metric
node_id: metric:audit-hallucination
title: "审核幻觉检测"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 审核幻觉检测 (audit-hallucination)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 审核发现 + 招标文书原文，检测无中生有的证据或结论
- **Rubric**: `scripts/rubrics/audit_hallucination.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-audit-results]]
