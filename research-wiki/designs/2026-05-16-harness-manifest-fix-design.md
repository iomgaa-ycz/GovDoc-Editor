---
type: design
id: harness-manifest-fix
title: "L2 Harness Manifest 修正——指向原始招标文件"
created: 2026-05-16
status: approved
---

# L2 Harness Manifest 修正

## 问题

L2 harness manifest (`scripts/fixtures/harness_manifest.yaml`) 的 `tender_doc` 指向了**工作底稿**（1-2KB 的 .docx），而非原始招标文件（PDF）。工作底稿是系统的输出目标，不是输入。导致 agent 面对几段话的摘要做 52 个审核点的审核，85% 返回"存疑"。

## 方案

修改 manifest 指向正确的原始招标文件 PDF，同时手动解压汕头项目 ZIP。

### 从化项目

- `tender_doc` → `real_data/.../3、从化区.../从化区中医医院...招标文件（2024040902）.pdf.pdf`（676KB）
- `supplementary_docs` → `[real_data/.../3、从化区.../广州市从化区...合同.pdf]`（24MB）
- 跳过 190MB 归档资料（后续再处理）

### 汕头项目

- 先手动解压 ZIP 到 `real_data/` 对应目录下
- `tender_doc` → 解压后的招标公告 PDF（~120KB）

## 预期效果

- "存疑"率从 85% 降到 20-30%
- `agent-step-efficiency` 维度预期通过
- 运行时间不变

## 不做的事

- 不改业务代码
- 不加 ZIP 自动解压（MVP 手动）
- 不处理 190MB 归档资料
