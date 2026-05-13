---
type: metric
node_id: metric:pipeline-a-success
title: "管道 A 成功率"
date: 2026-05-13
tags: ["harness", "hard-metric", "L1"]
---

# 管道 A 成功率 (pipeline-a-success)

- **类型**: 硬性指标
- **层**: L1（管道层）
- **计算**: `COUNT(status='completed') / COUNT(*)` from `pipeline_runs WHERE pipeline='A'`
- **阈值**: >= 80%
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-pipeline-runs]]
