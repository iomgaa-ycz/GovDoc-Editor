---
type: schema
node_id: schema:harness-pipeline-runs
title: "表结构: pipeline_runs"
date: 2026-05-13
tags: ["harness"]
---

# pipeline_runs

Layer 1 管道执行汇总表。每次 run_extract() / run_audit() 调用记录一行。

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | HarnessLog 运行 ID |
| timestamp | TEXT | 自动填充 |
| pipeline | TEXT | "A" 或 "B" |
| project_name | TEXT | 测试项目名 |
| input_file | TEXT | 输入文件路径 |
| status | TEXT | completed / failed |
| duration_s | REAL | 执行耗时（秒） |
| total_tokens | INTEGER | 总 token 用量 |
| error | TEXT | 失败时的错误信息 |
