# 发现覆盖率 (workpaper-finding-coverage)

## 评判标准
检查工作底稿是否包含了所有已完成审核点的 finding：
1. 每个 status='completed' 的 AuditPointRun 是否都有对应的 finding 在底稿中
2. 底稿中的 finding 数量是否与完成的审核点数量一致
3. 是否有遗漏的审核结果

## 评分规则
- 1.0：全部完成的审核点都被包含
- 0.7-0.9：极少数遗漏
- 0.4-0.6：约半数被包含
- 0.0-0.3：大量遗漏

## 判定阈值
score >= 0.9 → passed
