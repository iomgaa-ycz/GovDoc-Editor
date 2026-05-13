# 任务完成度 (agent-task-completion)

## 评判标准
检查 PES 三个阶段是否都产出了预期文件：
1. plan 阶段：plan.json（或 plan.md）存在且非空
2. execute 阶段：findings/ 目录下有至少 1 个 .json 文件
3. summarize 阶段：output.json 存在且可解析

## 评分规则
- 1.0：三个阶段全部产出预期文件
- 0.67：两个阶段产出
- 0.33：一个阶段产出
- 0.0：无任何产出

## 判定阈值
score >= 1.0 → passed
