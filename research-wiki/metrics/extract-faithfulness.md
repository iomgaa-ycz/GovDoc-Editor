---
type: metric
node_id: metric:extract-faithfulness
title: "法条引用忠实度"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 法条引用忠实度 (extract-faithfulness)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 审核点 JSON + 法规原文
- **Rubric**: `scripts/rubrics/extract_faithfulness.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-extract-results]]
