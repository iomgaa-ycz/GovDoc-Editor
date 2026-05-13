---
type: metric
node_id: metric:phase-no-crash
title: "Phase 零崩溃"
date: 2026-05-13
tags: ["harness", "hard-metric", "L1"]
---

# Phase 零崩溃 (phase-no-crash)

- **类型**: 硬性指标
- **层**: L1（管道层）
- **计算**: `COUNT(status='failed')` from `phase_metrics`
- **阈值**: = 0
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-phase-metrics]]
