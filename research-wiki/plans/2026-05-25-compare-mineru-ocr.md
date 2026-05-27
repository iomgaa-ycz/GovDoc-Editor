# 对比模块 MinerU OCR 后端集成 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将文档对比模块的 PDF 转 Markdown 后端从 GLM-OCR 切换为 MinerU，使用独立的 DocumentStore 实例，与主管道完全隔离。

**Architecture:** 新增 `CompareConfig.ocr_backend` 配置字段，在 `runtime.py` 创建对等的 `get_compare_document_store()` 单例（独立 storage_root），`compare/service.py` 切换到该 store。DocumentStore 类零改动。

**Tech Stack:** Python 3.11 / scrivai >=0.2.1 / pydantic v2 / pytest

---

## 文件清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `pyproject.toml:21` | MODIFY | scrivai 版本声明 |
| `govdoc/config.py:82-91` | MODIFY | CompareConfig 新增 ocr_backend 字段 |
| `govdoc.yaml:34-38` | MODIFY | compare 配置块新增 ocr_backend |
| `govdoc/runtime.py:37-41` | MODIFY | 新增 get_compare_document_store() |
| `govdoc/compare/service.py:204-220` | MODIFY | 切换 PDF 转换使用 compare store |
| `tests/unit/test_document_store.py` | MODIFY | 新增双 store 缓存隔离测试 |

---

### Task 1: 升级 scrivai 依赖

**Files:**
- Modify: `pyproject.toml:21`

- [ ] **Step 1: 修改版本声明**

```python
# pyproject.toml 第 21 行
# 原:
"scrivai>=0.2.0",
# 改为:
"scrivai>=0.2.1",
```

- [ ] **Step 2: 安装并验证**

Run:
```bash
source activate govdoc-auditor-v3 && pip install -e . && pip show scrivai | grep Version
```
Expected: `Version: 0.2.1` (或更高)

- [ ] **Step 3: 验证 mineru 后端已注册**

Run:
```bash
source activate govdoc-auditor-v3 && python -c "from scrivai.io.convert import _BACKENDS; print(sorted(_BACKENDS.keys()))"
```
Expected: 输出包含 `'mineru'`

- [ ] **Step 4: 提交**

```bash
git add pyproject.toml
git commit -m "deps: upgrade scrivai to >=0.2.1 for MinerU OCR backend"
```

---

### Task 2: 配置层——CompareConfig 新增 ocr_backend

**Files:**
- Modify: `govdoc/config.py:82-91`
- Modify: `govdoc.yaml:34-38`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_config.py` 中追加（若文件不存在则创建）：

```python
"""CompareConfig.ocr_backend 配置测试。"""

from govdoc.config import CompareConfig, load_config


class TestCompareOcrBackend:
    """验证 CompareConfig 支持 ocr_backend 字段。"""

    def test_default_is_mineru(self) -> None:
        """CompareConfig 默认 ocr_backend 为 mineru。"""
        cfg = CompareConfig()
        assert cfg.ocr_backend == "mineru"

    def test_load_config_reads_compare_ocr_backend(self) -> None:
        """完整配置加载后 compare.ocr_backend 为 mineru。"""
        cfg = load_config()
        assert cfg.compare.ocr_backend == "mineru"
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_config.py::TestCompareOcrBackend -v
```
Expected: FAIL — `CompareConfig` 没有 `ocr_backend` 属性

- [ ] **Step 3: 实现——config.py 新增字段**

`govdoc/config.py` 第 82-91 行，`CompareConfig` 类新增一个字段：

```python
class CompareConfig(BaseModel):
    """文档对比功能配置。"""

    model_config = ConfigDict(extra="forbid")

    max_files: int | None = None
    min_segment_length: int = 16
    pdf_timeout_s: int = 3600
    simhash_threshold: int = 10
    ocr_backend: str = "mineru"
```

- [ ] **Step 4: 实现——govdoc.yaml 新增配置行**

`govdoc.yaml` 的 `compare:` 块末尾追加一行：

```yaml
compare:
  max_files: null
  min_segment_length: 16
  pdf_timeout_s: 3600
  ocr_backend: mineru
```

- [ ] **Step 5: 运行测试确认通过**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_config.py::TestCompareOcrBackend -v
```
Expected: 2 passed

- [ ] **Step 6: 运行全部单元测试确认无回归**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v
```
Expected: 全部 PASSED

- [ ] **Step 7: 提交**

```bash
git add govdoc/config.py govdoc.yaml tests/unit/test_config.py
git commit -m "feat(config): add CompareConfig.ocr_backend for MinerU support"
```

---

### Task 3: Runtime 层——新增 get_compare_document_store()

**Files:**
- Modify: `govdoc/runtime.py:37-41`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_runtime.py` 中追加（若文件不存在则创建）：

```python
"""get_compare_document_store 单元测试。"""

from unittest.mock import patch, MagicMock
from pathlib import Path

from govdoc.runtime import get_compare_document_store


class TestGetCompareDocumentStore:
    """验证对比模块 DocumentStore 工厂。"""

    def setup_method(self) -> None:
        get_compare_document_store.cache_clear()

    @patch("govdoc.runtime.get_config")
    def test_returns_store_with_mineru_backend(self, mock_get_config: MagicMock, tmp_path: Path) -> None:
        """get_compare_document_store 返回 ocr_backend=mineru 的 DocumentStore。"""
        cfg = MagicMock()
        cfg.storage_root = tmp_path
        cfg.compare.ocr_backend = "mineru"
        mock_get_config.return_value = cfg

        store = get_compare_document_store()

        assert store._ocr_backend == "mineru"

    @patch("govdoc.runtime.get_config")
    def test_storage_root_is_compare_prepared(self, mock_get_config: MagicMock, tmp_path: Path) -> None:
        """get_compare_document_store 使用 storage_root / compare_prepared 子目录。"""
        cfg = MagicMock()
        cfg.storage_root = tmp_path
        cfg.compare.ocr_backend = "mineru"
        mock_get_config.return_value = cfg

        store = get_compare_document_store()

        assert store._root == tmp_path / "compare_prepared"

    @patch("govdoc.runtime.get_config")
    def test_is_independent_from_main_store(self, mock_get_config: MagicMock, tmp_path: Path) -> None:
        """compare store 与主 store 是不同实例。"""
        from govdoc.runtime import get_document_store
        get_document_store.cache_clear()

        cfg = MagicMock()
        cfg.storage_root = tmp_path
        cfg.app.ocr_backend = "glm"
        cfg.compare.ocr_backend = "mineru"
        mock_get_config.return_value = cfg

        main_store = get_document_store()
        compare_store = get_compare_document_store()

        assert main_store is not compare_store
        assert main_store._ocr_backend == "glm"
        assert compare_store._ocr_backend == "mineru"
        assert main_store._root != compare_store._root
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_runtime.py::TestGetCompareDocumentStore -v
```
Expected: FAIL — `get_compare_document_store` 不存在

- [ ] **Step 3: 实现——runtime.py 新增工厂函数**

在 `govdoc/runtime.py` 中，紧跟 `get_document_store()` 之后（约第 41 行后）插入：

```python
@lru_cache
def get_compare_document_store() -> DocumentStore:
    """对比模块专用 DocumentStore（独立 storage_root + 独立 OCR 后端）。"""
    cfg = get_config()
    compare_root = cfg.storage_root / "compare_prepared"
    return DocumentStore(compare_root, ocr_backend=cfg.compare.ocr_backend)
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_runtime.py::TestGetCompareDocumentStore -v
```
Expected: 3 passed

- [ ] **Step 5: 运行全部单元测试确认无回归**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v
```
Expected: 全部 PASSED

- [ ] **Step 6: 提交**

```bash
git add govdoc/runtime.py tests/unit/test_runtime.py
git commit -m "feat(runtime): add get_compare_document_store() for MinerU OCR"
```

---

### Task 4: Compare 服务层——切换到 compare store

**Files:**
- Modify: `govdoc/compare/service.py:204-220`

- [ ] **Step 1: 写失败测试**

在 `tests/unit/test_compare_service.py` 中追加（若文件不存在则创建）：

```python
"""_extract_pdf_paragraphs 使用 compare store 的测试。"""

from pathlib import Path
from unittest.mock import patch, MagicMock

from govdoc.compare.service import _extract_pdf_paragraphs


class TestExtractPdfUsesCompareStore:
    """验证 _extract_pdf_paragraphs 使用 get_compare_document_store。"""

    @patch("govdoc.compare.service.get_compare_document_store")
    @patch("govdoc.compare.service.get_config")
    def test_calls_compare_store_not_main(
        self,
        mock_config: MagicMock,
        mock_compare_store: MagicMock,
        tmp_path: Path,
    ) -> None:
        """_extract_pdf_paragraphs 调用 get_compare_document_store 而非 get_document_store。"""
        mock_config.return_value.compare.pdf_timeout_s = 60

        md_path = tmp_path / "result.md"
        md_path.write_text("段落一\n\n段落二", encoding="utf-8")
        mock_store = MagicMock()
        mock_store.get_or_convert.return_value = md_path
        mock_compare_store.return_value = mock_store

        result = _extract_pdf_paragraphs(tmp_path / "test.pdf")

        mock_compare_store.assert_called_once()
        mock_store.get_or_convert.assert_called_once()
        assert len(result) >= 1
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_service.py::TestExtractPdfUsesCompareStore -v
```
Expected: FAIL — `get_compare_document_store` 不在 `govdoc.compare.service` 的导入中

- [ ] **Step 3: 实现——修改 _extract_pdf_paragraphs**

`govdoc/compare/service.py` 第 204-220 行，修改 import 和 store 获取：

```python
def _extract_pdf_paragraphs(path: Path) -> list[str]:
    """通过对比专用 DocumentStore 把 PDF 转换为 Markdown 段落。"""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

    from govdoc.runtime import get_compare_document_store, get_config

    timeout = get_config().compare.pdf_timeout_s
    store = get_compare_document_store()

    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            prepared_md = pool.submit(store.get_or_convert, path).result(timeout=timeout)
        except FuturesTimeoutError:
            raise RuntimeError(f"PDF 转换超时（{timeout}s）: {path.name}")

    markdown = prepared_md.read_text(encoding="utf-8")
    return extract_markdown_paragraphs(markdown)
```

变更说明：
- 第 208 行：`get_document_store` → `get_compare_document_store`
- 第 211 行：`get_document_store()` → `get_compare_document_store()`
- 其余逻辑（超时、ThreadPoolExecutor）不变

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_service.py::TestExtractPdfUsesCompareStore -v
```
Expected: 1 passed

- [ ] **Step 5: 运行全部单元测试确认无回归**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v
```
Expected: 全部 PASSED

- [ ] **Step 6: 提交**

```bash
git add govdoc/compare/service.py tests/unit/test_compare_service.py
git commit -m "feat(compare): switch PDF conversion to MinerU via compare DocumentStore"
```

---

### Task 5: 双 Store 缓存隔离测试

**Files:**
- Modify: `tests/unit/test_document_store.py`

- [ ] **Step 1: 写测试**

在 `tests/unit/test_document_store.py` 末尾追加：

```python
class TestDualStoreIsolation:
    """验证两个不同 ocr_backend 的 DocumentStore 缓存互不干扰。"""

    @patch("govdoc.storage.files._scrivai_to_markdown")
    def test_same_file_different_backends_cached_independently(
        self, mock_to_md, tmp_path: Path
    ) -> None:
        """相同文件内容在两个 store 各自独立缓存，互不复用。"""
        root_a = tmp_path / "store_a"
        root_b = tmp_path / "store_b"
        store_a = DocumentStore(root_a, ocr_backend="glm")
        store_b = DocumentStore(root_b, ocr_backend="mineru")

        raw_file = tmp_path / "test.pdf"
        raw_file.write_bytes(b"identical pdf content")

        mock_to_md.return_value = "# GLM result"
        result_a = store_a.get_or_convert(raw_file)

        mock_to_md.return_value = "# MinerU result"
        result_b = store_b.get_or_convert(raw_file)

        assert mock_to_md.call_count == 2
        assert result_a.read_text(encoding="utf-8") == "# GLM result"
        assert result_b.read_text(encoding="utf-8") == "# MinerU result"
        assert result_a.parent != result_b.parent
```

- [ ] **Step 2: 运行测试确认通过**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_document_store.py::TestDualStoreIsolation -v
```
Expected: 1 passed

- [ ] **Step 3: 运行全部单元测试做最终回归检查**

Run:
```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v
```
Expected: 全部 PASSED

- [ ] **Step 4: 提交**

```bash
git add tests/unit/test_document_store.py
git commit -m "test(storage): verify dual DocumentStore cache isolation"
```
