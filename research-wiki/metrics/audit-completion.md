---
type: metric
node_id: metric:audit-completion
title: "审核点完成率"
date: 2026-05-13
tags: ["harness", "hard-metric", "L1"]
---

# 审核点完成率 (audit-completion)

- **类型**: 硬性指标
- **层**: L1（管道层）
- **计算**: `COUNT(status='completed') / COUNT(*)` from `audit_results`
- **阈值**: >= 90%
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-audit-results]]
