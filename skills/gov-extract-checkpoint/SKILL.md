---
name: gov-extract-checkpoint
description: |
  Use when extracting government procurement audit checkpoints from legal or
  policy guideline documents.
---

# 政府采购审核点抽取

## 适用场景
- 从法规、制度、处罚标准中抽取结构化审核点
- 为后续招标文书审查建立规则库

## 抽取策略
1. 先按违法违规大类切分。
2. 每个“具体情形”对应一个审核点。
3. 必须附法律依据原文片段。

## 输出约束
- 输出必须满足 `GovCheckpoint`
- `legal_basis.quote` 必须是原文片段
- `retrieval_hint` 使用关键词组合，不写完整句子

