# E2E 测试第二轮修复设计

> 日期: 2026-05-23
> 状态: 设计完成

## 目标

修复全量 E2E 测试运行中发现的 6 个失败，包含 1 个对比算法 bug、1 个 GPU 资源问题、4 个测试代码问题。

## 一、对比算法句子级去重修复（bug fix）

### 问题

`_build_nfile_sentence_matches()` 独立运行，不知道段落匹配的存在。当段落只含一个句子时（如 "投标人应具有独立承担民事责任的能力。"），同一文本被段落+句子各计一次，导致 matchCount 虚高。

### 修复方案（方案 A：收集时过滤）

**修改文件**：`govdoc/compare/service.py`，3 处改动：

1. `_build_nfile_sentence_matches` 签名加参数：
```python
def _build_nfile_sentence_matches(
    documents: list[DocumentModel],
    paragraph_ranges_by_file: dict[int, list[tuple[int, int]]] | None = None,
) -> list[MatchRecord]:
```

2. 遍历句子时过滤：
```python
for doc in documents:
    for order, sentence in enumerate(_iter_sentence_occurrences(doc), start=1):
        if paragraph_ranges_by_file:
            if _is_covered_by_ranges(
                document=doc, start=sentence.start, end=sentence.end,
                ranges=paragraph_ranges_by_file.get(doc.file_index, []),
            ):
                continue
        sentence_lookup[sentence.text][doc.file_index].append(sentence)
```

3. 调用处变更（约第 740-748 行）：
```python
paragraph_matches = _build_nfile_block_matches(documents)
paragraph_ranges = _build_exact_ranges_by_file(paragraph_matches)
sentence_matches = _build_nfile_sentence_matches(
    documents, paragraph_ranges_by_file=paragraph_ranges,
)
segment_matches = _build_nfile_segment_matches(
    documents=documents, min_segment_length=min_segment_length,
    exact_matches=paragraph_matches + sentence_matches,
)
```

### 单元测试

在 `tests/unit/test_compare_service.py` 增加：
```python
def test_sentence_dedup_against_paragraph(tmp_path):
    """段落内的单句子不应被重复计入 sentenceCount。"""
    _write_docx(tmp_path / "a.docx", ["唯一共同段落。"])
    _write_docx(tmp_path / "b.docx", ["唯一共同段落。"])
    payload = create_compare_bundle(
        files=[(tmp_path/"a.docx","a.docx"), (tmp_path/"b.docx","b.docx")],
        output_root=tmp_path / "out",
    )
    assert payload.summary.common_paragraph_count == 1
    assert payload.summary.common_sentence_count == 0
```

## 二、GPU 切换

4090-server 的 GPU 0 被 3 个进程挤满（48.4/49.1 GB），其中 PID 868644 是 zombie 进程锁死 24.8 GB。

**操作**：
1. SSH 到 100.83.164.94
2. 修改 govdoc testing 服务启动参数 `CUDA_VISIBLE_DEVICES=7`
3. 重启 uvicorn

## 三、4 个 E2E 测试修复

### test-09：编辑后等待改为 waitFor

将 `waitForTimeout(1000)` 改为 `page.getByText(originalTitle + ' [E2E]').waitFor({ timeout: 5000 })`

### test-12：遍历找有内容的运行

不取默认运行，遍历 Select 选项，找编辑器有内容（textContent.length > 10）的运行

### test-13：重写文件添加/移除

利用 `setInputFiles` 的替换语义：
- `setInputFiles([A, B, C])` → 3 个卡片
- `setInputFiles([A, C])` → 2 个卡片（移除了 B）

### test-15：直接进 audit-results 找 completed 运行

不从 Dashboard 跳转，直接 `goto('/audit-results')`，遍历 Select 找有 completed 审核点的运行

## 四、test-14 真值校准

算法修复后本地重新运行 7 个 fixture 用例，用实际输出更新断言。

## 五、实施顺序

```
1. GPU 切换                    ← 无代码依赖
2. 算法 bug 修复 + 单元测试    ← 核心修复
3. 重新计算 fixture 真值       ← 依赖 2
4. 更新 test-14 断言           ← 依赖 3
5. 修复 test-09/12/13/15       ← 独立
6. 部署到 testing               ← 依赖 2-5
7. 运行全量测试                 ← 依赖 6
```
