---
type: metric
node_id: metric:workpaper-render
title: "底稿渲染成功"
date: 2026-05-13
tags: ["harness", "hard-metric", "L2"]
---

# 底稿渲染成功 (workpaper-render)

- **类型**: 硬性指标
- **层**: L2（API 层）
- **计算**: finalize -> docx 生成成功率
- **阈值**: = 100%
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-api-calls]]
