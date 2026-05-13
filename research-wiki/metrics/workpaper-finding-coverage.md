---
type: metric
node_id: metric:workpaper-finding-coverage
title: "发现覆盖率"
date: 2026-05-13
tags: ["harness", "semantic-metric", "L1"]
---

# 发现覆盖率 (workpaper-finding-coverage)

- **类型**: 语义指标（HarnessJudge 评判）
- **层**: L1（管道层）
- **评判依据**: 工作底稿中包含的发现 vs 管道 B 全部发现
- **Rubric**: `scripts/rubrics/workpaper_finding_coverage.md`
- **阈值**: score >= 0.7
- **基线**: 待首次运行后确定
- **关联 schema**: [[harness-quality-scores]]
