---
type: design
node_id: design:unified-doc-conversion
title: 统一文档转 Markdown 路径（Scrivai 0.1.8 适配）
date: 2026-05-14
tags: ["scrivai", "conversion", "monkeyocr"]
---

# 设计：统一文档转 Markdown 路径

> 日期：2026-05-14
> 状态：已批准

## 1. 背景与问题

Scrivai 0.1.8 发布，**删除**了旧的 `docx_to_markdown` / `pdf_to_markdown` 两个函数，替换为统一入口 `to_markdown(path)`。

当前 `DocumentStore`（`govdoc/storage/files.py`）的问题：

| 问题 | 影响 |
|------|------|
| `_convert_docx()` 调用已删除的 `scrivai.docx_to_markdown` | 升级后所有 DOCX 转换崩溃 |
| `_convert_pdf()` 调用已删除的 `scrivai.pdf_to_markdown` | 升级后所有 PDF 转换崩溃 |
| `.doc` 和 `.docx` 共用 `_convert_docx()`，fallback 为纯文本提取 | `.doc` 转换质量极差或报错 |
| DOCX/PDF 两条独立路径，错误处理不一致 | docx 吞错 fallback，pdf 直接报错 |

## 2. 决策记录

| 决策点 | 结论 | 理由 |
|---|---|---|
| 方案选择 | 方案 A：全部改调 `scrivai.to_markdown` | 最小改动、一条路径、Scrivai 全权负责格式路由 |
| 业务层 fallback | 不再做纯文本 fallback | Scrivai 自带 pandoc fallback，业务层再吞错会掩盖问题 |
| OCR 配置注入 | `govdoc.yaml` → `AppConfig.ocr_base_url` → `DocumentStore` | 保持配置优先级链一致 |

**被否决的方案**：

- **方案 B**（保留双路径 + 修补）：Scrivai 已统一路由，业务层再拆无意义，代码重复
- **方案 C**（薄适配层 + 后处理 hook）：YAGNI，无证据需要差异化后处理

## 3. Scrivai 0.1.8 `to_markdown` 接口

```python
to_markdown(
    path: str | Path,
    *,
    ocr_base_url: str | None = None,   # MonkeyOCR 地址
    timeout: int = 300,
    fallback: bool = True,              # pandoc 降级开关
    upload_rate: int | None = None,     # 上传限速
) -> str
```

**路由逻辑**：
- `.pdf` → MonkeyOCR
- `.doc` / `.docx` → LibreOffice headless → PDF → MonkeyOCR
- fallback（OCR 不可达）：`.docx` → pandoc；`.doc` → LibreOffice → docx → pandoc

**外部依赖**：LibreOffice（已安装 7.3.7.2）、pandoc（已安装 2.9.2.1）、MonkeyOCR（Tailscale `100.81.95.44:7861`，已验证连通）

## 4. 变更清单

| 文件 | 动作 | 改动摘要 |
|------|------|----------|
| `govdoc/storage/files.py` | MODIFY | 删除 `_convert_docx`、`_convert_pdf`、`_fallback_text_extract`；新增 `_convert`；改写 `get_or_convert` 路由；`__init__` 接收 `ocr_base_url` |
| `govdoc/config.py` | MODIFY | `AppConfig` 新增 `ocr_base_url: str \| None = None` |
| `govdoc/runtime.py` | MODIFY | `get_document_store()` 传 `ocr_base_url=config.ocr_base_url` |
| `govdoc.yaml` | MODIFY | `app` 下新增 `ocr_base_url: null` |
| `CLAUDE.md` | MODIFY | NO_PROXY 列表加 `100.81.95.44` |
| `tests/unit/test_document_store.py` | NEW | mock `scrivai.to_markdown`，验证三种后缀统一走 `_convert` |

## 5. 错误处理策略

| 场景 | 行为 |
|------|------|
| 转换成功 | 写入 `prepared/{sha}.md`，正常返回 |
| OCR 不可达 + `.docx`/`.doc` | Scrivai 自动 fallback 到 pandoc |
| OCR 不可达 + `.pdf` | Scrivai 抛 `IOError`，原样上抛 |
| LibreOffice 缺失 | Scrivai 抛 `IOError`，原样上抛 |
| `to_markdown` 返回空字符串 | 业务层抛 `RuntimeError` |
| 非文档格式 | 保留纯文本 decode fallback |

## 6. 验证计划

1. **单元测试**：mock `scrivai.to_markdown`，验证 `.docx`/`.doc`/`.pdf` 三种后缀都走 `_convert`
2. **集成测试**：用 `real_data/` 中真实文件跑 `to_markdown`，确认 OCR 连通且输出非空
3. **手动**：Swagger UI 上传 `.doc` 文件，确认不再报错
