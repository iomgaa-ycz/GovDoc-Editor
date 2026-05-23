# PR #27 合并前修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 PR #27 (feat(compare): N 文件对比 + PDF 支持) 审核发现的所有 Bug 和风格/规范问题，使其可安全合并到 master。

**Architecture:** PR #27 把 `govdoc/compare/` 从 `first/second` 二元结构重构为 `files[]` N 文件模型。本修复计划在 PR 分支上执行 7 项修正：清理死代码、实装 `pdf_timeout_s`、还原 vite 端口、移除 CLAUDE.md 变更、迁移设计文档、解除下载按钮硬编码、清理未使用函数。

**Tech Stack:** Python 3.11 / FastAPI / Pydantic v2 / Vite + React + TypeScript / concurrent.futures

**执行流程：** PR 来自 fork（Bepr4），无法推送到源分支。流程为：拉 PR 代码到本地分支 → 在本地执行所有修复 → squash merge 到 master → 推送并关闭原 PR。

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `govdoc/compare/compare.py` | MODIFY | 删除 `ExactMatch`、`find_exact_matches`、`split_sentences` 死代码 |
| `govdoc/compare/extractor.py` | MODIFY | 删除未使用的 `extract_paragraphs_from_path` |
| `govdoc/compare/service.py` | MODIFY | `_extract_pdf_paragraphs` 增加超时机制 |
| `tests/unit/test_compare_service.py` | MODIFY | 更新测试引用：旧 API → N 文件 API |
| `frontend/src/pages/DocComparePage.tsx` | MODIFY | 下载按钮移除 `.slice(0, 3)` 限制 |
| `frontend/vite.config.ts` | MODIFY | 代理端口还原 8002 → 8000 |
| `CLAUDE.md` | REVERT | 还原此文件所有变更（不合并） |
| `docs/compare-n-file-pdf-redesign.md` | DELETE+CREATE | 移动到 `research-wiki/designs/compare-nfile-pdf.md` |

---

### Task 0: 拉取 PR 分支到本地

**Files:** 无

- [ ] **Step 1: 拉取 PR #27 代码到本地分支**

```bash
git fetch origin pull/27/head:pr27-fixup
git checkout pr27-fixup
```

- [ ] **Step 2: 验证分支内容**

Run: `git log --oneline -3`
Expected: 顶部应为 `feat(compare): N 文件对比 + PDF 支持 + 重构设计文档`

---

### Task 1: 还原 CLAUDE.md 变更

**Files:**
- Revert: `CLAUDE.md`

- [ ] **Step 1: 还原 CLAUDE.md 到 master 版本**

```bash
git checkout master -- CLAUDE.md
```

- [ ] **Step 2: 验证还原成功**

Run: `git diff master -- CLAUDE.md`
Expected: 无输出（与 master 完全一致）

- [ ] **Step 3: 暂存**

```bash
git add CLAUDE.md
```

---

### Task 2: 还原 vite.config.ts 代理端口

**Files:**
- Modify: `frontend/vite.config.ts:14-15`

- [ ] **Step 1: 还原代理端口为 8000**

```typescript
// frontend/vite.config.ts 第 14-15 行
// 将：
      "/api": "http://localhost:8002",
      "/healthz": "http://localhost:8002",
// 改为：
      "/api": "http://localhost:8000",
      "/healthz": "http://localhost:8000",
```

- [ ] **Step 2: 验证变更**

Run: `grep -n "localhost:80" frontend/vite.config.ts`
Expected: 两行都应为 `localhost:8000`

- [ ] **Step 3: 暂存**

```bash
git add frontend/vite.config.ts
```

---

### Task 3: 清理 compare.py 死代码

PR 中 `service.py` 已全部改用 `NFile*` 系列函数。旧的 `ExactMatch`、`find_exact_matches`、`split_sentences` 不再被任何生产代码引用。`TextSegment`、`trim_match`、`find_common_segments` 仍被 `find_nfile_common_segments` 内部使用，必须保留。

**Files:**
- Modify: `govdoc/compare/compare.py`
- Modify: `tests/unit/test_compare_service.py`

- [ ] **Step 1: 从 compare.py 删除死代码**

删除以下三段：

1. `ExactMatch` 类（约第 20-27 行）：

```python
@dataclass(frozen=True)
class ExactMatch:
    """完全相同文本及其在两份文档中的位置。"""

    text: str
    first_positions: list[int]
    second_positions: list[int]
```

2. `split_sentences` 函数（约第 65-79 行）：

```python
def split_sentences(paragraphs: list[str]) -> list[str]:
    """按中英文常见句末符号拆分段落为句子。"""
    sentences: list[str] = []

    for paragraph in paragraphs:
        normalized = normalize_text(paragraph)
        if not normalized:
            continue

        for part in SENTENCE_SPLIT_RE.split(normalized):
            sentence = normalize_text(part)
            if sentence:
                sentences.append(sentence)

    return sentences
```

3. `find_exact_matches` 函数（约第 82-107 行）：

```python
def find_exact_matches(first_items: list[str], second_items: list[str]) -> list[ExactMatch]:
    """查找两组文本项中完全相同的内容。"""
    first_positions: dict[str, list[int]] = defaultdict(list)
    second_positions: dict[str, list[int]] = defaultdict(list)

    for index, text in enumerate(first_items, start=1):
        first_positions[text].append(index)

    for index, text in enumerate(second_items, start=1):
        second_positions[text].append(index)

    seen: set[str] = set()
    matches: list[ExactMatch] = []

    for text in first_items:
        if text in second_positions and text not in seen:
            seen.add(text)
            matches.append(
                ExactMatch(
                    text=text,
                    first_positions=first_positions[text],
                    second_positions=second_positions[text],
                )
            )

    return matches
```

同时删除 `SENTENCE_SPLIT_RE`（约第 17 行），因为它仅被 `split_sentences` 使用：

```python
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])\s*|(?<=[.])\s+(?=[A-Z0-9\"\'])")
```

删除后，`re` 模块不再被本文件使用，也删除 `import re`。

- [ ] **Step 2: 更新测试 — 替换旧 API 测试为 N 文件 API 测试**

在 `tests/unit/test_compare_service.py` 中：

**2a.** 修改 import 块（约第 11-16 行），将：

```python
from govdoc.compare.compare import (
    find_common_segments,
    find_exact_matches,
    find_nfile_common_segments,
    find_nfile_exact_matches,
)
```

改为：

```python
from govdoc.compare.compare import (
    find_common_segments,
    find_nfile_common_segments,
    find_nfile_exact_matches,
)
```

**2b.** 替换 `test_match_algorithms_find_exact_items_and_segments` 测试函数（约第 32-47 行），将：

```python
def test_match_algorithms_find_exact_items_and_segments() -> None:
    """底层算法应识别完全相同文本和连续公共片段。"""
    exact_matches = find_exact_matches(
        ["甲", "乙", "甲", "丙"],
        ["乙", "甲", "丁"],
    )
    segments = find_common_segments(
        "开头这里有连续公共片段 ABCDEFGHIJ 结尾",
        "另一份也有连续公共片段 ABCDEFGHIJ 收尾",
        min_length=12,
    )

    assert [match.text for match in exact_matches] == ["甲", "乙"]
    assert exact_matches[0].first_positions == [1, 3]
    assert exact_matches[0].second_positions == [2]
    assert any("连续公共片段 ABCDEFGHIJ" in segment.text for segment in segments)
```

改为：

```python
def test_match_algorithms_find_nfile_exact_and_segments() -> None:
    """底层算法应识别 N 文件间完全相同文本和连续公共片段。"""
    exact_matches = find_nfile_exact_matches(
        {0: ["甲", "乙", "甲", "丙"], 1: ["乙", "甲", "丁"]},
    )
    segments = find_common_segments(
        "开头这里有连续公共片段 ABCDEFGHIJ 结尾",
        "另一份也有连续公共片段 ABCDEFGHIJ 收尾",
        min_length=12,
    )

    by_text = {match.text: match for match in exact_matches}
    assert "甲" in by_text
    assert "乙" in by_text
    assert by_text["甲"].file_positions == {0: [1, 3], 1: [2]}
    assert by_text["乙"].file_positions == {0: [2], 1: [1]}
    assert any("连续公共片段 ABCDEFGHIJ" in segment.text for segment in segments)
```

- [ ] **Step 3: 运行测试验证**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_service.py tests/unit/test_compare_extractor.py -v`
Expected: 全部 PASS（20 个用例；其中 `test_match_algorithms_find_nfile_exact_and_segments` 替代旧测试）

- [ ] **Step 4: 验证无残留引用**

Run: `grep -rn "ExactMatch\|find_exact_matches\|split_sentences\|SENTENCE_SPLIT_RE" --include='*.py' govdoc/ tests/ | grep -v __pycache__`
Expected: 无输出

- [ ] **Step 5: 暂存**

```bash
git add govdoc/compare/compare.py tests/unit/test_compare_service.py
```

---

### Task 4: 清理 extractor.py 死代码

`extract_paragraphs_from_path` 在 PR 中新增但未被任何代码引用。

**Files:**
- Modify: `govdoc/compare/extractor.py`

- [ ] **Step 1: 删除 `extract_paragraphs_from_path` 函数**

删除约第 133-139 行：

```python
def extract_paragraphs_from_path(path: str | Path) -> list[str]:
    """从无需 OCR 的本地文件直接提取段落。"""
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        return extract_docx_paragraphs(file_path)
    raise ValueError(f"不支持直接提取的文件格式: {suffix}")
```

- [ ] **Step 2: 验证无残留引用**

Run: `grep -rn "extract_paragraphs_from_path" --include='*.py' govdoc/ tests/ | grep -v __pycache__`
Expected: 无输出

- [ ] **Step 3: 暂存**

```bash
git add govdoc/compare/extractor.py
```

---

### Task 5: 实装 pdf_timeout_s 超时机制

`CompareConfig.pdf_timeout_s` 已定义但从未使用。`_extract_pdf_paragraphs` 调用 `get_document_store().get_or_convert(path)` 时无超时保护，大 PDF 的 OCR 可能无限阻塞同步请求线程。

**设计：** `get_or_convert` 不接受 timeout 参数（且不可修改 scrivai），用 `concurrent.futures.ThreadPoolExecutor` 在线程中执行并设置超时。

**Files:**
- Modify: `govdoc/compare/service.py:202-208`

- [ ] **Step 1: 修改 `_extract_pdf_paragraphs` 增加超时**

将 `govdoc/compare/service.py` 中的 `_extract_pdf_paragraphs`（约第 202-208 行）从：

```python
def _extract_pdf_paragraphs(path: Path) -> list[str]:
    """通过 DocumentStore 缓存路径把 PDF 转换为 Markdown 段落。"""
    from govdoc.runtime import get_document_store

    prepared_md = get_document_store().get_or_convert(path)
    markdown = prepared_md.read_text(encoding="utf-8")
    return extract_markdown_paragraphs(markdown)
```

改为：

```python
def _extract_pdf_paragraphs(path: Path) -> list[str]:
    """通过 DocumentStore 缓存路径把 PDF 转换为 Markdown 段落。"""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

    from govdoc.runtime import get_config, get_document_store

    timeout = get_config().compare.pdf_timeout_s
    store = get_document_store()

    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            prepared_md = pool.submit(store.get_or_convert, path).result(timeout=timeout)
        except FuturesTimeoutError:
            raise RuntimeError(f"PDF 转换超时（{timeout}s）: {path.name}")

    markdown = prepared_md.read_text(encoding="utf-8")
    return extract_markdown_paragraphs(markdown)
```

- [ ] **Step 2: 运行测试验证**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_service.py::test_compare_pdf_uses_document_store_conversion -v`
Expected: PASS（FakeStore 秒返回，不会触发超时）

- [ ] **Step 3: 暂存**

```bash
git add govdoc/compare/service.py
```

---

### Task 6: 下载按钮移除硬编码限制

`DocComparePage.tsx` 第 190 行 `.slice(0, 3)` 只展示前 3 份文件的下载按钮，与"不写死上限"的设计理念矛盾。

**Files:**
- Modify: `frontend/src/pages/DocComparePage.tsx:190`

- [ ] **Step 1: 移除 `.slice(0, 3)` 限制**

将第 190 行从：

```tsx
          {result.documents.files.slice(0, 3).map((doc) => {
```

改为：

```tsx
          {result.documents.files.map((doc) => {
```

- [ ] **Step 2: 验证变更**

Run: `grep -n "slice" frontend/src/pages/DocComparePage.tsx`
Expected: 无匹配行（该文件中不应有 slice 调用）

- [ ] **Step 3: 暂存**

```bash
git add frontend/src/pages/DocComparePage.tsx
```

---

### Task 7: 迁移设计文档到 research-wiki

`docs/compare-n-file-pdf-redesign.md` 应按项目规范放在 `research-wiki/designs/`。

**Files:**
- Delete: `docs/compare-n-file-pdf-redesign.md`
- Create: `research-wiki/designs/compare-nfile-pdf.md`

- [ ] **Step 1: 移动文件**

```bash
mv docs/compare-n-file-pdf-redesign.md research-wiki/designs/compare-nfile-pdf.md
```

- [ ] **Step 2: 注册到 research-wiki**

```bash
source activate govdoc-auditor-v3 && python .claude/tools/research_wiki.py add_entity research-wiki/ --type design --id compare-nfile-pdf --title "N 文件对比 + PDF 支持设计"
```

如果 `add_entity` 报 entity 已存在（因为文件已在目标位置），忽略错误，直接继续。

- [ ] **Step 3: 重建索引**

```bash
source activate govdoc-auditor-v3 && python .claude/tools/research_wiki.py rebuild_index research-wiki/
```

- [ ] **Step 4: 暂存**

```bash
git add docs/compare-n-file-pdf-redesign.md research-wiki/designs/compare-nfile-pdf.md research-wiki/index.md
```

---

### Task 8: 最终验证与提交修复

- [ ] **Step 1: 运行完整单元测试**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_service.py tests/unit/test_compare_extractor.py -v`
Expected: 全部 PASS

- [ ] **Step 2: Ruff 检查**

Run: `source activate govdoc-auditor-v3 && ruff check govdoc/compare/ govdoc/schemas/compare.py govdoc/api/routes/compare.py govdoc/config.py`
Expected: `All checks passed!` 或 `No issues found`

- [ ] **Step 3: 在修复分支上提交所有修复**

```bash
git add -A
git commit -m "fix(compare): PR#27 审核修复 — 清理死代码、实装超时、还原端口、迁移文档"
```

---

### Task 9: Squash 合并到 master 并关闭 PR

- [ ] **Step 1: 切回 master**

```bash
git checkout master
```

- [ ] **Step 2: Squash merge 修复后的 PR 分支**

```bash
git merge --squash pr27-fixup
```

- [ ] **Step 3: 提交合并**

```bash
git commit -m "feat(compare): N 文件对比 + PDF 支持（PR #27 审核修复后合并）"
```

- [ ] **Step 4: 验证 master 上测试通过**

Run: `source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_service.py tests/unit/test_compare_extractor.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 推送 master**

```bash
git push origin master
```

- [ ] **Step 6: 关闭原 PR 并清理本地分支**

```bash
gh pr close 27 --comment "代码已审核修复后合并到 master（squash merge）。修复项：清理死代码、实装 pdf_timeout_s、还原 vite 端口 8000、迁移设计文档到 research-wiki、移除下载按钮硬编码限制。"
git branch -D pr27-fixup
```
