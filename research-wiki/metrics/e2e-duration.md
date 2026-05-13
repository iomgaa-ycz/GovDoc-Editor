---
type: metric
node_id: metric:e2e-duration
title: "端到端耗时"
date: 2026-05-13
tags: ["harness", "hard-metric", "L1"]
---

# 端到端耗时 (e2e-duration)

- **类型**: 硬性指标
- **层**: L1（管道层）
- **计算**: `SUM(duration_s)` from `pipeline_runs` WHERE project_name 相同，单项目全流程耗时
- **阈值**: <= 600s
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-pipeline-runs]]
