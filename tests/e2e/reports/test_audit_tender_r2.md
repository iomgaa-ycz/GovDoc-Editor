# E2E 测试报告: AI批量审核流程 (R2)

**测试时间**: 2026-04-20 ~08:52 - ~09:10 (UTC)
**Playwright Session**: `r2_audit`
**测试环境**:
- 前端: http://localhost:5173
- 后端: http://localhost:8000
- OCR 服务: http://100.83.164.94:7865

---

## 测试摘要

| 步骤 | 操作 | 结果 | 备注 |
|------|------|------|------|
| 1. 打开页面 | 导航到 /ai-review | **PASS** | 页面正常加载 |
| 2. 创建新项目 | 输入"E2E测试R2-从化区中医医院"并点击新建 | **PASS** | 项目创建成功，下拉框自动选中 |
| 3. 上传 PDF (新项目) | 上传从化区中医医院招标文件 PDF | **FAIL** | 500 Internal Server Error |
| 4. 切换已有项目 | 选择"E2E测试-从化区中医医院" | **PASS** | 文书已上传，显示 5 个审核点 |
| 5. 选择审核点 | 勾选全部 5 个审核点 | **PASS** | 按钮变为"启动审核 (5 个审核点)" |
| 6. 启动审核 | 点击"启动审核" | **PASS** | 审核运行 75877fc0 创建成功 |
| 7. 监控进度 | 轮询 progress API | **FAIL** | API 约 2-3 分钟后开始持续返回 500 |
| 8. 等待完成 | 等待 >10 分钟 | **FAIL** | 后端所有 DB 相关 API 均 500 |

**总体结果**: **FAIL** — 审核启动成功但后端数据库锁导致 progress API 持续 500

---

## 详细记录

### 步骤 1: 打开 AI 批量审核页面

- URL: `http://localhost:5173/ai-review`
- 页面标题: "GovDoc Auditor V3"
- 顶部状态栏: "GovDoc V3 已连通 | 待启动项目审查"
- 页面布局: 三栏 — 任务设置 | 审核进度 | 审核点进度
- 现有项目: smoke-test, E2E测试-从化区中医医院, E2E测试-审核流程

### 步骤 2: 创建新项目

- 在"新项目名称"输入框中输入: "E2E测试R2-从化区中医医院"
- 点击"新建"按钮
- API 响应: `POST /api/v1/projects => [201] Created`
- 项目 ID: `b9a59ce0fde84c80b041d4ee65c8d93c`
- 下拉框自动切换到新项目

### 步骤 3: 上传 PDF 文件 (新项目)

- 文件: `从化区中医医院手术室设备及附件、病房护理及医院设备采购招标文件（2024040902）.pdf.pdf`
- 文件大小: 676.7 KB
- 通过 `setInputFiles` 选择文件，点击"上传文书"按钮
- API 请求: `POST /api/v1/projects/b9a59ce0fde84c80b041d4ee65c8d93c/tender-doc`
- 等待约 2 分钟后返回: **500 Internal Server Error**

**根因分析**:
- 后端调用 `scrivai.pdf_to_markdown(raw, base_url=ocr_url)` 失败
- OCR URL: `http://100.83.164.94:7865`
- `_convert_pdf` 方法在失败时抛出 `RuntimeError`，未被 API 层捕获为友好错误

**前端 Bug**: 上传失败（500）后，"上传文书"按钮仍然保持 loading 状态（旋转图标），没有显示任何错误信息给用户。错误只在浏览器控制台中可见。

### 步骤 4-5: 使用已有项目

- 切换到"E2E测试-从化区中医医院"项目
- 文书已上传: `从化区中医医院手术室设备及附件、病房护理及医院设备采购.docx`
- 显示 5 个终稿审核点:
  1. 2.限定供应商所在行业或限制其他行业供应商参与竞争。
  2. 3.设置对企业规模的不合理限制以排斥中小企业。
  3. 1.直接或变相对外地企业进入本地市场设置阻碍。
  4. 1.直接或变相对外地企业进入本地市场设置阻碍。（重复）
  5. 2.限定供应商所在行业或限制其他行业供应商参与竞争。（重复）
- 全部勾选后按钮显示"启动审核 (5 个审核点)"

**注意**: 审核点 3 和 4 重复了审核点 1 和 5，可能是导入数据问题。

### 步骤 6: 启动审核

- 点击"启动审核 (5 个审核点)"
- 成功创建 AuditRun: `75877fc005b847d1a57a825a26f509ae`
- 顶部状态栏更新: "审核运行 75877fc0 | 当前审核已就绪"
- progress API 初始响应正常:
  ```json
  {
    "status": "running",
    "total_count": 5,
    "processed_count": 0,
    "point_runs": [
      {"id": "767da324...", "status": "running"},
      {"id": "e38289c2...", "status": "pending"},
      {"id": "187c9cab...", "status": "pending"},
      {"id": "5b605c50...", "status": "pending"},
      {"id": "30412d10...", "status": "pending"}
    ]
  }
  ```

### 步骤 7-8: 监控进度 — 后端崩溃

- 审核启动后约 2-3 分钟，progress API 开始返回 500
- 之后所有涉及数据库的 API 端点均返回 500:
  - `GET /api/v1/audit/runs/.../progress` => 500
  - `GET /api/v1/projects` => 500
  - `GET /api/v1/checkpoints` => 500
- FastAPI 进程仍然存活（`GET /docs` => 200）
- 500 状态持续超过 15 分钟，未恢复

**根因推测**: SQLite 数据库并发锁问题。后台审核任务（PES 运行 + LLM 调用）在写数据库时持有长时间锁，阻塞了所有 API 读请求，导致读超时返回 500。

---

## 截图清单

| 文件名 | 说明 |
|--------|------|
| `r2_audit_uploading.png` | PDF 上传中（loading 状态） |
| `r2_audit_upload_error.png` | PDF 上传 500 错误后（按钮仍 loading，无错误提示） |
| `r2_audit_setup.png` | 已有项目 + 5 个审核点全部勾选 |
| `r2_audit_progress.png` | 审核已启动，1 running + 4 pending |
| `r2_audit_progress_500.png` | Progress API 500 后页面冻结状态 |
| `r2_audit_result.png` | 最终截图（页面仍冻结） |

---

## 发现的 Bug

### BUG-1: PDF 上传 500 后前端无错误提示 (P1)

- **现象**: PDF 上传返回 500 后，"上传文书"按钮仍然保持 loading 旋转状态，不恢复，也不显示错误信息
- **影响**: 用户无法得知上传失败的原因
- **位置**: `frontend/src/hooks/useProjectWorkflow.ts:23` / `frontend/src/context/V3WorkbenchContext.tsx:160`
- **建议**: 在 catch 块中重置 loading 状态并显示友好错误消息

### BUG-2: SQLite 并发锁导致全局 API 500 (P0)

- **现象**: 启动审核后约 2-3 分钟，所有涉及 DB 的 API 均返回 500
- **影响**: 系统完全不可用，无法查询任何数据
- **根因**: 后台审核任务使用同步 SQLite 写入，长时间持有数据库锁（PES 运行可能 3-5 分钟/审核点），阻塞所有并发的 API 读请求
- **建议**:
  1. 使用 `WAL` (Write-Ahead Logging) 模式配置 SQLite，允许并发读写
  2. 审核任务中缩短事务时间：仅在状态更新时打开短事务，而不是整个 PES 运行期间持有连接
  3. 使用独立的数据库连接（或连接池）用于后台任务
  4. 考虑迁移到 PostgreSQL 以支持更好的并发

### BUG-3: 审核点重复 (P2)

- **现象**: 5 个终稿审核点中有 2 对重复内容
- **影响**: 浪费审核资源，重复审核相同条款
- **建议**: 在审核点导入/终稿流程中增加去重校验

---

## 前端控制台错误汇总

| 级别 | 数量 | 说明 |
|------|------|------|
| ERROR | ~200+ | 主要是 progress API 持续 500 的错误 |
| WARNING | 2 | React Router v7 future flag 警告（正常） |
| ERROR | 1 | favicon.ico 404（无关紧要） |
| ERROR | 1 | tender-doc 上传 500 |

---

## 网络请求时间线

1. `GET /api/v1/projects` => 200 (页面加载)
2. `GET /api/v1/checkpoints` => 200
3. `GET /api/v1/audit/runs` => 200
4. `POST /api/v1/projects` => 201 (创建新项目)
5. `POST /api/v1/projects/.../tender-doc` => 500 (~2 分钟后，PDF OCR 失败)
6. `GET /api/v1/projects/.../tender-docs` => 200 (切换项目)
7. `POST /api/v1/audit/runs` => 201/202 (启动审核)
8. `GET /api/v1/audit/runs/.../progress` => 200 (前几次正常)
9. `GET /api/v1/audit/runs/.../progress` => 500 (之后持续 500)

---

## 结论

AI 批量审核流程的前端交互（项目创建、文件选择、审核点勾选、启动审核）基本可用。但存在两个阻断性问题：

1. **PDF 上传依赖 OCR 服务**，当 OCR 服务不可用或处理失败时，返回 500 且前端无任何错误反馈
2. **SQLite 并发锁**是最严重的问题：后台审核任务运行时会锁死整个数据库，导致所有 API 不可用。这使得无法在前端观察审核进度或执行其他操作

建议在解决 BUG-2（SQLite WAL 模式 + 事务优化）后重新执行此 E2E 测试。
