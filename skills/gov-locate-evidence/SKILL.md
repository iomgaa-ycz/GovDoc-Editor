---
name: gov-locate-evidence
description: |
  Use when locating evidence passages inside tender documents for a checkpoint.
---

# 证据定位

## 适用场景
- 根据审核点关键词在招标文书中搜索相关段落
- 为 `GovFinding.evidence_refs` 和 `evidence_quotes` 提供依据

## 方法
1. 先用 `govdoc-cli parse-tender` 识别文书结构。
2. 再用 `govdoc-cli locate-section` 缩小范围。
3. 必要时用 `qmd search` 做全文检索。

