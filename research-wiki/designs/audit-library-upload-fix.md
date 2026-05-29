---
type: design
node_id: design:audit-library-upload-fix
title: "审核点库上传交互修复（拖拽 + .doc + 标题兜底）"
date: 2026-05-29
---

# 审核点库上传交互修复（拖拽 + .doc + 标题兜底）

- **状态**: 已批准（待实现）
- **关联**: 审核点库页面（`/audit-library`）、`FileSelectBox`、管道 A（extract_rules）/ rules 上传
- **方案**: 方案 A —— 增强 `FileSelectBox` 本体（不改 FileManagement 的 `UploadBar`）
- **范围**: 纯前端

## 1. 背景与问题

用户在 `/audit-library` 页测试上传时报告两个问题，经线上实测（无代理直连 `http://100.70.102.30:8080`，HTTP 200）+ 代码定位，全部落在前端：

| 问题 | 现象 | 根因 | 证据 |
|---|---|---|---|
| **拖拽无效** | 拖 PDF/Word 到上传框没反应（浏览器反而打开文件） | `FileSelectBox`（`AuditLibraryPage.tsx:74-98`）只是 `<label>` 包隐藏 `<input>`，**无任何拖拽事件处理器** | 实测 `onDrop:false, onDragOver:false`；文案却写"选择或拖入" |
| **`.doc` 选不了** | 点击选择时 PDF 可以，旧版 Word（`.doc`）不行 | extract 调用点 `accept=".md,.pdf,.docx"` **漏了 `.doc`**，被系统文件框过滤掉 | 实测 `FILE_INPUT_ACCEPT:[".md,.pdf,.docx"]`；后端 `files.py:15` `_SCRIVAI_SUFFIXES={".docx",".doc",".pdf"}` **本就支持 .doc** |

附带确认的两个交互痘点（用户要求一并修）：

- **标题必填误导**：「开始抽取」按钮需同时填「法规标题」+选文件才能点（`disabled` 逻辑），只选文件不填标题→按钮一直灰着→像坏了。实测：无标题 `disabled:true`，有标题 `disabled:false`。
- **拖错类型无反馈**：拖入不支持的格式应给提示，不能默默丢弃。

> 后端转换链（`store.get_or_convert` → MarkdownConverter/MonkeyOCR）已支持 `.doc/.docx/.pdf`，**无需后端改动**。

## 2. 架构与组件边界

将 `FileSelectBox` 从 `AuditLibraryPage.tsx` 内部函数**抽到独立文件并导出**，因为要给它加拖拽 + 扩展名过滤 + 错误状态。独立后单一职责清晰、可单测，且提取页/导入页共用同一增强组件（即"统一上传控件"）。`UploadBar`（FileManagement 用，横条多文件语义）不动。

```
AuditLibraryPage.tsx ──import──> components/FileSelectBox.tsx
  extract 模式: accept=".md,.pdf,.doc,.docx"   ├─ 点击选择 (<input type=file>)
  import  模式: accept=".xls,.xlsx,.csv"        ├─ 拖拽 (onDragOver/onDragLeave/onDrop)
                                                └─ 扩展名过滤 + 内联错误提示
```

## 3. 详细设计（函数级）

### 3.1 `frontend/src/components/FileSelectBox.tsx` [NEW]

从原 `AuditLibraryPage.tsx:74-98` 迁移并增强。

- **props 不变**：`{ title, subtitle, accept, onSelect }`，`onSelect: (file: File | null) => void`
- **内部 state**：`dragging: boolean`、`error: string | null`
- **工具**：
  - `parseAccept(accept: string): string[]` —— `accept.split(",").map(s => s.trim().toLowerCase())`
  - `matches(file: File): boolean` —— `exts.some(ext => file.name.toLowerCase().endsWith(ext))`（按扩展名，不用 MIME：`.doc/.docx` 的 MIME 不可靠）
- **事件处理**：
  - `onDragOver(e)`：`e.preventDefault()` + `setDragging(true)`（**必须 preventDefault，否则浏览器直接打开文件**）
  - `onDragLeave()`：`setDragging(false)`
  - `onDrop(e)`：`e.preventDefault()` + `setDragging(false)`；取 `e.dataTransfer.files[0]`；匹配 → `setError(null); onSelect(file)`；不匹配 → `setError(\`仅支持 ${accept} 格式\`)`
  - `<input onChange>`：保留原点击选择路径
- **视觉**：`dragging` 时切换高亮边框/底色（沿用现有 `hover:border-accent` 风格）；`error` 非空时在框下方渲染红字（`text-status-err`）

### 3.2 `frontend/src/pages/AuditLibraryPage.tsx` [MODIFY]

- 删除内部 `FileSelectBox` 定义，改为 `import { FileSelectBox } from "@/components/FileSelectBox"`（按项目现有别名约定）
- **extract 调用点（~417 行）**：
  - `accept=".md,.pdf,.doc,.docx"`，`subtitle="支持 .md, .pdf, .doc, .docx"`
  - `onSelect` 改为：
    ```ts
    setUploadFile(file);
    if (file && !uploadTitle.trim()) setUploadTitle(stripExt(file.name));
    ```
- **import 调用点（~468 行）**：`accept` 不变，自动获得拖拽能力，无标题逻辑

### 3.3 `frontend/src/pages/audit-library-utils.ts` [MODIFY]

- 新增 `stripExt(name: string): string` —— 去掉最后一个扩展名（无扩展名则原样返回）

## 4. 错误处理与边界

- 拖入不支持格式 → 内联红字提示，下次有效选择/拖入时清除
- 多文件拖入 → 取第一个匹配的（维持单文件 `onSelect(File)` 语义）
- 标题自动兜底**仅在标题为空（trim 后）时**触发，不覆盖用户已输入内容
- `preventDefault` 必须覆盖 `onDragOver` 与 `onDrop`，否则拖拽不生效

## 5. 测试计划

- **单测** `components/FileSelectBox.test.tsx`（vitest + @testing-library/react）：
  - 渲染后构造 `DataTransfer`，模拟**有效**文件 drop → 断言 `onSelect` 被调用、无错误
  - 模拟**无效**文件 drop → 断言 `onSelect` 不调用、错误文案出现
  - 点击选择（`input change`）路径仍正常
- **单测** `audit-library-utils.test.ts`：`stripExt` 各分支（多点文件名、无扩展名、中文名）
- **E2E**（`@playwright/cli`，遵循真实文件 + 每步截图约定）：扩展现有 audit 流程，进入 AI 提取 → 选 `.doc` 文件 → 断言文件名回显、标题自动填入、「开始抽取」由 disabled 变可点
- **验证命令**：`cd frontend && npm run test`；E2E：`cd frontend && npx playwright test`

## 6. 方案权衡（决策记录）

| 方案 | 取舍 | 结论 |
|---|---|---|
| **A 增强 `FileSelectBox` 本体** | 改动最小、保留虚线框视觉、提取/导入两处共用天然统一、纯前端 | **采纳** |
| B 复用 `UploadBar` | 视觉是横条非虚线框、多文件语义、`accept` 硬编码无 .md/xls，需大改 | 拒绝 |
| C 抽全新 `FileDropZone` 合并 `UploadBar` | 两控件视觉/单多文件语义不同，MVP 过度工程 | 拒绝（YAGNI）|
