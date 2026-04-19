# P1b · output_utils.py 混合重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 把 `govdoc/pipelines/output_utils.py`（225 行）重构为 `_preprocess()` + `json5.loads()` + `_validate_govfinding_schema()` 三段结构，行数降到 ~120 行，行为对真实 LLM 输出保持一致。

**Architecture:** 保留 ①（中文引号/裸引号修复）和 ③（业务 schema 校验），删除 ②（手写宽松 JSON 解析约 100 行），用 `json5` 库替代。

**Tech Stack:** Python 3.11, `json5>=0.9.28`

**依赖：** Umbrella 分支已建立；可与 P0/P1c 并行。

---

## Task 0: 建立子分支

- [ ] **Step 1: 从 umbrella 切子分支**

```bash
git checkout feat/tech-debt-cleanup
git pull --ff-only 2>/dev/null || true
git checkout -b feat/p1b-output-utils-json5
```

---

## Task 1: 采集真实 LLM 输出样本（护栏基准）

**Files:**
- Create: `tests/fixtures/output_utils_samples/*.txt`

- [ ] **Step 1: 列出可用的 mock trajectories**

Run:
```bash
ls tests/fixtures/mock_agent_trajectories/
```

Expected: 至少看到 `audit_case_01/` 和 `extract_case_01/`

- [ ] **Step 2: 从 trajectories 中抽出至少 10 份包含 LLM 原始输出的文件**

Run:
```bash
find tests/fixtures/mock_agent_trajectories -name "*.json" -o -name "output.json" -o -name "findings*.json" | head -20
```

按需从实际目录里挑 10 份，复制到新位置：

```bash
mkdir -p tests/fixtures/output_utils_samples
# 例：（按实际发现的文件替换）
for src in $(find tests/fixtures/mock_agent_trajectories -name "output*.json" | head -10); do
    name=$(echo "$src" | sed 's|/|_|g')
    cp "$src" "tests/fixtures/output_utils_samples/${name}"
done
ls tests/fixtures/output_utils_samples/
```

Expected: 目录下至少 10 份 `.json`

- [ ] **Step 3: 提交样本**

```bash
git add tests/fixtures/output_utils_samples/
git commit -m "test: 采集真实 LLM 输出样本用于 P1b 护栏"
```

---

## Task 2: 扩充 `test_output_utils.py` 到 12+ case

**Files:**
- Modify: `tests/unit/test_output_utils.py`

- [ ] **Step 1: 读现有测试**

Run: `cat tests/unit/test_output_utils.py`
Expected: 当前仅 2 个 case

- [ ] **Step 2: 扩充覆盖 6 类错误模式 × 2+ case**

追加到 `tests/unit/test_output_utils.py`:

```python
import json
from pathlib import Path

import pytest

from govdoc.pipelines.output_utils import relaxed_json_loads


# =============== 错误模式 1: 中文引号 ===============

def test_chinese_quotes_basic():
    """中文全角引号 " " → ASCII " """
    raw = '{"verdict": "合规"}'
    result = relaxed_json_loads(raw)
    assert result == {"verdict": "合规"}


def test_chinese_quotes_mixed_with_ascii():
    """中英文引号混杂"""
    raw = '{"verdict": "合规", "evidence": "see §3.2"}'
    result = relaxed_json_loads(raw)
    assert result["verdict"] == "合规"
    assert result["evidence"] == "see §3.2"


# =============== 错误模式 2: 字符串内裸引号 ===============

def test_unescaped_quotes_in_value():
    """字符串值内包含未转义双引号"""
    raw = '{"evidence": "他说 "你好"，然后离开"}'
    result = relaxed_json_loads(raw)
    assert "你好" in result["evidence"]


# =============== 错误模式 3: 尾部逗号 ===============

def test_trailing_comma_array():
    raw = '{"items": [1, 2, 3,]}'
    result = relaxed_json_loads(raw)
    assert result["items"] == [1, 2, 3]


def test_trailing_comma_object():
    raw = '{"a": 1, "b": 2,}'
    result = relaxed_json_loads(raw)
    assert result == {"a": 1, "b": 2}


# =============== 错误模式 4: 单引号 key ===============

def test_single_quoted_keys():
    raw = "{'verdict': '合规'}"
    result = relaxed_json_loads(raw)
    assert result == {"verdict": "合规"}


# =============== 错误模式 5: 结构正常（回归保护） ===============

def test_standard_json_passthrough():
    raw = '{"verdict": "合规", "evidence": "clean"}'
    result = relaxed_json_loads(raw)
    assert result == {"verdict": "合规", "evidence": "clean"}


def test_nested_structures():
    raw = '{"findings": [{"id": "f1", "verdict": "合规"}]}'
    result = relaxed_json_loads(raw)
    assert result["findings"][0]["verdict"] == "合规"


# =============== 错误模式 6: 组合错误 ===============

def test_chinese_quotes_plus_trailing_comma():
    raw = '{"verdict": "合规", "items": [1, 2,],}'
    result = relaxed_json_loads(raw)
    assert result["verdict"] == "合规"
    assert result["items"] == [1, 2]


def test_single_quotes_plus_trailing_comma():
    raw = "{'verdict': '合规', 'items': [1, 2,],}"
    result = relaxed_json_loads(raw)
    assert result["verdict"] == "合规"


# =============== 错误模式 7: 注释（json5 原生支持） ===============

def test_json5_line_comment():
    raw = """{
        // 这是注释
        "verdict": "合规"
    }"""
    result = relaxed_json_loads(raw)
    assert result == {"verdict": "合规"}


# =============== Smoke: 真实 LLM 输出样本 ===============

@pytest.mark.parametrize("sample_path", sorted(Path("tests/fixtures/output_utils_samples").glob("*.json")))
def test_real_llm_samples_parse_successfully(sample_path):
    """对 Task 1 采集的每个真实 LLM 输出样本，relaxed_json_loads 必须 parse 成功。"""
    raw = sample_path.read_text(encoding="utf-8")
    # 允许空文件跳过
    if not raw.strip():
        pytest.skip(f"empty sample: {sample_path.name}")
    result = relaxed_json_loads(raw)
    # 不强求结构，只要能 parse 成功（非 None 且无异常）
    assert result is not None


# =============== Schema 验证（③ 业务级） ===============

def test_schema_validation_govfinding_required_fields():
    """relaxed_json_loads 解析后，业务 schema 校验应能识别必填字段缺失。"""
    # 此测试的具体断言取决于 normalize_output 的 schema 逻辑
    # 保留占位，实际按 output_utils.py 中的校验器形态补
    pass
```

- [ ] **Step 3: 跑测试，确认 12+ 通过（当前手写实现已覆盖这些情况）**

Run:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_output_utils.py -v
```

Expected: 12+ case 全绿。如有 FAIL，说明当前手写实现 **本就没覆盖某模式**——这是发现，不是回归。如发现 FAIL，需在 Task 3 的重构里保证 json5 能处理该模式。

- [ ] **Step 4: 提交**

```bash
git add tests/unit/test_output_utils.py
git commit -m "test: 扩充 output_utils 单测到 12+ case 覆盖 6 类 LLM 输出错误"
```

---

## Task 3: 添加 json5 依赖

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 读 pyproject.toml 的 dependencies**

Run: `grep -A 30 'dependencies = \[' pyproject.toml | head -30`

- [ ] **Step 2: 加 `json5>=0.9.28`**

Edit `pyproject.toml`，在 `dependencies = [...]` 列表末尾加：

```toml
"json5>=0.9.28",
```

- [ ] **Step 3: 安装**

```bash
conda run -n govdoc-auditor-v3 pip install -e .
```

Expected: json5 被安装

- [ ] **Step 4: 验证 import**

```bash
conda run -n govdoc-auditor-v3 python -c "import json5; print(json5.__version__)"
```

Expected: 打印版本号（≥0.9.28）

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml
git commit -m "chore: 添加 json5 依赖用于 P1b output_utils 重构"
```

---

## Task 4: 重构 output_utils.py 为三段结构

**Files:**
- Modify: `govdoc/pipelines/output_utils.py`

- [ ] **Step 1: 阅读当前文件**

Run: `cat govdoc/pipelines/output_utils.py | head -80`

- [ ] **Step 2: 改写为三段结构**

新文件结构（目标 ≤140 行）：

```python
"""输出工具：LLM 输出的 relaxed JSON 解析 + 业务级 schema 校验。

三段结构：
  ① _preprocess: 修复 LLM 中文输出特有问题（中文引号、裸引号）— 保留手写
  ② json5.loads: 宽松 JSON 解析（尾逗号/单引号/注释）— 交给 json5 库
  ③ _validate_*_schema: 业务级字段校验 — 保留

设计基线：docs/v2-lessons-design-amendment.md §P1
"""
from __future__ import annotations

import logging
import re
from typing import Any

import json5

logger = logging.getLogger(__name__)


# =============== ① Preprocess ===============

_CHINESE_DOUBLE_QUOTE_OPEN = "\u201c"   # "
_CHINESE_DOUBLE_QUOTE_CLOSE = "\u201d"  # "


def _preprocess(raw: str) -> str:
    """修 LLM 中文输出的两类错误：中文引号 + 字符串内裸双引号。

    ① 把中文引号 " " 替换为 ASCII "
    ② 对字符串内未转义的双引号加反斜杠（启发式：当下一个 " 后面不是结构性字符时判定为字符串内裸引号）

    其他宽松（尾逗号/单引号/注释）由 json5.loads 负责，此处不处理。
    """
    # 步骤 ①: 中文引号
    out = raw.replace(_CHINESE_DOUBLE_QUOTE_OPEN, '"').replace(_CHINESE_DOUBLE_QUOTE_CLOSE, '"')

    # 步骤 ②: 字符串内裸引号（搬运原 _escape_intra_string_quotes 逻辑）
    out = _escape_intra_string_quotes(out)

    return out


def _escape_intra_string_quotes(text: str) -> str:
    """对 JSON 字符串值内的裸双引号加反斜杠。

    启发式扫描：字符状态机，跟踪是否在字符串内，遇到 " 时判断是结束符还是正文引号。
    """
    # [搬原 output_utils.py 的 _escape_intra_string_quotes + _looks_like_string_terminator 实现]
    # 保留原有状态机逻辑；约 40-50 行
    raise NotImplementedError("从原 output_utils.py 搬运实现")


# =============== ② Relaxed Parse (json5) ===============

def relaxed_json_loads(raw: str) -> Any:
    """宽松 JSON 加载：预处理 → json5 解析 → 成功返回 dict/list。

    失败时记录 warning 并抛原异常。
    """
    if not raw or not raw.strip():
        raise ValueError("empty input")

    prepared = _preprocess(raw)
    try:
        return json5.loads(prepared)
    except Exception as exc:
        logger.warning("relaxed_json_loads 失败: %s（前 200 字符：%r）", exc, prepared[:200])
        raise


# =============== ③ Schema Validation ===============

def normalize_output(payload: Any, *, expected_kind: str = "audit") -> dict[str, Any]:
    """业务级 schema 归一化 / 必填字段校验。

    - expected_kind='audit': 期望 findings 数组，每项需 checkpoint_id/verdict/evidence
    - expected_kind='extract': 期望 checkpoints 数组，每项需 id/title/category

    返回归一化后的 dict；字段缺失抛 ValueError。
    """
    # [搬原 normalize_output + _normalize_structural_punctuation 的 schema 部分]
    raise NotImplementedError("从原 output_utils.py 搬运实现")
```

⚠️ 执行时：
- `_escape_intra_string_quotes` 和 `normalize_output` 的 body 从原文件**原封搬运**，不重新设计
- 删除原文件中与"宽松解析"有关的函数（`_normalize_structural_punctuation` 等）—— 这些是 ② 的，现在由 json5 负责

- [ ] **Step 3: 行数验证**

Run: `wc -l govdoc/pipelines/output_utils.py`
Expected: ≤140 行

- [ ] **Step 4: 跑扩充后的单测**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_output_utils.py -v`
Expected: **12+ case 全绿**

如有 FAIL，说明 json5 某个行为与手写不一致：
- 若是 json5 支持但未兼容的错误模式：在 `_preprocess` 里补修复
- 若是 json5 更严格（如原手写容错了奇怪输入）：评估是否真需要保留此容错；记录到 `工程md/INTEGRATION_ISSUES.md`

- [ ] **Step 5: 跑真样本 smoke**

Run:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_output_utils.py::test_real_llm_samples_parse_successfully -v
```

Expected: 所有真 LLM 样本 parse 通过

- [ ] **Step 6: 提交**

```bash
git add govdoc/pipelines/output_utils.py
git commit -m "refactor: 重构 output_utils 为 preprocess + json5 + validate 三段结构"
```

---

## Task 5: 上下游调用点验证

**Files:**
- 只读检查，不改：`govdoc/pipelines/pes_overrides.py` 等

- [ ] **Step 1: 全仓搜 `output_utils` 引用**

Run:
```bash
grep -rn "output_utils" govdoc/ tests/ --include="*.py"
```

- [ ] **Step 2: 对每个引用点确认未受影响**

如果有文件 import 了被删除的函数（如 `_normalize_structural_punctuation`），需要：
- 要么在这些文件里替换为新 API
- 要么重新暴露函数（但违背 YAGNI）

优先选方案 1（替换为 `relaxed_json_loads` 或 `normalize_output`）。

- [ ] **Step 3: 跑集成测试**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/integration/ -v`
Expected: 全绿（特别是 `test_pipeline_b_with_mock_pes_replay`）

- [ ] **Step 4: 跑完整测试套件**

Run: `conda run -n govdoc-auditor-v3 python -m pytest tests/ -v`
Expected: 全绿

- [ ] **Step 5: ruff 检查**

Run:
```bash
conda run -n govdoc-auditor-v3 ruff check govdoc/pipelines/output_utils.py tests/unit/test_output_utils.py
conda run -n govdoc-auditor-v3 ruff format --check govdoc/pipelines/output_utils.py tests/unit/test_output_utils.py
```

Expected: 零 warning、无格式差异

- [ ] **Step 6: 如果 Task 5 Step 2 有调整，提交**

```bash
git add <调整的文件>
git commit -m "refactor: 同步 output_utils 调用点到新 API"
```

---

## Task 6: 推 PR + 合入 umbrella

- [ ] **Step 1: 推到远端**

```bash
git push -u origin feat/p1b-output-utils-json5
```

- [ ] **Step 2: 开 PR（目标分支 feat/tech-debt-cleanup）**

PR 描述模板：
```
## 目的
P1b · output_utils.py 混合重构：保留 ①预处理 + ②换 json5 + 保留 ③schema 校验

## 变更
- 新增依赖 json5>=0.9.28
- govdoc/pipelines/output_utils.py: 225 → ≤140 行
- tests/unit/test_output_utils.py: 2 → 12+ case
- tests/fixtures/output_utils_samples/: 10 份真 LLM 输出样本

## DoD
- [x] 12+ case 全绿覆盖 6 类错误
- [x] 真样本 parse 成功率 100%
- [x] 行数 ≤140
- [x] ruff 零 warning
```

- [ ] **Step 3: CI 绿 + review 通过后，merge 到 umbrella**

```bash
git checkout feat/tech-debt-cleanup
git merge --no-ff feat/p1b-output-utils-json5 -m "Merge P1b · output_utils 混合重构"
```

- [ ] **Step 4: 执行回滚演练**

按 umbrella index plan §"回滚演练"章节执行。

---

## P1b DoD 汇总

- [ ] `test_output_utils.py` 12+ case 全绿
- [ ] 真 LLM 样本 parse 成功率 100%
- [ ] `output_utils.py` 总行数 ≤ 140
- [ ] `ruff check` 零新增 warning
- [ ] 调用点全部同步到新 API
- [ ] PR 描述完整
- [ ] 回滚演练通过
