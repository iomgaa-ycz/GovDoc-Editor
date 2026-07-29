---
type: plan
node_id: plan:2026-07-29-compare-oom-root-fix
title: 对比功能内存爆炸根治：向量化聚类+子进程隔离
date: 2026-07-29
---

# 对比功能内存爆炸根治：向量化聚类+子进程隔离


## 背景
2026-07-29 律师 9 份物业投标文件串标对比，simhash 全叉积（20.7 亿次比较）+ 269 万条携带双份全文的配对记录 → uvicorn 60.8GB OOM。

## 关键决策
- similar 匹配改为 numpy 向量化精确匹配（uint64 XOR + bitwise_count，零近似）+ union-find 聚类：一组相似段落一条 MatchRecord，内存上界 = 段落总数
- 对比任务移入 spawn 子进程 + RLIMIT_AS 16GB：任何异常只杀子进程，主服务不死
- 配套：max_files=6（前端/后端/yaml 三处同步）、CompareRun 启动清扫、移除 markdown_path→raw_path 兜底重转、候选对 5000 万熔断（CompareTooComplexError 文案透传给律师）

## 实测（真实 9 文件 69,141 段）
- 预实验：全量 36 对 8.8s（旧算法 2h 未完成）、峰值 0.66GB、聚类压缩 321x、与旧算法零漏检零多检
- E2E（6 文件最重组合 56,902 段）：66s 完成，主进程 0.15GB / 子进程峰值 0.53GB；review.json 54MB（54MB 主体为文档块文本，前端走分层加载）
- 隔离验收：256MB 上限下子进程死亡 → 任务 failed（友好文案）→ healthz 存活
- 4 个中断对比 retry 全部 completed（47s）

## 实施
commits: 后端 ca6a1ce/0faab9d/17fc7b4/71952fc，前端 84808a5/9ef657b/391dcfb/67682ca；Codex 实现 + spec/quality/style 三阶段审核全过（后端 248 测试 / 前端 50 测试）

## 遗留
- 9 文件对比需求受 max_files=6 约束（该次任务需律师拆分重发）
- ISSUE-004（病态 PDF 分块不减体积）仍待办
