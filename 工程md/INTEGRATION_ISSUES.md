# 上游依赖变更登记（qmd / scrivai）

> 按 CLAUDE.md 约定：qmd 不可修改、scrivai 变更需先在此登记。每条 ISSUE 记录动机、变更内容、版本与影响面。

## ISSUE-001 `.claude/skills` symlink（历史）

skills/ 与 agents/ 放项目根，`.claude/skills` 为指向 `skills/` 的 symlink（EvoSkill 路径兼容）。详见 CLAUDE.md §4.1。

## ISSUE-002 workpaper.docx 手工模板（历史）

`templates/workpaper.docx` 必须 Word/LibreOffice 手工制作；docxtpl + python-docx 程序化生成会拆 `<w:r>` 导致解析失败。详见 CLAUDE.md §4.5。

## ISSUE-003 scrivai `chunk_pdf` 全量驻留内存 → v0.2.4 流式化

- **日期**: 2026-07-27
- **影响版本**: scrivai 0.2.3 → 0.2.4
- **动机（生产事故）**: 2026-07-24 stable 后端并发转换 10 份 43~322MB 扫描版 PDF，`scrivai/io/chunking.py:chunk_pdf()` 把每个 PDF 的全部分块字节物化驻留内存（`ChunkInfo.pdf_bytes`），扫描件共享图片资源在各 chunk 重复复制，uvicorn 内存膨胀至 58GB 被内核 OOM 杀死（4090，62GB 无 swap）。
- **变更内容**:
  - `ChunkInfo` 删除 `pdf_bytes` 字段，仅保留页码范围 + 源路径；
  - 新增 `build_chunk_bytes(source_path, start_page, end_page)`，在 OCR worker 线程内按需构建单块字节（pypdf reader 非线程安全，每次调用独立打开）；
  - `converter.py` 两处消费点（MonkeyOCR 临时文件 / glm base64）改为按需调用。
- **效果**: 单文件转换内存峰值从「全部分块 × 块大小」降为「backend 并发数（monkey=3）× 单块大小」。
- **配套业务侧防护**（GovDoc）: `documents.py` 转换并发上限 2（Semaphore）+ 上传 1GB 限额（前端/后端/nginx 三层一致）。
