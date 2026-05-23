# E2E 测试全覆盖设计

> 日期: 2026-05-23
> 状态: 设计完成

## 目标

构建完善的 E2E 测试体系，覆盖全部 6 页面的全部离散操作。核心原则：

1. **对比场景精确匹配**：造数据，真值已知，断言精确数值
2. **审核场景结构+合理性**：不要求精确匹配，但验证 verdict/rationale/suggestion/evidence 非空且合理
3. **全覆盖**：所有按钮、操作、输出结果必须覆盖，包括 LLM 测试
4. **严格断言**：不能宽松到实际出错却测试通过

## 一、对比场景 — 造数据 + 精确断言

### 1.1 后端对比算法概要

三级匹配，优先级从高到低：

| 级别 | category | 定义 | 去重 |
|------|----------|------|------|
| 段落级 | `paragraph` | 完全相同的 DOCX 段落文本 | — |
| 句子级 | `sentence` | 完全相同的句子（以 `。！？；` 分割） | 已被段落级覆盖的不重复计 |
| 片段级 | `segment` | ≥16 字符的连续公共子串（SequenceMatcher） | 已被段落/句子级覆盖的不重复计 |

关键规则：
- DOCX 解析：直接读 `word/document.xml`，按 `<w:p>` 提取段落，`normalize_text()` 去零宽/NBSP
- PDF 解析：经 MonkeyOCR 转 Markdown → `extract_markdown_paragraphs()` 提取段落
- 全文构建：`"\n".join(paragraphs)`，段落间有 `\n` 分隔符
- 计数：`commonParagraphCount` = 段落匹配数，`commonSentenceCount` = 句子匹配数，`commonSegmentCount` = 片段匹配数，`matchCount` = 三者之和

### 1.2 测试数据矩阵

造 **10 个 DOCX 文件** + 对应 PDF，提交到 `tests/fixtures/compare/`。

#### 用例 ① 段落级精确匹配

| 文件 | 段落内容 |
|------|---------|
| `para_a.docx` | ["投标人应具有独立承担民事责任的能力。", "文件A独有的第二段内容。"] |
| `para_b.docx` | ["投标人应具有独立承担民事责任的能力。", "文件B独有的第二段内容。"] |

**真值**: `commonParagraphCount=1, commonSentenceCount=0, commonSegmentCount=0, matchCount=1`

说明：
- 共享段落"投标人应具有独立承担民事责任的能力。" → 1 个段落匹配
- 独有段落完全不同且 < 16 字符连续公共子串 → 0 片段
- 无句末符内部分割（整段匹配已覆盖） → 0 句子

#### 用例 ② 句子级精确匹配

| 文件 | 段落内容 |
|------|---------|
| `sent_a.docx` | ["采购人可自行选择。供应商不得串通。评标委员会独立评审。"] |
| `sent_b.docx` | ["采购人可自行选择。代理机构按规定。评标委员会独立评审。"] |

**真值**: `commonParagraphCount=0, commonSentenceCount=2, matchCount=2`

说明：
- 整段不同（中间句不同） → 0 段落匹配
- "采购人可自行选择。" 和 "评标委员会独立评审。" 在两个文件中相同 → 2 句子
- 已被句子覆盖的文本不再产生片段匹配

#### 用例 ③ 片段级连续匹配

| 文件 | 段落内容 |
|------|---------|
| `seg_a.docx` | ["甲方根据具有良好的商业信誉和健全的财务会计制度的要求执行。"] |
| `seg_b.docx` | ["乙方应当具有良好的商业信誉和健全的财务会计制度并提交证明。"] |

**真值**: `commonParagraphCount=0, commonSentenceCount=0, commonSegmentCount≥1, matchCount≥1`

说明：
- 整段不同 → 0 段落
- 无完全相同句子 → 0 句子
- "具有良好的商业信誉和健全的财务会计制度" = 18 字符 ≥ 16 → ≥1 片段
- 匹配文本必须包含 "具有良好的商业信誉"

#### 用例 ④ 三级混合

| 文件 | 段落内容 |
|------|---------|
| `mix_a.docx` | ["完全相同的第一段落。", "第一句共享。第二句不同A。第三句共享。", "前缀具有良好的商业信誉和健全的财务会计制度后缀A。", "独有段落A。"] |
| `mix_b.docx` | ["完全相同的第一段落。", "第一句共享。第二句不同B。第三句共享。", "开头具有良好的商业信誉和健全的财务会计制度尾部B。", "独有段落B。"] |

**真值**: `commonParagraphCount=1, commonSentenceCount=2, commonSegmentCount≥1, matchCount≥4`

#### 用例 ⑤ 自比较

用 `para_a.docx` 与自身对比。

**真值**: `commonParagraphCount=2`（文件有 2 个段落，每个都匹配）

#### 用例 ⑥ 无重复

| 文件 | 段落内容 |
|------|---------|
| `unique_a.docx` | ["甲方内容。"] |
| `unique_b.docx` | ["乙方内容。"] |

**真值**: `matchCount=0`

#### 用例 ⑦ 多文档 N=4

| 文件 | 段落内容 |
|------|---------|
| `multi_1.docx` | ["四文件共享段落。", "仅12共享段落。", "仅1独有段落。"] |
| `multi_2.docx` | ["四文件共享段落。", "仅12共享段落。", "仅2独有段落。"] |
| `multi_3.docx` | ["四文件共享段落。", "仅34共享段落。", "仅3独有段落。"] |
| `multi_4.docx` | ["四文件共享段落。", "仅34共享段落。", "仅4独有段落。"] |

**真值**:
- `commonParagraphCount=3`（"四文件共享段落。" + "仅12共享段落。" + "仅34共享段落。"）
- "四文件共享段落。" 的 `fileIndices=[0,1,2,3]`
- "仅12共享段落。" 的 `fileIndices=[0,1]`
- "仅34共享段落。" 的 `fileIndices=[2,3]`

### 1.3 PDF 测试

将用例 ① 的 DOCX 手工转成 PDF（`para_a.pdf`, `para_b.pdf`）。

**真值与 DOCX 相同**：`commonParagraphCount=1, matchCount=1`。

理由：PDF 内嵌文本与 DOCX 内容一致，MonkeyOCR 提取结果应相同。

### 1.4 测试文件

重写 `test-14-compare-verify.js`，包含全部 7 个用例 + PDF 用例，每个用例精确断言。放 **all 模式**（非 quick），因为 PDF 转换耗时。

---

## 二、LLM 测试增强 — 结构完整性 + 内容合理性

### 2.1 增强 test-04（AI 提取）

在提取完成后（现有代码已等待完成），增加对每个新增审核点的验证：

```
对于每个提取出的审核点:
  payload = 解析 payload_json
  assert payload.title.length > 2
  assert payload.description.length > 10
  assert payload.category 非空
  assert payload.severity ∈ {"critical", "major", "minor"}
```

### 2.2 增强 test-05/06（AI 审核）

在审核完成后，对每个 completed 的 point_run 验证：

```
点击每个 completed 的审核点:
  assert "审核结论" 可见
  verdict_text = 获取结论文本
  assert verdict_text ∈ {"合规", "不合规", "存疑"}
  assert "审查意见" 可见且内容 length > 20
  assert "整改建议" 可见且内容 length > 10
  如果 verdict = "不合规" 或 "存疑":
    assert "原文引用" 可见
```

### 2.3 新增审核结果质量验证（test-15）

独立于 test-05/06（那些是 LLM 执行+等待），test-15 **直接读取已有数据**验证质量：

```
进入 /audit-results
选择一个 completed 的审核运行
遍历所有 completed 的审核点:
  验证 verdict/rationale/suggestion/evidence
进入 /workpaper
选择同一运行
验证底稿 HTML 包含 "审查"/"意见" 等关键词
验证文档信息卡片中 findings 数量 > 0
```

test-15 放 **quick 模式**（只读已有数据，不调 LLM），但依赖环境中存在已完成的审核运行。

---

## 三、现有测试断言加严

### 3.1 test-03（对比基础）

当前只检查 "匹配总数" 卡片出现。增加：
- 验证 4 个指标卡数值非空
- 验证匹配清单至少 1 项
- 验证匹配文本含中文

### 3.2 test-07（审核结果历史）

当前只检查列表和 UUID。增加：
- 点击审核点后验证右侧有 "审核结论" 或 "审核状态"

### 3.3 test-08-13（新增的 UI 测试）

已设计为严格断言，不需要额外加严。

---

## 四、最终测试文件清单

| 编号 | 文件 | 模式 | 类型 | 变更 |
|------|------|------|------|------|
| 01 | navigation | quick | UI | 不变 |
| 02 | import-checkpoints | quick | UI | 不变 |
| 03 | doc-compare | quick | UI | **加严断言** |
| 04 | ai-extract | all | LLM | **增加质量验证** |
| 05 | ai-audit | all | LLM | **增加质量验证** |
| 06 | ai-audit-multifile | all | LLM | **增加质量验证** |
| 07 | audit-results-history | quick | UI | **加严断言** |
| 08 | dashboard-details | quick | UI | 新增 |
| 09 | audit-library-crud | quick | UI | 新增 |
| 10 | ai-review-workflow | quick | UI | 新增 |
| 11 | audit-results-interactions | quick | UI | 新增 |
| 12 | workpaper-page | quick | UI | 新增 |
| 13 | doc-compare-advanced | quick | UI | 新增 |
| 14 | compare-verify | all | 精确验证 | **重写**（造数据+精确断言） |
| 15 | result-quality | quick | 质量验证 | **新增**（读已有数据验证结构+合理性） |

---

## 五、fixture 文件清单

```
tests/fixtures/compare/
├── para_a.docx          # 段落级用例
├── para_b.docx
├── para_a.pdf           # PDF 版
├── para_b.pdf
├── sent_a.docx          # 句子级用例
├── sent_b.docx
├── seg_a.docx           # 片段级用例
├── seg_b.docx
├── mix_a.docx           # 三级混合用例
├── mix_b.docx
├── unique_a.docx        # 无重复用例
├── unique_b.docx
├── multi_1.docx         # 多文档用例
├── multi_2.docx
├── multi_3.docx
└── multi_4.docx
```

---

## 六、验证计划

```bash
# 生成 fixture 文件
source activate govdoc-auditor-v3 && python tests/fixtures/compare/gen_fixtures.py

# 运行 quick 模式（UI + 质量验证，无 LLM）
bash frontend/e2e/run-tests.sh --quick

# 运行单个精确对比测试
bash frontend/e2e/run-tests.sh --only 14

# 运行全部（含 LLM）
bash frontend/e2e/run-tests.sh
```
