---
type: metric
node_id: metric:extract-json-correctness
title: "提取输出 Schema 合规"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 提取输出 Schema 合规 (extract-json-correctness)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 提取输出 JSON 结构 vs GovCheckpoint schema
- **Rubric**: `scripts/rubrics/extract_json_correctness.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-extract-results]]
