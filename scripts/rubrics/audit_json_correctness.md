# 输出 Schema 合规 (audit-json-correctness)

## 评判标准
检查 output.json 是否严格符合 WorkpaperAuditOutput schema：
1. 根节点有 `findings` 数组和 `summary` 字符串
2. 每个 finding 有 `checkpoint`（GovCheckpoint）和 `verdict`（GovFindingVerdict）
3. verdict 的 `verdict` 字段值为枚举之一：合规|不合规|存疑
4. 有 evidence_required 标记时，必须有 evidence_quotes 或 evidence_refs

## 评分规则
- 1.0：完全符合 schema
- 0.5：结构基本正确但有字段缺失
- 0.0：无法解析

## 判定阈值
score >= 0.9 → passed
