---
type: plan
node_id: plan:unified-doc-conversion
title: 统一文档转 Markdown 路径实施计划
date: 2026-05-14
tags: ["scrivai", "conversion", "monkeyocr"]
implements: design:unified-doc-conversion
---

# 统一文档转 Markdown 路径实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `DocumentStore` 从已删除的 `scrivai.docx_to_markdown` / `pdf_to_markdown` 迁移到 Scrivai 0.1.8 统一接口 `scrivai.to_markdown`，解决 DOCX/PDF 双路径不一致和 DOC 无法转换的问题。

**Architecture:** `DocumentStore` 删除三个旧方法（`_convert_docx`、`_convert_pdf`、`_fallback_text_extract`），新增一个 `_convert` 方法统一调 `scrivai.to_markdown(path)`。OCR 服务地址通过 `govdoc.yaml` → `AppConfig.ocr_base_url` → `DocumentStore.__init__` 注入。

**Tech Stack:** Python 3.11 / Scrivai 0.1.8 / MonkeyOCR / LibreOffice / pandoc

---

## 文件清单

| 文件 | 动作 | 职责 |
|------|------|------|
| `govdoc/config.py:25-31` | MODIFY | `AppConfig` 新增 `ocr_base_url` 字段 |
| `govdoc.yaml:1-5` | MODIFY | `app` 节新增 `ocr_base_url` |
| `govdoc/storage/files.py` | MODIFY | 核心改造：删旧方法，新增 `_convert`，改 `__init__` 和 `get_or_convert` |
| `govdoc/runtime.py:37-39` | MODIFY | `get_document_store()` 传入 `ocr_base_url` |
| `tests/unit/test_document_store.py` | CREATE | 单元测试 |
| `CLAUDE.md:36-43` | MODIFY | NO_PROXY 加 `100.81.95.44` |

---

### Task 1: 配置层 — `AppConfig` 新增 `ocr_base_url`

**Files:**
- Modify: `govdoc/config.py:25-31`
- Modify: `govdoc.yaml:1-5`
- Test: `tests/unit/test_config.py`（已有，验证加载不报错即可）

- [ ] **Step 1: 修改 `AppConfig`**

在 `govdoc/config.py` 的 `AppConfig` 类中新增字段：

```python
class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = "0.0.0.0"
    port: int = 8000
    storage_root: str = "./data/storage"
    database_url: str = "sqlite:///./data/app.sqlite"
    ocr_base_url: str | None = None
```

- [ ] **Step 2: 修改 `govdoc.yaml`**

在 `app` 节下新增一行：

```yaml
app:
  host: 0.0.0.0
  port: 8000
  storage_root: ./data/storage
  database_url: sqlite:///./data/app.sqlite
  ocr_base_url: null
```

- [ ] **Step 3: 运行现有配置测试确认不破坏**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_config.py -v`
Expected: PASS（现有测试全绿，`extra="forbid"` 不会拒绝 `None` 值）

- [ ] **Step 4: Commit**

```bash
git add govdoc/config.py govdoc.yaml
git commit -m "feat(config): AppConfig 新增 ocr_base_url 字段"
```

---

### Task 2: `DocumentStore` 核心改造

**Files:**
- Modify: `govdoc/storage/files.py`

- [ ] **Step 1: 修改 `__init__` 接收 `ocr_base_url`**

将 `govdoc/storage/files.py` 中 `DocumentStore.__init__` 改为：

```python
def __init__(self, storage_root: Path, *, ocr_base_url: str | None = None) -> None:
    self._root = storage_root
    self._prepared_dir = storage_root / "prepared"
    self._raw_dir = storage_root / "raw"
    self._ocr_base_url = ocr_base_url
    self._prepared_dir.mkdir(parents=True, exist_ok=True)
    self._raw_dir.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: 新增 `_convert` 方法，替换 `_convert_docx` / `_convert_pdf` / `_fallback_text_extract`**

删除 `_convert_docx`（第 123-135 行）、`_convert_pdf`（第 137-150 行）、`_fallback_text_extract`（第 152-159 行）三个方法，替换为：

首先，在 `files.py` 文件顶部 import 区域新增模块级 import 和常量：

```python
from scrivai import to_markdown as _scrivai_to_markdown

_SCRIVAI_SUFFIXES = frozenset({".docx", ".doc", ".pdf"})
```

然后新增 `_convert` 方法（替换被删除的三个方法）：

```python
def _convert(self, raw: Path, target: Path, warnings_stack: list[str] | None) -> Path:
    """通过 scrivai.to_markdown 统一转换 .docx/.doc/.pdf。"""
    md = _scrivai_to_markdown(raw, ocr_base_url=self._ocr_base_url)
    if not md or not md.strip():
        raise RuntimeError(f"to_markdown 返回空内容: {raw}")
    target.write_text(md, encoding="utf-8")
    return target
```

- [ ] **Step 3: 改写 `get_or_convert` 路由逻辑**

将 `get_or_convert` 方法中第 98-108 行的 `if/elif/else` 替换为：

```python
if suffix in _SCRIVAI_SUFFIXES:
    prepared = self._convert(raw, prepared, warnings_stack)
else:
    msg = f"不支持的文档格式: {suffix}，尝试作为纯文本处理"
    if warnings_stack is not None:
        warnings_stack.append(msg)
    warnings.warn(msg)
    text = content.decode("utf-8", errors="replace")
    prepared.write_text(text, encoding="utf-8")
```

- [ ] **Step 4: 清理无用 import**

检查 `files.py` 顶部 import。删除后 `warnings` 仍需要（纯文本 fallback 用到），其余 import 均保留。无需改动。

- [ ] **Step 5: Commit**

```bash
git add govdoc/storage/files.py
git commit -m "feat(storage): DocumentStore 统一调 scrivai.to_markdown"
```

---

### Task 3: `runtime.py` 传入 `ocr_base_url`

**Files:**
- Modify: `govdoc/runtime.py:37-39`

- [ ] **Step 1: 修改 `get_document_store`**

将 `govdoc/runtime.py` 中第 37-39 行改为：

```python
@lru_cache
def get_document_store() -> DocumentStore:
    cfg = get_config()
    return DocumentStore(cfg.storage_root, ocr_base_url=cfg.app.ocr_base_url)
```

- [ ] **Step 2: Commit**

```bash
git add govdoc/runtime.py
git commit -m "feat(runtime): get_document_store 传入 ocr_base_url"
```

---

### Task 4: 单元测试

**Files:**
- Create: `tests/unit/test_document_store.py`

- [ ] **Step 1: 创建测试文件**

创建 `tests/unit/test_document_store.py`：

```python
"""DocumentStore 单元测试：验证 scrivai.to_markdown 统一转换路径。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from govdoc.storage.files import DocumentStore


@pytest.fixture()
def store(tmp_path: Path) -> DocumentStore:
    """创建使用临时目录的 DocumentStore。"""
    return DocumentStore(tmp_path)


@pytest.fixture()
def store_with_ocr(tmp_path: Path) -> DocumentStore:
    """创建带自定义 ocr_base_url 的 DocumentStore。"""
    return DocumentStore(tmp_path, ocr_base_url="http://custom-ocr:7861")


class TestGetOrConvert:
    """get_or_convert 路由逻辑测试。"""

    def test_md_file_returns_directly(self, store: DocumentStore, tmp_path: Path) -> None:
        """已是 .md 的文件直接返回，不经过转换。"""
        md_file = tmp_path / "raw" / "test.md"
        md_file.parent.mkdir(parents=True, exist_ok=True)
        md_file.write_text("# Hello", encoding="utf-8")
        result = store.get_or_convert(md_file)
        assert result == md_file

    @pytest.mark.parametrize("suffix", [".docx", ".doc", ".pdf"])
    @patch("govdoc.storage.files._scrivai_to_markdown", return_value="# Converted content")
    def test_supported_formats_call_to_markdown(
        self, mock_to_md, suffix: str, store: DocumentStore, tmp_path: Path
    ) -> None:
        """docx/doc/pdf 三种格式均调用 scrivai.to_markdown。"""
        raw_file = tmp_path / "raw" / f"test{suffix}"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"fake content")

        result = store.get_or_convert(raw_file)

        mock_to_md.assert_called_once_with(raw_file, ocr_base_url=None)
        assert result.exists()
        assert result.read_text(encoding="utf-8") == "# Converted content"

    @patch("govdoc.storage.files._scrivai_to_markdown", return_value="# OCR result")
    def test_ocr_base_url_passed_through(
        self, mock_to_md, store_with_ocr: DocumentStore, tmp_path: Path
    ) -> None:
        """自定义 ocr_base_url 正确传递给 to_markdown。"""
        raw_file = tmp_path / "raw" / "test.pdf"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"fake pdf")

        store_with_ocr.get_or_convert(raw_file)

        mock_to_md.assert_called_once_with(raw_file, ocr_base_url="http://custom-ocr:7861")

    @patch("govdoc.storage.files._scrivai_to_markdown", return_value="")
    def test_empty_result_raises(
        self, mock_to_md, store: DocumentStore, tmp_path: Path
    ) -> None:
        """to_markdown 返回空字符串时抛 RuntimeError。"""
        raw_file = tmp_path / "raw" / "test.docx"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"fake docx")

        with pytest.raises(RuntimeError, match="返回空内容"):
            store.get_or_convert(raw_file)

    @patch("govdoc.storage.files._scrivai_to_markdown", side_effect=IOError("OCR unreachable"))
    def test_conversion_error_propagates(
        self, mock_to_md, store: DocumentStore, tmp_path: Path
    ) -> None:
        """scrivai 抛出的 IOError 原样上抛，不被吞掉。"""
        raw_file = tmp_path / "raw" / "test.pdf"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"fake pdf")

        with pytest.raises(IOError, match="OCR unreachable"):
            store.get_or_convert(raw_file)

    def test_unsupported_format_fallback_text(
        self, store: DocumentStore, tmp_path: Path
    ) -> None:
        """非文档格式降级为纯文本提取。"""
        raw_file = tmp_path / "raw" / "data.csv"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_text("a,b,c\n1,2,3", encoding="utf-8")

        warnings_stack: list[str] = []
        result = store.get_or_convert(raw_file, warnings_stack=warnings_stack)

        assert result.exists()
        assert "a,b,c" in result.read_text(encoding="utf-8")
        assert any("不支持" in w for w in warnings_stack)

    def test_file_not_found_raises(self, store: DocumentStore) -> None:
        """原始文件不存在时抛 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError, match="原始文件不存在"):
            store.get_or_convert("/nonexistent/file.docx")


class TestSha256Cache:
    """SHA256 缓存机制测试。"""

    @patch("govdoc.storage.files._scrivai_to_markdown", return_value="# Cached")
    def test_second_call_uses_cache(
        self, mock_to_md, store: DocumentStore, tmp_path: Path
    ) -> None:
        """相同内容的文件第二次调用不再触发 to_markdown。"""
        raw_file = tmp_path / "raw" / "test.docx"
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(b"same content")

        store.get_or_convert(raw_file)
        store.get_or_convert(raw_file)

        assert mock_to_md.call_count == 1
```

- [ ] **Step 2: 运行测试确认全部通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_document_store.py -v`
Expected: 8 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_document_store.py
git commit -m "test(storage): DocumentStore 单元测试覆盖统一转换路径"
```

---

### Task 5: CLAUDE.md NO_PROXY 更新

**Files:**
- Modify: `CLAUDE.md:36-43`

- [ ] **Step 1: 更新 NO_PROXY 代码块和说明**

将 `CLAUDE.md` 中 NO_PROXY 相关的 bash 代码块（第 37-39 行区域）更新为：

```bash
export no_proxy="110.42.53.85,100.81.95.44,localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="110.42.53.85,100.81.95.44,localhost,127.0.0.1,${NO_PROXY:-}"
```

在紧随其后的说明列表中，`110.42.53.85` 条目之后新增一条：

```
>   - `100.81.95.44` = MonkeyOCR 文档转换服务（Tailscale），Scrivai `to_markdown` 依赖
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: NO_PROXY 加入 MonkeyOCR 地址 100.81.95.44"
```

---

### Task 6: 全量回归验证

- [ ] **Step 1: 运行全部单元测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v`
Expected: 全部 PASS，无 import 错误

- [ ] **Step 2: 确认 scrivai 旧 API 不再被引用**

Run: `grep -r "docx_to_markdown\|pdf_to_markdown" govdoc/ tests/ --include="*.py"`
Expected: 无输出（零引用）

- [ ] **Step 3:（可选）集成烟雾测试**

仅在 MonkeyOCR 可达时执行：

```bash
source activate govdoc-auditor-v3 && \
export NO_PROXY="100.81.95.44,110.42.53.85,localhost,127.0.0.1" && \
python -c "
from scrivai import to_markdown
md = to_markdown('real_data/sample.docx')
print(f'OK: {len(md)} chars')
"
```

Expected: 输出 `OK: N chars`（N > 0）

---
