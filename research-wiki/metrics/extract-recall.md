---
type: metric
node_id: metric:extract-recall
title: "审核点召回率"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 审核点召回率 (extract-recall)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 产出审核点 vs golden set 审核点
- **Rubric**: `scripts/rubrics/extract_recall.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-extract-results]]
