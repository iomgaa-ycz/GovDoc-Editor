---
type: metric
node_id: metric:workpaper-summarization
title: "摘要质量"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 摘要质量 (workpaper-summarization)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 工作底稿摘要 vs 原始审核发现
- **Rubric**: `scripts/rubrics/workpaper_summarization.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-quality-scores]]
