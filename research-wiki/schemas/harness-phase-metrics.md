---
type: schema
node_id: schema:harness-phase-metrics
title: "表结构: phase_metrics"
date: 2026-05-13
tags: ["harness"]
---

# phase_metrics

Layer 1 阶段级指标表。PES 三阶段（Plan / Execute / Summarize）各记录一行。

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | 关联 pipeline_runs.run_id |
| pipeline | TEXT | "A" 或 "B" |
| phase | TEXT | plan / execute / summarize |
| duration_s | REAL | 阶段耗时（秒） |
| tokens_in | INTEGER | 输入 token 数 |
| tokens_out | INTEGER | 输出 token 数 |
| status | TEXT | completed / failed |
| attempt_no | INTEGER | 重试次数（1 = 首次） |
