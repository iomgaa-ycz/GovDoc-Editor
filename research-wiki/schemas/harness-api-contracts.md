---
type: schema
node_id: schema:harness-api-contracts
title: "表结构: api_contracts"
date: 2026-05-13
tags: ["harness"]
---

# api_contracts

Layer 2 API 契约检查表。每个端点的 schema 契约验证记录一行。

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | 关联 pipeline_runs.run_id |
| endpoint | TEXT | 端点标识（method + path） |
| check_name | TEXT | 检查项名称 |
| passed | INTEGER | 是否通过（0/1） |
| detail | TEXT | 详细说明（失败原因等） |
