---
type: schema
node_id: schema:harness-audit-results
title: "表结构: audit_results"
date: 2026-05-13
tags: ["harness"]
---

# audit_results

Layer 1 审核结果表。管道 B 每个审核点运行（AuditPointRun）记录一行。

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | 关联 pipeline_runs.run_id |
| point_run_id | TEXT | AuditPointRun ID |
| checkpoint_id | TEXT | 审核点 ID |
| verdict | TEXT | 判定结果（pass / fail / uncertain） |
| has_evidence | INTEGER | 是否包含证据（0/1） |
| evidence_count | INTEGER | 证据条数 |
| has_case_refs | INTEGER | 是否包含案例引用（0/1） |
| duration_s | REAL | 单审核点耗时（秒） |
| status | TEXT | completed / failed |
