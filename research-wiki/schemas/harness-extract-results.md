---
type: schema
node_id: schema:harness-extract-results
title: "表结构: extract_results"
date: 2026-05-13
tags: ["harness"]
---

# extract_results

Layer 1 审核点提取结果表。管道 A 每个产出的审核点记录一行。

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | 关联 pipeline_runs.run_id |
| checkpoint_id | TEXT | 审核点 ID |
| title | TEXT | 审核点标题 |
| category | TEXT | 审核点分类 |
| has_legal_basis | INTEGER | 是否包含法条依据（0/1） |
| legal_basis_count | INTEGER | 法条引用数量 |
