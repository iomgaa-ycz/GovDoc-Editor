# 文档对比功能重构计划：N 文件 + PDF 支持

> 编写日期：2026-05-19  
> 分支：`feat/compare-improvement`  
> 目标：把当前“两份 DOCX 对比”重构为“任意数量文件对比 + PDF 参与查重”。

## 1. 背景与目标

当前 `govdoc/compare/` 的文档对比功能存在两个核心限制：

1. 只支持两份文件：后端 schema、service、API、前端 UI 都围绕 `first` / `second` 二元结构设计。
2. 只支持 DOCX：`govdoc/compare/extractor.py` 只提供 DOCX 提取能力，API 也只允许 `.docx`。

新需求：

1. 支持 PDF 文件参与对比。
2. 支持 N 份文件上传，N >= 2，不再把业务能力固定在“两份文件”。
3. 在所有文件之间查重：任意两个或多个文件中出现相同内容，都应返回。

示例语义：

- 上传 1、2、3、4、5 五份文件。
- 1 和 2 有相同段落，要查出来。
- 1 和 4 有相同句子，要查出来。
- 2、3、5 有相同公共片段，要合并成一条涉及 2、3、5 的匹配记录。
- 同一内容在同一文件内出现多次，也要保留所有出现位置。

## 2. 关键设计决策

### 2.1 “无限多文件”的工程定义

本次重构不再在数据模型、API 字段、前端 UI 中写死 `2` 或固定 `20` 这类业务上限。

但“无限多”在运行时仍受 CPU、内存、请求超时、OCR 服务耗时影响。因此本计划采用：

- **数据模型无固定上限**：schema、service、前端类型统一使用 `files[]`。
- **前端无固定槽位上限**：用户可以持续添加文件或一次选择多个文件。
- **后端不写死 20**：如需保护部署环境，通过配置项控制，而不是把产品能力写死在代码里。
- **MVP 仍为同步接口**：当前 compare 接口是同步返回结果。本次先保持同步，后续如需支持超大批量文件，再升级为异步任务 + 轮询进度。

建议新增配置：

```python
class CompareConfig(BaseModel):
    """文档对比运行保护配置。"""

    max_files: int | None = None       # None 表示不限制文件数量
    min_segment_length: int = 16
    pdf_timeout_s: int = 300


class GovDocConfig(BaseModel):
    ...
    compare: CompareConfig = Field(default_factory=CompareConfig)
```

`govdoc.yaml`：

```yaml
compare:
  max_files: null
  min_segment_length: 16
  pdf_timeout_s: 300
```

如果生产环境需要限制，例如最多 50 份文件，应改配置，不在业务逻辑里硬编码。

### 2.2 PDF 设计原则

PDF 转换不能在 compare 模块里裸调：

```python
to_markdown(str(path))
```

原因：

- 项目现有 `DocumentStore` 已经支持 `.pdf`，并接入 `ocr_base_url`。
- `scrivai.to_markdown` 依赖 MonkeyOCR，OCR 地址来自配置。
- 现有 `DocumentStore.get_or_convert()` 有 SHA256 缓存，避免同一文件重复 OCR。
- 裸调会绕过缓存、配置、空结果校验和已有测试约束。

因此 PDF 路径设计为：

```text
上传 PDF
  -> compare service 保存到 review/uploads/
  -> DocumentStore.get_or_convert(stored_pdf)
  -> scrivai.to_markdown(stored_pdf, ocr_base_url=config.app.ocr_base_url)
  -> prepared/*.md 缓存
  -> extractor.extract_markdown_paragraphs(markdown_text)
  -> DocumentModel
  -> N 文件查重
```

DOCX 路径仍保留当前 `extract_docx_paragraphs()`，因为现有 XML 提取器稳定、轻量，并且对段落和表格顺序已有测试覆盖。

### 2.3 API 契约

上传字段统一改为重复字段 `files`：

```text
POST /api/v1/compare
multipart/form-data:
  files: file1.docx
  files: file2.pdf
  files: file3.docx
```

不再接收 `first_file` / `second_file`。这是 breaking change，需要同步修改所有调用方和测试。

下载接口改为按 `file_index` 下载：

```text
GET /api/v1/compare/{review_id}/download/{file_index}
```

`file_index` 从 0 开始，与用户上传顺序一致。

### 2.4 匹配结果语义

每条匹配记录表示“一段文本在两个或多个文件中出现”。

不再使用：

```python
first_occurrences
second_occurrences
first_count
second_count
```

改为：

```python
file_indices: list[int]
occurrences: dict[str, list[CompareOccurrence]]
per_file_counts: dict[str, int]
file_count: int
```

其中 `occurrences["2"]` 表示该匹配在 `file_index == 2` 的文件中所有出现位置。

## 3. 涉及文件清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `govdoc/config.py` | 修改 | 新增 `CompareConfig`，提供运行保护配置 |
| `govdoc.yaml` | 修改 | 新增 `compare` 配置段 |
| `govdoc/compare/extractor.py` | 修改 | 新增 Markdown 段落提取；保留 DOCX 提取 |
| `govdoc/compare/compare.py` | 修改 | 新增 N 文件精确匹配和公共片段聚合函数 |
| `govdoc/compare/service.py` | 重写 | 核心编排从 `first/second` 改为 `files[]` |
| `govdoc/schemas/compare.py` | 重写 | 响应 schema 改为 N 文件模型 |
| `govdoc/api/routes/compare.py` | 修改 | 接收 `files[]`，支持 `.docx` + `.pdf` |
| `govdoc/compare/__init__.py` | 修改 | 更新导出函数 |
| `govdoc/harness/api_eval.py` | 修改 | L2 API 评估改为 `files` 字段 |
| `frontend/src/api/compare.ts` | 重写 | 类型定义 + API 调用适配 N 文件 |
| `frontend/src/pages/DocComparePage.tsx` | 重写 | 上传和结果展示改为 N 文件 |
| `frontend/e2e/test-03-doc-compare.js` | 修改 | 前端 E2E 改为多文件上传 |
| `tests/unit/test_compare_extractor.py` | 修改 | 新增 Markdown/PDF 相关单测 |
| `tests/unit/test_compare_service.py` | 修改 | 新增 N 文件服务层测试 |
| `tests/e2e/test_04_compare.py` | 修改 | 后端 E2E 改为 `files[]` |
| `docs/e2e-test-plan.md` | 修改 | API 契约说明同步更新 |

## 4. 后端 Schema 设计

文件：`govdoc/schemas/compare.py`

### 4.1 新模型

```python
class CompareFileMeta(CompareModel):
    """单个参与对比文件的元信息。"""

    file_index: int
    name: str
    suffix: str
    paragraph_count: int
    block_count: int


class CompareSummary(CompareModel):
    """N 文件对比摘要。"""

    file_count: int
    files: list[CompareFileMeta]
    common_paragraph_count: int
    common_sentence_count: int
    common_segment_count: int
    match_count: int
    min_segment_length: int


class CompareOccurrenceSegment(CompareModel):
    """匹配范围落在某个段落块内的一段。"""

    file_index: int
    block_id: str
    block_index: int
    start: int
    end: int


class CompareOccurrence(CompareModel):
    """某个匹配在某个文件中的一次出现。"""

    file_index: int
    start: int
    end: int
    segments: list[CompareOccurrenceSegment]


class CompareMatch(CompareModel):
    """一条跨文件匹配记录。"""

    id: str
    category: CompareCategoryId
    label: str
    color: str
    text: str
    length: int
    file_indices: list[int]
    occurrences: dict[str, list[CompareOccurrence]]
    per_file_counts: dict[str, int]
    file_count: int
    occurrence_count: int


class CompareDocument(CompareModel):
    """前端渲染单个文件所需的段落块结构。"""

    file_index: int
    name: str
    suffix: str
    block_count: int
    blocks: list[CompareDocumentBlock]


class CompareDocuments(CompareModel):
    """所有参与对比的文件。"""

    files: list[CompareDocument]


class CompareDownloads(CompareModel):
    """每个文件的高亮 DOCX 下载链接。"""

    files: dict[str, str]


class CompareArtifacts(CompareModel):
    """服务端生成物信息。"""

    review_dir: str
    download_names: dict[str, str]


class CompareResponse(CompareModel):
    review_id: str
    summary: CompareSummary
    documents: CompareDocuments
    matches: list[CompareMatch]
    categories: list[CompareCategory]
    downloads: CompareDownloads
    artifacts: CompareArtifacts
```

### 4.2 兼容性决策

本项目 MVP 规则为“不考虑向后兼容，直接修改原文件”。因此：

- 删除响应中的 `documents.first` / `documents.second`。
- 删除响应中的 `downloads.first` / `downloads.second`。
- 删除 `CompareMatch.firstOccurrences` / `secondOccurrences`。
- 前端、测试、harness 同步更新。

## 5. 提取层设计

文件：`govdoc/compare/extractor.py`

### 5.1 保留 DOCX 提取

现有函数继续保留：

- `normalize_text(text)`
- `extract_docx_paragraphs(path)`
- `extract_docx_full_text(path)`

DOCX 仍走当前 WordprocessingML 解析路径。

### 5.2 新增 Markdown 段落提取

PDF 经 Scrivai/MonkeyOCR 转换后的结果是 Markdown，因此新增纯函数：

```python
def extract_markdown_paragraphs(markdown_text: str) -> list[str]:
    """从 Markdown 文本中提取可参与对比的段落。

    规则：
    1. 按空行切分块。
    2. 块内多行合并为一段，避免 OCR 换行导致同一段被拆碎。
    3. 使用 normalize_text 统一空白字符。
    4. 丢弃空段落。
    """
```

实现注意：

- 不要做复杂 Markdown AST 解析，MVP 只需要稳定文本块。
- 表格 Markdown 可以先按行合并为一个块，后续如对表格查重要求更高再细化。
- 不要删除中文标点。
- 不要对文本做过度归一化，否则会影响精确匹配可信度。

### 5.3 统一提取入口

建议新增：

```python
def extract_paragraphs_from_path(path: str | Path) -> list[str]:
    """从无需 OCR 的本地文件直接提取段落。

    当前只处理 .docx。
    PDF 转换需要配置和缓存，由 service 层通过 DocumentStore 处理。
    """
```

不要在 extractor 里直接读取 `govdoc.yaml` 或调用 runtime，避免提取层和运行时装配耦合。

PDF 的实际流程放在 service 层：

```python
if suffix == ".pdf":
    prepared_md = get_document_store().get_or_convert(stored_path)
    paragraphs = extract_markdown_paragraphs(prepared_md.read_text(encoding="utf-8"))
```

## 6. 匹配算法设计

文件：`govdoc/compare/compare.py`

现有双文件函数保留，方便复用和回归测试：

- `find_exact_matches(first_items, second_items)`
- `find_common_segments(first_text, second_text, min_length)`
- `split_sentences(paragraphs)`
- `trim_match(...)`

新增 N 文件函数。

### 6.1 精确文本匹配

段落和句子的精确匹配都可以按文本聚合：

```python
@dataclass(frozen=True)
class NFileExactMatch:
    text: str
    file_positions: dict[int, list[int]]


def find_nfile_exact_matches(
    all_items: dict[int, list[str]],
) -> list[NFileExactMatch]:
    """查找出现在两个或多个文件中的完全相同文本。"""
```

算法：

1. 建立 `text -> file_index -> positions[]`。
2. 只保留 `len(file_positions) >= 2` 的文本。
3. 同一文本在同一文件出现多次时，保留所有 positions。
4. 输出顺序按首次出现的文件顺序和段落顺序稳定排序。

注意：

- 段落匹配的 position 是 block index。
- 句子匹配不能只靠 position 回查 block，service 层要维护 `text -> file_index -> SentenceOccurrence[]`。

### 6.2 公共片段匹配

不能使用 `dict[int, tuple[int, int]]`，因为同一片段可能在同一文件出现多次，会被覆盖。

应使用：

```python
@dataclass(frozen=True)
class TextRange:
    start: int
    end: int


@dataclass(frozen=True)
class NFileSegmentMatch:
    text: str
    file_ranges: dict[int, list[TextRange]]
```

新增函数：

```python
def find_nfile_common_segments(
    all_texts: dict[int, str],
    min_length: int = 16,
) -> list[NFileSegmentMatch]:
    """在 N 个文件之间查找连续公共片段。"""
```

算法：

1. 对所有文件对 `(i, j)` 执行现有 `find_common_segments()`。
2. 对每个 `TextSegment`，按 `segment.text` 聚合。
3. 发现某个片段文本后，再扫描所有文件，补齐该文本在每个文件中的全部出现位置。
4. 对每个文件保存 `list[TextRange]`，不能覆盖。
5. 对 `(file_index, start, end)` 做去重。
6. 只保留出现在两个或多个文件中的片段。
7. 对结果按长度降序、涉及文件数降序、文本顺序排序。

这里用 `set[tuple[int, int]]` 只去重“同一文件同一位置”的重复记录；如果同一文本在同一文件的不同位置出现两次，会得到两个不同 `(start, end)`，不会被覆盖。

伪代码：

```python
segment_map: dict[str, dict[int, set[tuple[int, int]]]] = defaultdict(lambda: defaultdict(set))

for fi, fj in combinations(file_indices, 2):
    for seg in find_common_segments(all_texts[fi], all_texts[fj], min_length):
        segment_map[seg.text][fi].add((seg.first_start, seg.first_end))
        segment_map[seg.text][fj].add((seg.second_start, seg.second_end))

results = []
for text, per_file_ranges in segment_map.items():
    for file_index, full_text in all_texts.items():
        # 补齐同一片段文本在所有文件中的全部出现位置。
        for start, end in find_all_ranges(full_text, text):
            per_file_ranges[file_index].add((start, end))

    if len(per_file_ranges) < 2:
        continue
    results.append(
        NFileSegmentMatch(
            text=text,
            file_ranges={
                file_index: [TextRange(start, end) for start, end in sorted(ranges)]
                for file_index, ranges in per_file_ranges.items()
            },
        )
    )
```

### 6.3 片段去重与覆盖规则

段落和句子属于更高优先级匹配。片段匹配需要避免把已经被完整段落/句子覆盖的内容重复显示。

建议规则：

- 先生成段落匹配。
- 再生成句子匹配。
- 最后生成公共片段。
- 如果一个片段 occurrence 在某个文件中被同文件的段落/句子匹配范围完全覆盖，则该 occurrence 可丢弃。
- 如果丢弃后该片段只剩一个文件，整条片段匹配丢弃。
- 如果仍涉及两个或多个文件，保留剩余 occurrence。

这比只用 `(text, first_start, second_start)` 去重更稳。

## 7. 服务层设计

文件：`govdoc/compare/service.py`

这是改动最大的部分。

### 7.1 内部模型

```python
@dataclass(frozen=True)
class TextBlock:
    id: str
    index: int
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class DocumentModel:
    file_index: int
    file_name: str
    suffix: str
    blocks: list[TextBlock]
    full_text: str


@dataclass(frozen=True)
class MatchOccurrence:
    file_index: int
    start: int
    end: int


@dataclass(frozen=True)
class MatchRecord:
    id: str
    category: CompareCategoryId
    text: str
    file_occurrences: dict[int, list[MatchOccurrence]]
```

`TextBlock.id` 格式：

```python
id=f"file-{file_index}-block-{index}"
```

不要再使用 `first-block-1` / `second-block-1`。

### 7.2 入口函数

直接改为 N 文件入口：

```python
def create_compare_bundle(
    files: list[tuple[Path, str]],
    output_root: Path | None = None,
    min_segment_length: int | None = None,
) -> CompareResponse:
    """从多个本地文件路径创建对比 review。"""


def create_compare_bundle_from_bytes(
    files: list[tuple[bytes, str]],
    output_root: Path | None = None,
    min_segment_length: int | None = None,
) -> CompareResponse:
    """从多个上传文件创建对比 review。"""
```

其中 `files` 元素为：

```python
(content_or_path, original_filename)
```

不保留 `first_path` / `second_path` 旧签名。所有调用方同步改造。

### 7.3 上传文件落盘

保存到：

```text
data/storage/compare/{review_id}/uploads/file_{file_index}_{safe_name}
```

要求：

- 保留原始扩展名，PDF 转换依赖扩展名。
- 使用 `_sanitize_filename()` 防路径穿越。
- 如果多个文件同名，通过 `file_index` 前缀区分。

### 7.4 构建 DocumentModel

新增：

```python
def _build_document_model(
    file_index: int,
    file_name: str,
    path: Path,
) -> DocumentModel:
    """把 DOCX/PDF 转换为统一 TextBlock 模型。"""
```

逻辑：

```python
suffix = path.suffix.lower()

if suffix == ".docx":
    paragraphs = extract_docx_paragraphs(path)
elif suffix == ".pdf":
    prepared_md = get_document_store().get_or_convert(path)
    markdown = prepared_md.read_text(encoding="utf-8")
    paragraphs = extract_markdown_paragraphs(markdown)
else:
    raise ValueError(...)
```

注意：

- PDF 转换失败时不要吞错。
- `to_markdown` 返回空内容时应抛出可读错误。
- OCR 不可达时 API 层应转为友好错误。
- `full_text` 仍使用 `"\n".join(block.text for block in blocks)`。
- block 的 `start/end` 必须基于 `full_text` 中的偏移计算。

### 7.5 构建段落匹配

```python
def _build_nfile_block_matches(
    documents: list[DocumentModel],
) -> list[MatchRecord]:
```

流程：

1. `all_items = {doc.file_index: [block.text for block in doc.blocks]}`
2. 调 `find_nfile_exact_matches(all_items)`
3. 通过 block index 构造每个文件的 `MatchOccurrence`
4. 只保留涉及两个或多个文件的匹配

注意不要使用 `documents[file_idx]` 直接索引，建议先建：

```python
documents_by_index = {doc.file_index: doc for doc in documents}
```

### 7.6 构建句子匹配

现有 `_iter_sentence_occurrences(document)` 可以保留并改造为支持 `file_index`。

句子匹配不能只保存 sentence position。应建立：

```python
sentence_lookup: dict[str, dict[int, list[SentenceOccurrence]]]
```

流程：

1. 遍历每个文档，得到 `SentenceOccurrence`。
2. 按 `sentence.text` 聚合到 `sentence_lookup`。
3. 只保留出现在两个或多个文件中的句子。
4. 用 `SentenceOccurrence.start/end` 构造 `MatchOccurrence`。

这样能正确处理：

- 同一句子在同一文件出现多次。
- 句子不等于段落的情况。
- 句子所在 block 的定位。

### 7.7 构建公共片段匹配

```python
def _build_nfile_segment_matches(
    documents: list[DocumentModel],
    min_segment_length: int,
    exact_matches: list[MatchRecord],
) -> list[MatchRecord]:
```

流程：

1. `all_texts = {doc.file_index: doc.full_text}`
2. 调 `find_nfile_common_segments(all_texts, min_segment_length)`
3. 把 `TextRange` 转为 `MatchOccurrence`
4. 根据段落/句子匹配范围过滤被完全覆盖的 occurrence
5. 过滤后仍涉及两个或多个文件才保留

### 7.8 annotation 序列化

原函数：

```python
_build_annotations(document, matches, side)
```

改为：

```python
def _build_annotations(
    document: DocumentModel,
    matches: list[MatchRecord],
) -> tuple[dict[str, list[dict]], dict[str, list[CompareOccurrence]]]:
```

内部逻辑：

```python
occurrences = match.file_occurrences.get(document.file_index, [])
```

`_split_occurrence_by_blocks()` 生成的 `CompareOccurrenceSegment` 要带 `file_index`。

### 7.9 matches 序列化

```python
def _serialize_matches(
    matches: list[MatchRecord],
    match_segments_by_file: dict[int, dict[str, list[CompareOccurrence]]],
) -> list[CompareMatch]:
```

输出：

```python
occurrences = {
    str(file_index): match_segments_by_file[file_index].get(match.id, [])
    for file_index in match.file_occurrences
}
per_file_counts = {
    str(file_index): len(items)
    for file_index, items in occurrences.items()
}
```

排序建议：

1. category priority：paragraph -> sentence -> segment
2. 涉及文件数多的靠前
3. 文本长度长的靠前
4. id 稳定排序

### 7.10 下载文件生成

MVP 不生成高亮 PDF，统一生成高亮 DOCX：

```text
file_0_reviewed.docx
file_1_reviewed.docx
file_2_reviewed.docx
```

对 PDF 来说，高亮 DOCX 是 OCR/Markdown 文本重排后的审阅副本，不是原 PDF 原版式。

前端文案应避免暗示“下载高亮 PDF”，统一称为“下载高亮副本”。

`CompareDownloads.files`：

```json
{
  "0": "/api/v1/compare/{review_id}/download/0",
  "1": "/api/v1/compare/{review_id}/download/1"
}
```

`CompareArtifacts.download_names`：

```json
{
  "0": "招标文件_reviewed.docx",
  "1": "合同_reviewed.docx"
}
```

### 7.11 下载读取

```python
def get_compare_download(
    review_id: str,
    file_index: int,
    output_root: Path | None = None,
) -> CompareDownload:
```

校验：

- `review_id` 仍使用安全正则。
- `file_index >= 0`。
- metadata 中存在该文件。
- 文件存在。

## 8. API 路由设计

文件：`govdoc/api/routes/compare.py`

### 8.1 上传接口

```python
ALLOWED_EXTENSIONS = {".docx", ".pdf"}


@router.post("", response_model=CompareResponse)
async def compare_uploaded_files(
    files: list[UploadFile] = File(...),
) -> CompareResponse:
    """接收 N 份 DOCX/PDF 文件并返回对比结果。"""
```

处理逻辑：

1. `len(files) < 2` 返回 400。
2. 读取 `load_config().compare.max_files`。
3. 如果 `max_files is not None and len(files) > max_files`，返回 413 或 400，说明当前部署限制。
4. 校验扩展名为 `.docx` 或 `.pdf`。
5. 读取 bytes，调用 `create_compare_bundle_from_bytes(files=file_data)`。

错误处理建议：

```python
try:
    return create_compare_bundle_from_bytes(files=file_data)
except BadZipFile as exc:
    raise HTTPException(status_code=400, detail=f"DOCX 文件解析失败: {exc}") from exc
except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
except RuntimeError as exc:
    raise HTTPException(status_code=502, detail=f"文档转换失败: {exc}") from exc
except OSError as exc:
    raise HTTPException(status_code=502, detail=f"文档转换服务不可用: {exc}") from exc
```

### 8.2 下载接口

```python
@router.get("/{review_id}/download/{file_index}")
def download_compare_file(
    review_id: str,
    file_index: int,
) -> FileResponse:
    """下载指定文件的高亮 DOCX 副本。"""
```

下载 media type 仍为：

```python
application/vnd.openxmlformats-officedocument.wordprocessingml.document
```

## 9. 前端 API 设计

文件：`frontend/src/api/compare.ts`

### 9.1 类型定义

TypeScript 类型与后端 camelCase 响应对齐：

```typescript
export interface CompareFileMeta {
  fileIndex: number;
  name: string;
  suffix: string;
  paragraphCount: number;
  blockCount: number;
}

export interface CompareSummary {
  fileCount: number;
  files: CompareFileMeta[];
  commonParagraphCount: number;
  commonSentenceCount: number;
  commonSegmentCount: number;
  matchCount: number;
  minSegmentLength: number;
}

export interface CompareOccurrenceSegment {
  fileIndex: number;
  blockId: string;
  blockIndex: number;
  start: number;
  end: number;
}

export interface CompareOccurrence {
  fileIndex: number;
  start: number;
  end: number;
  segments: CompareOccurrenceSegment[];
}

export interface CompareMatch {
  id: string;
  category: CompareCategoryId;
  label: string;
  color: string;
  text: string;
  length: number;
  fileIndices: number[];
  occurrences: Record<string, CompareOccurrence[]>;
  perFileCounts: Record<string, number>;
  fileCount: number;
  occurrenceCount: number;
}

export interface CompareDocument {
  fileIndex: number;
  name: string;
  suffix: string;
  blockCount: number;
  blocks: CompareDocumentBlock[];
}

export interface CompareResponse {
  reviewId: string;
  summary: CompareSummary;
  documents: {
    files: CompareDocument[];
  };
  matches: CompareMatch[];
  categories: CompareCategory[];
  downloads: {
    files: Record<string, string>;
  };
  artifacts: {
    reviewDir: string;
    downloadNames: Record<string, string>;
  };
}
```

### 9.2 API 调用

```typescript
export function compareFiles(files: File[]): Promise<CompareResponse> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  return request("/api/v1/compare", {
    method: "POST",
    body: form,
  });
}
```

保留 `buildCompareDownloadUrl(path)`。

删除或替换 `compareDocxFiles(firstFile, secondFile)`。

## 10. 前端页面设计

文件：`frontend/src/pages/DocComparePage.tsx`

### 10.1 上传视图

当前页面有两个固定状态：

```typescript
const [firstFile, setFirstFile] = useState<File | null>(null);
const [secondFile, setSecondFile] = useState<File | null>(null);
```

改为：

```typescript
const [files, setFiles] = useState<File[]>([]);
```

建议 UI：

- 使用一个支持 `multiple` 的上传区，接受 `.docx,.pdf`。
- 用户可以一次选择多份，也可以多次追加。
- 已选文件显示为列表。
- 每个文件项可移除。
- 提交按钮要求 `files.length >= 2`。
- 不设置固定最大数量。

可复用现有 `frontend/src/components/FileDropzone.tsx`，因为它已经支持 `multiple`。

### 10.2 结果视图

指标区保持：

- 匹配总数
- 相同段落
- 相同句子
- 公共片段

新增文件数量可显示在摘要附近：

```text
共 N 份文件
```

### 10.3 文件栏布局

不能使用动态 Tailwind class：

```tsx
grid-cols-[repeat(N,1fr)_280px]
```

Tailwind 无法可靠识别运行时生成的任意 class。

建议布局：

```tsx
<div className="grid gap-4" style={{ gridTemplateColumns: "minmax(0, 1fr) 300px" }}>
  <div className="overflow-x-auto">
    <div
      className="grid gap-4"
      style={{
        gridAutoFlow: "column",
        gridAutoColumns: "minmax(360px, 420px)",
      }}
    >
      {result.documents.files.map((doc) => (
        <DocCol key={doc.fileIndex} fileIndex={doc.fileIndex} doc={doc} />
      ))}
    </div>
  </div>
  <MatchList />
</div>
```

这样 N 多时横向滚动，不会把每栏压到不可读。

后续如文件数非常大，可再引入虚拟列表；MVP 不引入新依赖。

### 10.4 DocCol 改造

```typescript
function DocCol({
  doc,
  lookup,
  selectedId,
  onSelect,
}: {
  doc: CompareDocument;
  lookup: Record<string, CompareMatch>;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {}
```

判断某个 segment 是否可见：

```typescript
const visible = seg.matchIds.filter((id) => {
  const match = lookup[id];
  return match && match.fileIndices.includes(doc.fileIndex);
});
```

点击高亮时：

- 设置 `selectedMatchId`。
- 所有包含该 match 的文件栏滚动到对应位置。
- 不包含该 match 的文件栏保持不动。

### 10.5 匹配清单

每条匹配显示：

- 类别标签
- 文本片段
- 涉及文件：`文件 1、文件 3、文件 5`
- 每个文件出现次数：`1:2 处 / 3:1 处 / 5:4 处`

辅助函数：

```typescript
function formatFileIndices(indices: number[]): string {
  return indices.map((i) => `文件 ${i + 1}`).join("、");
}
```

### 10.6 下载按钮

头部下载按钮从两个固定按钮改为循环：

```tsx
{result.documents.files.map((doc) => {
  const path = result.downloads.files[String(doc.fileIndex)];
  const filename = result.artifacts.downloadNames[String(doc.fileIndex)];
  return (
    <a key={doc.fileIndex} href={buildCompareDownloadUrl(path)}>
      <Button variant="secondary" size="sm">
        <Download className="h-4 w-4" />
        {filename ?? `文件 ${doc.fileIndex + 1}`}
      </Button>
    </a>
  );
})}
```

文件很多时可改成下拉菜单，避免头部拥挤。MVP 可先显示前几个 + 下拉。

## 11. Harness 与测试改造

### 11.1 单元测试：提取层

文件：`tests/unit/test_compare_extractor.py`

新增：

- `extract_markdown_paragraphs` 按空行切段。
- OCR 产生的单段多行会合并为一段。
- 空块被过滤。
- DOCX 原有测试保持。

PDF 转换本身不在 extractor 单测里调真实 OCR；service 层通过 mock `DocumentStore.get_or_convert()` 覆盖。

### 11.2 单元测试：算法层

文件：`tests/unit/test_compare_service.py` 或新增 `tests/unit/test_compare_algorithms.py`

新增场景：

1. 3 文件段落匹配：
   - 文件 0 和 1 共享 A。
   - 文件 1 和 2 共享 B。
   - 返回两条不同 match。
2. 5 文件子集匹配：
   - 文件 1、2 共享 X。
   - 文件 1、4 共享 Y。
   - 文件 2、3、5 共享 Z。
   - `file_indices` 分别正确。
3. 同一文件重复出现：
   - 文件 0 中 X 出现两次，文件 1 中 X 出现一次。
   - `per_file_counts["0"] == 2`。
4. 公共片段不覆盖：
   - 同一 segment text 在同一文件多个位置出现。
   - `file_ranges[file_index]` 保留多个 range。

### 11.3 单元测试：服务层

新增：

- `create_compare_bundle(files=[...])` 能生成 N 个 uploads。
- `review.json` 中 `documents.files` 长度正确。
- `downloads.files` 每个 file_index 都有。
- `get_compare_download(review_id, file_index)` 能下载对应文件。
- PDF 文件通过 mock `get_document_store().get_or_convert()` 返回 prepared markdown。
- OCR 空输出或转换失败时抛出异常。

### 11.4 后端 E2E

文件：`tests/e2e/test_04_compare.py`

修改上传：

```python
files=[
    ("files", (file_a.name, f1, DOCX_CONTENT_TYPE)),
    ("files", (file_b.name, f2, DOCX_CONTENT_TYPE)),
    ("files", (file_c.name, f3, DOCX_CONTENT_TYPE)),
]
```

断言：

- `documents.files` 存在且长度 >= 2。
- `matches[*].fileIndices` 存在。
- 下载 `/download/0`、`/download/1` 成功。
- 非支持格式仍返回 400。

如真实 PDF E2E 依赖 MonkeyOCR，可标记 slow 或只在 OCR 可达环境跑。

### 11.5 Harness API 评估

文件：`govdoc/harness/api_eval.py`

当前 `_run_compare_check()` 使用：

```python
files={
    "first_file": (...),
    "second_file": (...),
}
```

改为：

```python
files=[
    ("files", (first_file.name, first_file.read_bytes())),
    ("files", (second_file.name, second_file.read_bytes())),
]
```

如果 real_data 下有 PDF，可加入一个 PDF 文件覆盖混合格式。

### 11.6 前端 E2E

文件：`frontend/e2e/test-03-doc-compare.js`

修改：

- 上传控件可能只剩一个 `input[type=file][multiple]`。
- 使用 `setInputFiles([DOC_A, DOC_B, DOC_C])`。
- 等待 `匹配总数`。
- 验证有多个文件栏。
- 验证匹配清单存在。
- 如有 PDF fixture，再补一份 PDF。

## 12. 性能与风险

### 12.1 精确匹配复杂度

段落和句子精确匹配使用哈希聚合：

```text
O(total_paragraphs_or_sentences)
```

不会因为 N 文件两两组合爆炸。

### 12.2 公共片段复杂度

公共片段仍需要两两 SequenceMatcher：

```text
C(N, 2) = N * (N - 1) / 2
```

文件数很多时会慢。

MVP 策略：

- 不在代码里写死文件上限。
- 通过配置允许部署层设置 `compare.max_files`。
- `min_segment_length` 可配置，默认 16。
- 后续优化方向：
  - 先用段落/句子哈希判断两个文件是否可能相关。
  - 对完全没有共享短文本指纹的文件对跳过 SequenceMatcher。
  - 把 compare 改成异步任务，前端轮询进度。

### 12.3 PDF OCR 耗时

PDF 转换依赖 MonkeyOCR：

- 单个 PDF 可能耗时数秒到数十秒。
- 多个 PDF 串行转换可能导致请求耗时较长。

MVP 策略：

- 复用 `DocumentStore` 缓存，避免重复 OCR。
- 同一请求内先串行处理，保持实现简单。
- 前端 loading 文案不只写“对比中”，应能覆盖“文档转换中”。
- 后续可并行转换 PDF，但要注意 OCR 服务压力。

### 12.4 高亮 DOCX 与 PDF 原版式

PDF 上传后的下载副本是高亮 DOCX，不保留 PDF 原版式。

风险：

- 用户可能以为能下载高亮 PDF。

缓解：

- 前端下载按钮文案使用“高亮副本”。
- 文档说明 PDF 会转换为文本审阅副本。

## 13. 实施顺序

1. **配置层**
   - `govdoc/config.py` 新增 `CompareConfig`。
   - `govdoc.yaml` 新增 `compare` 配置段。

2. **Schema 层**
   - `govdoc/schemas/compare.py` 从 `first/second` 改为 `files[]`。
   - 新增 `CompareFileMeta`、`file_indices`、`occurrences`、`per_file_counts`。

3. **提取层**
   - `govdoc/compare/extractor.py` 新增 `extract_markdown_paragraphs()`。
   - 保留 DOCX 提取器。

4. **算法层**
   - `govdoc/compare/compare.py` 新增 `find_nfile_exact_matches()`。
   - 新增 `find_nfile_common_segments()`，使用 `dict[int, list[TextRange]]`。

5. **服务层**
   - `govdoc/compare/service.py` 改造内部模型。
   - 改造入口函数为 `files[]`。
   - PDF 通过 `get_document_store().get_or_convert()` 转 markdown。
   - 改造 annotation、序列化、下载生成。

6. **API 层**
   - `govdoc/api/routes/compare.py` 改为接收 `files`。
   - 下载接口改为 `{file_index}`。

7. **后端调用方**
   - `govdoc/harness/api_eval.py` 改上传字段。
   - 后端 E2E 改契约。

8. **前端 API**
   - `frontend/src/api/compare.ts` 更新类型。
   - `compareDocxFiles()` 改为 `compareFiles(files)`。

9. **前端 UI**
   - `frontend/src/pages/DocComparePage.tsx` 改为多文件上传。
   - 结果区改为横向滚动 N 文件栏 + 匹配清单。
   - 下载按钮循环生成。

10. **测试**
    - 单元测试：extractor、算法、service。
    - 后端 E2E：N 文件上传、下载、错误格式。
    - 前端 E2E：多文件上传和结果渲染。

## 14. 验证命令

后端单测：

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_compare_extractor.py tests/unit/test_compare_service.py -v
```

后端 E2E：

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/e2e/test_04_compare.py -v
```

前端类型检查：

```bash
cd frontend && npm run build
```

前端 E2E：

```bash
cd frontend && npx playwright test
```

L2 API harness 相关检查：

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v
```

如验证真实 PDF OCR，需要确保环境包含：

```bash
export no_proxy="110.42.53.85,100.81.95.44,localhost,127.0.0.1,${no_proxy:-}"
export NO_PROXY="110.42.53.85,100.81.95.44,localhost,127.0.0.1,${NO_PROXY:-}"
```

## 15. 完成标准

- API 支持 `files[]` 上传 N 份 `.docx` / `.pdf`。
- 返回结构中不存在 `first` / `second` 业务字段。
- 任意两个或多个文件共享内容都能返回。
- 同一文件内多次出现同一匹配不会被覆盖。
- PDF 通过现有 Scrivai/MonkeyOCR 配置转换，并复用缓存。
- 每个上传文件都有对应的高亮 DOCX 下载副本。
- 前端可以上传多份文件，结果区能展示 N 个文件。
- 后端单测、后端 E2E、前端构建、前端 E2E 更新并通过。
