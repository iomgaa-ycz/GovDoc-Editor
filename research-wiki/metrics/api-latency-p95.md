---
type: metric
node_id: metric:api-latency-p95
title: "API P95 延迟"
date: 2026-05-13
tags: ["harness", "hard-metric", "L2"]
---

# API P95 延迟 (api-latency-p95)

- **类型**: 硬性指标
- **层**: L2（API 层）
- **计算**: 同步端点 P95 延迟 `PERCENTILE(duration_ms, 0.95)` from `api_calls`
- **阈值**: <= 2000ms
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-api-calls]]
