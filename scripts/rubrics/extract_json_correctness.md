# 输出 Schema 合规 (extract-json-correctness)

## 评判标准
检查 output.json 是否严格符合 CheckpointListOutput schema：
1. 根节点有 `checkpoints` 数组
2. 每个元素有 `id`, `category`, `title`, `description`, `severity` 必填字段
3. `category` 值为枚举之一：意向性招标|围标串标|不合理条件限制或排斥供应商|其他违法违规
4. `severity` 值为枚举之一：critical|major|minor
5. `legal_basis` 若存在，每项有 `law_name`, `article`, `quote`

## 评分规则
- 1.0：完全符合 schema，所有字段类型和枚举值正确
- 0.5：结构基本正确但有字段缺失或类型错误
- 0.0：无法解析或结构完全不匹配

## 判定阈值
score >= 0.9 → passed
