---
type: design
node_id: design:compare-lazy-load
title: 文档对比分层加载与前端重构
date: 2026-05-27
---

# 文档对比分层加载与前端重构

## 1. 背景与问题

3 份投标文件（共 26,689 段落）对比后生成 7.1GB `review.json`，通过 result API 返回 861MB JSON，浏览器无法解析渲染。

体积分布：

| 部分 | 大小 | 原因 |
|------|------|------|
| matches | 3,944 MB | 155 万条匹配，每条带完整 text（2,965 MB） |
| documents | 883 MB | 文档纯文本仅 5.4 MB，但 segments JSON 结构膨胀 |
| 其他 | < 1 MB | — |

附加问题：后端无并发限制，多任务同时执行可能 OOM；进度页独占一页但用户无法操作；失败任务无重试。

## 2. 设计目标

- 首屏秒开（< 5 MB），匹配列表可筛选浏览
- 点击匹配项后瞬间展示上下文（< 100 KB/次）
- 进度内嵌到入口页历史表格，减少页面跳转
- 失败任务可重试
- 后端并发受控，不因多任务 OOM

## 3. 后端变更

### 3.1 存储拆分

对比完成时，除现有 `review.json` 外，额外生成索引文件：

```
compare/{review_id}/
  review.json          ← 完整数据（现有，保留用于下载/导出）
  summary.json         ← 摘要 + matches 列表（无 text 字段），~3-5 MB
  blocks_{fileIndex}.json  ← 每个文件的 blocks 独立存储
  match_index.json     ← matchId → 各文件的 blockIndex 映射
```

`summary.json` 结构：

```json
{
  "reviewId": "...",
  "summary": { "fileCount": 3, "commonParagraphCount": 1200, ... },
  "categories": [...],
  "downloads": {...},
  "artifacts": {...},
  "matches": [
    {
      "id": "paragraph-001",
      "category": "paragraph",
      "label": "完全重复",
      "color": "#F59E0B",
      "length": 356,
      "fileIndices": [0, 1, 2],
      "occurrenceCount": 3,
      "preview": "本工程位于清远市..."
    }
  ]
}
```

`match_index.json` 结构：

```json
{
  "paragraph-001": {
    "0": { "blockIndices": [48], "text": "完整匹配文本..." },
    "1": { "blockIndices": [223] },
    "2": { "blockIndices": [198] }
  }
}
```

### 3.2 新增 API

| API | 方法 | 返回 | 大小 |
|-----|------|------|------|
| `/{review_id}/summary` | GET | summary.json 内容 | ~3-5 MB |
| `/{review_id}/context?matchId=xxx&surrounding=3` | GET | 匹配涉及的各文件上下文 blocks | ~50-100 KB |
| `/{review_id}/retry` | POST | 重新提交失败任务 | — |

context API 逻辑：
1. 从 `match_index.json` 读取 matchId 对应的 blockIndices
2. 从 `blocks_{fileIndex}.json` 切片读取前后各 N 段
3. 返回 `{ match: {...}, fileContexts: [...] }`

context 响应结构：

```json
{
  "match": {
    "id": "paragraph-001",
    "text": "完整匹配文本...",
    "category": "paragraph",
    "label": "完全重复",
    "color": "#F59E0B",
    "fileIndices": [0, 1, 2],
    "occurrenceCount": 3
  },
  "fileContexts": [
    {
      "fileIndex": 0,
      "name": "1广东宏业建设工程有限公司.pdf",
      "totalBlocks": 2581,
      "matchBlockIndex": 48,
      "blocks": [
        { "id": "b-46", "index": 46, "text": "...", "segments": [...] },
        { "id": "b-48", "index": 48, "text": "...", "segments": [...], "isMatchTarget": true },
        { "id": "b-50", "index": 50, "text": "...", "segments": [...] }
      ]
    }
  ]
}
```

### 3.3 retry API

`POST /{review_id}/retry`：
- 校验状态为 `failed`
- 从 `CompareRun` 读取 `document_ids`
- 创建新 `CompareRun`（新 reviewId），加入后台任务
- 返回新的 `{ reviewId, status: "pending" }`

### 3.4 并发控制

在 `govdoc/compare/` 增加 `asyncio.Semaphore` 或 `threading.Semaphore`，限制同时执行的对比任务数（默认 1）。超出的任务状态设为 `pending`（排队中），前序任务完成后自动触发。

配置项：`compare.max_concurrent`（默认 1），加入 `govdoc.yaml` 和 `CompareConfig`。

### 3.5 现有 API 保留

- `GET /{review_id}/result` — 保留但不再被前端调用，作为导出/调试用途
- `GET /{review_id}/status` — 不变
- `GET /` — 列表接口不变
- `POST /` — 创建接口增加排队逻辑

## 4. 前端变更

### 4.1 页面结构（3 页）

| 页面 | 路由 | 说明 |
|------|------|------|
| 入口页 | `/compare` | 新建任务 + 历史表格（行内进度） |
| 结果页 | `/compare/:id` | 统计卡片 + 匹配列表表格 / 上下文视图 |

结果页有两个状态：未选中匹配时显示匹配表格，选中后切换为左侧匹配清单 + 右侧多文件对照。

### 4.2 入口页改造

历史表格行为按状态区分：

| 状态 | 行样式 | 进度条 | 操作 |
|------|--------|--------|------|
| 已完成 | 默认 | 不显示 | 「查看」蓝色链接 |
| 进行中 | 蓝色左边框 + 浅蓝底 | 始终展开 6 步 | 无按钮 |
| 失败 | 默认 | 不显示 | 「重试」红色链接 |
| 排队中 | 默认 | 不显示 | 无按钮 |

进行中的行通过蓝色左边框（4px）+ 共享浅蓝背景将主行和进度条视觉绑定。

进度页不再单独存在，提交对比后留在入口页，行内自动显示进度。

### 4.3 结果页改造

**首屏（summary 模式）**：
- 调用 `GET /summary` 获取摘要（~5 MB），秒开
- 渲染：统计卡片（4 个）+ 分类筛选按钮 + 匹配列表表格
- 表格列：类型 | 匹配内容（preview，前 100 字）| 涉及文件 | 出现次数
- 提示"点击任意匹配项查看各文件对应段落"

**上下文模式（点击匹配后）**：
- 调用 `GET /context?matchId=xxx&surrounding=3` 获取上下文（~50 KB）
- 布局变为：左侧匹配清单（300px 侧栏）+ 右侧多文件段落对照
- 右侧每个涉及的文件一列，只渲染匹配段 + 前后各 3 段
- 每列标注"第 N 段 / 共 M 段"
- 匹配段黄色高亮 + 边框
- 未涉及的文件不显示

### 4.4 前端 API 层

新增函数（`frontend/src/api/compare.ts`）：

```typescript
getCompareSummary(reviewId: string): Promise<CompareSummary>
getCompareContext(reviewId: string, matchId: string, surrounding?: number): Promise<CompareContext>
retryCompareRun(reviewId: string): Promise<{ reviewId: string }>
```

## 5. 性能对比

| 指标 | 改前 | 改后 |
|------|------|------|
| 首屏数据量 | 861 MB | ~5 MB |
| 首屏加载时间 | 超时/白屏 | < 1s |
| 点击跳转数据量 | 0（已在内存） | ~50-100 KB |
| 点击跳转延迟 | N/A（崩溃） | < 200ms |
| DOM 节点数 | 26,000+ blocks | ~20 blocks |
| 浏览器内存 | 数 GB | < 50 MB |

## 6. Pencil 设计稿

3 个屏幕位于 `pencil/pencil-new.pen`：

- `Screen/DocCompare-Hub` — 入口页（4 种状态 + 行内进度）
- `Screen/DocCompare-Result-Summary` — 结果首屏（统计 + 匹配表格）
- `Screen/DocCompare-Result-Context` — 上下文视图（匹配清单 + 多文件对照）

## 7. 不变更

- `review.json` 完整数据保留，供导出和调试
- 对比算法本身不变
- 高亮 DOCX 下载功能不变
- 文件上传/转换流程不变
