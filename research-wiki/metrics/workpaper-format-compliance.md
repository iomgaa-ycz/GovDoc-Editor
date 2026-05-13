---
type: metric
node_id: metric:workpaper-format-compliance
title: "格式规范性"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 格式规范性 (workpaper-format-compliance)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 工作底稿格式 vs 模板规范要求
- **Rubric**: `scripts/rubrics/workpaper_format_compliance.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-quality-scores]]
