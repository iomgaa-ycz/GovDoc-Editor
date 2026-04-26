# E2E 测试报告：AI 提取审核点流程

**测试日期**: 2026-04-20 (~08:22-08:27 UTC)  
**测试环境**: 前端 http://localhost:5173 / 后端 http://localhost:8000  
**Playwright CLI session**: `e2e_extract`  
**测试文件**: `2025年政府采购领域"四类"违法违规行为专项整治工作指引.doc` (.doc 7.8MB) 及 `.docx` (4.9MB)

---

## 测试结果摘要

| 步骤 | 结果 | 说明 |
|------|------|------|
| 打开审核点库页面 | PASS | 页面正常加载，显示审核点统计（终审5/草稿208/总计213） |
| 点击"上传"下拉菜单 | PASS | 下拉展开，显示"AI 提取"和"导入审查点表格"两个选项 |
| 选择"AI 提取"模式 | PASS | 表单正确显示：法规标题输入框 + 文件选择区 + 开始抽取按钮(disabled) |
| 填写法规标题 | PASS | 文本框正确接受中文输入 |
| 上传 .doc 文件 | PASS | 文件上传成功，显示文件名和大小(8038.0 KB)，开始抽取按钮启用 |
| 点击"开始抽取" (.doc) | **FAIL** | 后端返回 HTTP 500 Internal Server Error |
| 换用 .docx 文件重试 | **FAIL** | 后端同样返回 HTTP 500 Internal Server Error |
| 用极简 .md 文件测试 | **FAIL** | 后端同样返回 HTTP 500，确认问题与文件格式无关 |

**总体结论**: 前端交互流程（UI 层）工作正常，但后端 `POST /api/v1/rules/upload` 端点存在未捕获异常，所有文件类型均返回 500。

---

## 详细发现

### 1. 前端 UI 交互（PASS）

前端的 AI 提取流程 UI 设计合理，交互流畅：

- **入口清晰**: "上传" 下拉菜单提供 "AI 提取" 和 "导入审查点表格" 两种模式
- **表单验证**: 标题和文件两个字段都填写后，"开始抽取" 按钮才变为可用
- **文件展示**: 上传后正确显示文件名和大小，提供 "x" 按钮可移除文件
- **按钮状态**: 点击"开始抽取"后按钮正确变为 disabled 防止重复提交
- **支持格式提示**: 文件选择区标注"支持 .md, .txt, .pdf, .docx"

### 2. 后端 API 错误（FAIL -- 阻断性问题）

`POST /api/v1/rules/upload` 对所有文件类型均返回 500：

- **请求路径**: `/api/v1/rules/upload`（通过 Vite proxy 转发到 :8000）
- **HTTP 状态**: 500 Internal Server Error
- **响应体**: 空（`content-type: text/plain`）
- **影响**: 完全阻断 AI 提取功能

**可能原因分析**（基于代码审查 `govdoc/api/routes/rules.py`）：
- 第 36 行 `get_document_store()` 可能失败（配置或路径问题）
- 第 40 行 `store.get_or_convert()` 转换可能抛异常
- 第 46 行 `get_libraries()` 调用可能失败（qmd 数据库初始化问题）
- 第 47-51 行 `rule_library.add()` 可能抛出异常
- 路由函数没有 try-except 包裹，未捕获异常直接被 FastAPI 转为 500

**与上次测试的差异**：上次测试（03:42 UTC）该端点虽然很慢但最终有响应；本次（08:22 UTC）直接返回 500，可能是后端运行时状态已变化。

### 3. 前端错误处理（UX 问题）

- 500 错误发生后，前端**无可见的错误提示**（无 toast、无弹窗、无红色文字）
- "开始抽取"按钮从 disabled 静默恢复为可用状态
- 用户无法知道操作失败了，也不知道失败原因
- 错误仅出现在浏览器开发者控制台：`Error: API 500: Internal Server Error`
- 错误调用栈：`request (v3.ts:9)` -> `uploadRuleAndExtract (V3WorkbenchContext.tsx:124)` -> `handleUpload (AuditLibraryPage.tsx:72)`

### 4. 其他发现

- **favicon.ico 404**: `GET /favicon.ico` 返回 404（低优先级）
- **React Router 警告**: 控制台有 2 条 React Router v7 Future Flag 警告（低优先级）
- **文件格式说明 vs 实际支持**: 前端标注支持 `.md, .txt, .pdf, .docx`，但后端代码 `files.py` 实际也处理 `.doc`（`suffix in (".docx", ".doc")`）。建议前端标注与后端保持一致
- **文件名特殊字符**: 含 Unicode 引号（左右双引号 U+201C/U+201D）的文件名在 Playwright `upload` 命令中需要特殊处理（通过 `setInputFiles` + Unicode 转义或 symlink 才能上传成功）

---

## 截图记录

| 截图 | 说明 |
|------|------|
| `extract_form_filled.png` | .doc 文件上传后的表单状态 |
| `extract_error_500.png` | .doc 提交后的页面（无可见错误提示） |
| `extract_form_docx.png` | .docx 文件上传后的表单状态 |
| `extract_error_docx_500.png` | .docx 提交后的页面（同样无可见错误提示） |
| `extract_result.png` | 最终页面状态 |

---

## 建议修复优先级

| 优先级 | 问题 | 建议 |
|--------|------|------|
| **P0** | 后端 `/api/v1/rules/upload` 500 错误 | 检查后端 uvicorn 日志定位具体异常；给 `upload_rule()` 添加 try-except + 详细错误日志；修复 `get_libraries()` / `rule_library.add()` 的运行时问题 |
| **P1** | 前端无错误提示 | 在 `handleUpload` (AuditLibraryPage.tsx:72) 的 catch 块中显示 toast/alert 通知用户上传失败及原因 |
| **P2** | 前端支持格式标注不全 | 添加 `.doc` 到前端文件选择器的 accept 属性和说明文案 |
| **P3** | favicon.ico 404 | 添加 favicon 文件 |
