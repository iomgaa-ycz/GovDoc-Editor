# E2E 测试报告：提取审核点（第二轮）

## 测试时间
2026-04-20 09:15-09:25 UTC (05:15-05:25 EDT)

## 测试步骤与结果

### Step 1: 打开审核点库页面
- 状态: 成功
- 页面显示：终审 5 / 草稿 364 / 总计 369
- API 已连通

### Step 2: 进入 AI 提取模式
- 状态: 成功
- 路径：上传 ▾ → AI 提取
- 表单显示：法规标题输入框 + 文件选择 + 开始抽取按钮（disabled）

### Step 3: 填写表单
- 状态: 成功
- 法规标题: "2025年政府采购领域四类违法违规行为专项整治工作指引"
- 文件: 2025年政府采购领域"四类"违法违规行为专项整治工作指引.doc (8038 KB)
- "开始抽取"按钮变为 enabled

### Step 4: 点击"开始抽取"
- 状态: 请求已发出
- `POST /api/v1/rules/upload` 发送成功
- 按钮变为 disabled（表示处理中）

### Step 5: 等待后端处理
- 状态: **失败 — OOM Killed**
- 尝试了 3 次（2 次 conda run，1 次直接启动），每次 uvicorn 进程都被 OOM killer 杀掉
- dmesg 确认: `Out of memory: Killed process 52817 (uvicorn) total-vm:81071376kB, anon-rss:22106724kB`
- 进程虚拟内存 81GB，RSS 22GB，超过物理内存 32GB

## 根因分析

`POST /api/v1/rules/upload` 是**同步**端点，在单一请求中依次执行：
1. .doc → markdown 转换（通过 MonkeyOCR HTTP 服务，OK）
2. qmd 索引（加载 Qwen3-Embedding-0.6B 模型，~834MB RSS）
3. LLM 审核点抽取（Scrivai PES 三阶段）

步骤 2+3 叠加导致单进程内存飙升到 22GB+，触发 OOM killer。

## 发现的问题

| 优先级 | 问题 | 说明 |
|--------|------|------|
| **P0** | OOM: rules/upload 同步执行重量级操作 | qmd embedding 模型 + PES LLM 调用在单一同步请求中执行，内存爆炸 |
| **P1** | 无异步处理 | rules/upload 应返回 202 + run_id，后台异步执行转换/索引/抽取 |
| **P1** | 前端无错误反馈 | 500 后前端无 toast/弹窗，按钮从 disabled 恢复但用户不知道失败 |

## 建议修复

1. 将 `rules/upload` 改为异步：立即返回 202 + `extract_run_id`，后台 task 执行转换/索引/抽取
2. 前端轮询 `GET /rules/{id}/extract-runs/{run_id}/status` 获取进度
3. qmd embedding 模型预加载到独立 worker，避免在请求处理线程中加载

## 截图
- `tests/e2e/reports/r2_extract_form_ready.png` — 表单填写完成状态
- `tests/e2e/reports/r2_extract_result.png` — 最终状态（500 后）

## 最终结论
- **前端交互流程**: 通过（导航、表单、文件上传、按钮状态管理全部正常）
- **后端处理**: 失败（OOM，架构性问题，需要将同步操作改为异步）
- **OCR 服务连通性**: 通过（新地址 100.83.164.94:7865 可达，不再 ConnectionRefused）
