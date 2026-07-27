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

## ISSUE-004 病态 PDF 分块不减体积 → 建议整文件直发退化策略（待办）

- **日期**: 2026-07-27（登记，未实施）
- **现象**: 部分扫描版 PDF（如事故文件，876 页/160MB）所有页共享同一全局资源树（图片对象流），pypdf 按页分块后**每个分块仍 ~143-163MB**（`compress_identical_objects(remove_orphans)` 实测无效）。876 页 → 18 块 × 143MB ≈ 2.6GB 需传给 MonkeyOCR。
- **加重因素**: 后端部署机 pci-3 与 MonkeyOCR 机 4090-server 之间 Tailscale 走 DERP 中继（hkg，~1MB/s），该类文件单份转换耗时 1.5~3 小时。
- **建议方案**（scrivai，二选一）: (a) `chunk_pdf` 后检测「分块总字节 / 源文件字节 > 阈值（如 3x）」时退化为整文件单次发送（传输量降 ~18x，牺牲 OCR 并行度）；(b) 解决两机 Tailscale 直连（打洞/端口映射），带宽提升后此问题自然缓解。
- **优先级**: 中（当前功能正确、内存受控，仅影响该类文件的转换时长）。
