---
type: metric
node_id: metric:extract-category-accuracy
title: "分类准确性"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 分类准确性 (extract-category-accuracy)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 审核点分类 vs golden set 分类标签
- **Rubric**: `scripts/rubrics/extract_category_accuracy.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-extract-results]]
