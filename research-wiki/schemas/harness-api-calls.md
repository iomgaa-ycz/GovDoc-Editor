---
type: schema
node_id: schema:harness-api-calls
title: "表结构: api_calls"
date: 2026-05-13
tags: ["harness"]
---

# api_calls

Layer 2 API 调用记录表。每次 HTTP 请求记录一行。

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | 关联 pipeline_runs.run_id |
| method | TEXT | HTTP 方法（GET / POST / PUT / DELETE） |
| path | TEXT | 请求路径 |
| status_code | INTEGER | HTTP 响应状态码 |
| duration_ms | REAL | 请求耗时（毫秒） |
| request_size | INTEGER | 请求体大小（字节） |
| response_size | INTEGER | 响应体大小（字节） |
| error | TEXT | 错误信息（若有） |
