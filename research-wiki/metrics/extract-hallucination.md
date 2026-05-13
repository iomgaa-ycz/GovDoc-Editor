---
type: metric
node_id: metric:extract-hallucination
title: "提取幻觉检测"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 提取幻觉检测 (extract-hallucination)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 审核点 JSON + 法规原文，检测无中生有的条款引用
- **Rubric**: `scripts/rubrics/extract_hallucination.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-extract-results]]
