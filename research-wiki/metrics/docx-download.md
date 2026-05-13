---
type: metric
node_id: metric:docx-download
title: "DOCX 下载完整性"
date: 2026-05-13
tags: ["harness", "hard-metric", "L2"]
---

# DOCX 下载完整性 (docx-download)

- **类型**: 硬性指标
- **层**: L2（API 层）
- **计算**: 下载文件大小 > 0 且可正常打开
- **阈值**: pass
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-api-calls]]
