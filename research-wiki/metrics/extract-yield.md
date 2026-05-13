---
type: metric
node_id: metric:extract-yield
title: "审核点产出率"
date: 2026-05-13
tags: ["harness", "hard-metric", "L1"]
---

# 审核点产出率 (extract-yield)

- **类型**: 硬性指标
- **层**: L1（管道层）
- **计算**: `COUNT(*)` from `extract_results` per run，每法规产出的审核点数
- **阈值**: >= 5
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-extract-results]]
