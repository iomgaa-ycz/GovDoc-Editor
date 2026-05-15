---
type: schema
node_id: schema:harness-agent-trajectories
title: "表结构: agent_trajectories"
date: 2026-05-15
tags: ["harness"]
---

# agent_trajectories

PES agent 运行轨迹表。每次 PES 执行记录一行，存储完整的 plan、workspace 文件列表和 phase 详情。

| 列 | 类型 | 说明 |
|----|------|------|
| run_id | TEXT | 关联 _runs.run_id |
| pipeline | TEXT | "A" 或 "B" |
| source_run_id | TEXT | ExtractRun.id 或 AuditPointRun.id |
| plan_json | TEXT | PES plan 阶段产出的完整 JSON |
| workspace_files_json | TEXT | workspace 中所有文件路径的 JSON 数组 |
| phase_details_json | TEXT | 各 phase 的详细状态 JSON 数组 |
