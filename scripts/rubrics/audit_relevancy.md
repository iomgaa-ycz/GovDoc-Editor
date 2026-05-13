# 发现与审核点相关性 (audit-relevancy)

## 评判标准
逐个检查每个 GovFinding 是否紧扣其对应 GovCheckpoint：
1. finding 的分析内容是否针对 checkpoint 定义的审查维度
2. 是否存在"答非所问"（分析了不相关的内容）
3. evidence 是否与 checkpoint 的审查范围相关

## 评分规则
- 1.0：全部发现与其审核点高度相关
- 0.7-0.9：大部分相关，个别有轻微偏题
- 0.4-0.6：约半数相关
- 0.0-0.3：大量不相关内容

## 判定阈值
score >= 0.7 → passed
