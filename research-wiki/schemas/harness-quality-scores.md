---
type: schema
node_id: schema:harness-quality-scores
title: "表结构: quality_scores"
date: 2026-05-13
tags: ["harness"]
---

# quality_scores

Layer 1 质量评分表。HarnessJudge 对每个语义维度打分记录一行。

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | 关联 pipeline_runs.run_id |
| dimension | TEXT | 评判维度名称 |
| score | REAL | 评分（0.0 ~ 1.0） |
| passed | INTEGER | 是否通过阈值（0/1） |
| judge_reasoning | TEXT | Judge 的推理说明 |
