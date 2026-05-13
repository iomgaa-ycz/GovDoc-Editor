---
type: metric
node_id: metric:checkpoint-import-fidelity
title: "导入保真度"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L2"]
---

# 导入保真度 (checkpoint-import-fidelity)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L2（API 层）
- **评判依据**: 导入后 DB 记录 vs 原始 XLS 内容的字段保真度
- **Rubric**: `scripts/rubrics/checkpoint_import_fidelity.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-api-contracts]]
