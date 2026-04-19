# 审查点表格导入功能 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支持直接上传 xls/xlsx/csv 格式的审查点表格，后端解析后批量生成 CheckpointDraft，进入标准草稿审核流程。

**Architecture:** 后端新增解析模块 `govdoc/parsers/checkpoint_import.py`，读取表格 → forward-fill 合并单元格 → 固定列映射 → 输出 `list[GovCheckpoint]`。新增 `POST /api/v1/checkpoints/import` 端点接收文件并批量写入 DB。前端在审核点库页面将"上传法规提取"按钮改为下拉菜单，新增"导入审查点表格"选项。

**Tech Stack:** Python (xlrd, openpyxl, csv) / FastAPI / SQLModel / Alembic / React + TypeScript

**Design Spec:** `docs/superpowers/specs/2026-04-19-checkpoint-import-design.md`

---

## File Structure

| 文件 | 操作 | 职责 |
|---|---|---|
| `govdoc/parsers/checkpoint_import.py` | CREATE | xls/xlsx/csv 解析 → GovCheckpoint 列表 |
| `govdoc/db/models.py:43-48` | MODIFY | CheckpointDraft.rule_source_id/extract_run_id 改为可选 |
| `govdoc/db/migrations/versions/0002_checkpoint_draft_nullable.py` | CREATE | Alembic 迁移 |
| `govdoc/api/schemas.py` | MODIFY | 新增 ImportCheckpointsResponse |
| `govdoc/api/routes/checkpoints.py` | MODIFY | 新增 POST /import 端点 |
| `frontend/src/api/v3.ts` | MODIFY | 新增 importCheckpoints() |
| `frontend/src/context/V3WorkbenchContext.tsx` | MODIFY | 新增 importCheckpointFile() |
| `frontend/src/pages/AuditLibraryPage.tsx` | MODIFY | 按钮改下拉 + 导入模式 |
| `tests/unit/test_checkpoint_import.py` | CREATE | 解析模块单元测试 |

---

## Task 1: DB 模型改动 + Alembic 迁移

**Files:**
- Modify: `govdoc/db/models.py:43-48`
- Create: `govdoc/db/migrations/versions/0002_checkpoint_draft_nullable.py`

- [ ] **Step 1: 修改 CheckpointDraft 模型，使 rule_source_id 和 extract_run_id 可选**

在 `govdoc/db/models.py` 中，将 `CheckpointDraft` 的两个字段改为 `Optional`：

```python
# 改前（第 44-47 行）
class CheckpointDraft(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    rule_source_id: str = Field(foreign_key="rulesource.id")
    payload_json: str
    extract_run_id: str

# 改后
class CheckpointDraft(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    rule_source_id: str | None = Field(default=None, foreign_key="rulesource.id")
    payload_json: str
    extract_run_id: str | None = Field(default=None)
```

- [ ] **Step 2: 生成 Alembic 迁移脚本**

运行:
```bash
conda run -n govdoc-auditor-v3 alembic revision --autogenerate -m "checkpoint_draft_nullable_fk"
```

预期: 在 `govdoc/db/migrations/versions/` 下生成新迁移文件，内容包含将 `rule_source_id` 和 `extract_run_id` 列改为 nullable 的操作。

- [ ] **Step 3: 应用迁移**

运行:
```bash
conda run -n govdoc-auditor-v3 alembic upgrade head
```

预期: `OK` 无报错。

- [ ] **Step 4: 验证迁移成功**

运行:
```bash
conda run -n govdoc-auditor-v3 python -c "
from govdoc.db.session import get_db_session
from govdoc.db.models import CheckpointDraft
with get_db_session() as s:
    d = CheckpointDraft(payload_json='{}', status='draft')
    s.add(d)
    s.commit()
    s.refresh(d)
    print(f'Created draft id={d.id}, rule_source_id={d.rule_source_id}, extract_run_id={d.extract_run_id}')
    s.delete(d)
    s.commit()
    print('Cleanup OK')
"
```

预期: `rule_source_id=None, extract_run_id=None`，无外键报错。

- [ ] **Step 5: 提交**

```bash
git add govdoc/db/models.py govdoc/db/migrations/versions/
git commit -m "feat: CheckpointDraft.rule_source_id/extract_run_id 改为可选，支持直接导入"
```

---

## Task 2: 解析模块 — 测试先行

**Files:**
- Create: `tests/unit/test_checkpoint_import.py`
- Create: `govdoc/parsers/checkpoint_import.py`

- [ ] **Step 1: 编写解析模块的失败测试**

创建 `tests/unit/test_checkpoint_import.py`：

```python
"""审查点表格导入解析模块���元测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from govdoc.parsers.checkpoint_import import parse_checkpoint_file
from govdoc.schemas import CheckpointCategory, GovCheckpoint, Severity

SAMPLE_XLS = Path("tests/e2e/data/附件9 处理处罚标准.xls")


@pytest.fixture
def parsed_xls() -> tuple[list[GovCheckpoint], list[str]]:
    """解析样例 xls，返回 (checkpoints, skipped_reasons)。"""
    return parse_checkpoint_file(SAMPLE_XLS)


class TestParseCheckpointFile:
    """针对样例 xls 的集成测试。"""

    def test_returns_non_empty_list(self, parsed_xls: tuple[list[GovCheckpoint], list[str]]) -> None:
        checkpoints, _ = parsed_xls
        assert len(checkpoints) > 40, f"预期至少 40 条审查点，实际 {len(checkpoints)}"

    def test_every_item_is_gov_checkpoint(self, parsed_xls: tuple[list[GovCheckpoint], list[str]]) -> None:
        checkpoints, _ = parsed_xls
        for cp in checkpoints:
            assert isinstance(cp, GovCheckpoint)

    def test_no_empty_description(self, parsed_xls: tuple[list[GovCheckpoint], list[str]]) -> None:
        checkpoints, _ = parsed_xls
        for cp in checkpoints:
            assert cp.description.strip(), f"审查�� {cp.id} 的 description 不应为空"

    def test_no_empty_title(self, parsed_xls: tuple[list[GovCheckpoint], list[str]]) -> None:
        checkpoints, _ = parsed_xls
        for cp in checkpoints:
            assert cp.title.strip(), f"审查点 {cp.id} 的 title 不应为空"

    def test_forward_fill_category(self, parsed_xls: tuple[list[GovCheckpoint], list[str]]) -> None:
        """所有审查点的 category 不应为 OTHER（样例文件的大类标题都能匹配到具体分类）。"""
        checkpoints, _ = parsed_xls
        for cp in checkpoints:
            assert cp.category != CheckpointCategory.OTHER, (
                f"审查点 '{cp.title}' 的 category 不应为 OTHER，forward-fill 可能有问题"
            )

    def test_category_mapping(self, parsed_xls: tuple[list[GovCheckpoint], list[str]]) -> None:
        checkpoints, _ = parsed_xls
        categories = {cp.category for cp in checkpoints}
        assert CheckpointCategory.UNREASONABLE_RESTRICTION in categories

    def test_default_severity(self, parsed_xls: tuple[list[GovCheckpoint], list[str]]) -> None:
        checkpoints, _ = parsed_xls
        for cp in checkpoints:
            assert cp.severity == Severity.MAJOR

    def test_retrieval_hint_populated(self, parsed_xls: tuple[list[GovCheckpoint], list[str]]) -> None:
        checkpoints, _ = parsed_xls
        for cp in checkpoints:
            assert cp.retrieval_hint, f"审查点 {cp.id} 的 retrieval_hint 不应为空"
            assert len(cp.retrieval_hint) <= 80

    def test_legal_basis_parsed(self, parsed_xls: tuple[list[GovCheckpoint], list[str]]) -> None:
        """第一条审查点（采购文件设置差别歧视条款）应有 legal_basis。"""
        checkpoints, _ = parsed_xls
        first_with_legal = next(
            (cp for cp in checkpoints if cp.legal_basis),
            None,
        )
        assert first_with_legal is not None, "至少一条审查点应有 legal_basis"
        lb = first_with_legal.legal_basis[0]
        assert lb.law_name.strip(), "law_name 不应为空"

    def test_unique_ids(self, parsed_xls: tuple[list[GovCheckpoint], list[str]]) -> None:
        checkpoints, _ = parsed_xls
        ids = [cp.id for cp in checkpoints]
        assert len(ids) == len(set(ids)), "每条审查点的 id 应唯一"


class TestParseCSV:
    """CSV 格式测试，用临时文件构造。"""

    def test_csv_basic(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "大类,违法违规问题,表现形式,处理依据,处罚依据,处理建议,责任主体\n"
            "一、采购文件设置差别歧视条款,1.直接限制,设置供应商注册地限制,政府采购法第5条,,给予警告,采购人\n"
            ",2.限定行业,将特定行业作为条件,政府采购法第22条,,责令整改,代理机构\n",
            encoding="utf-8",
        )
        checkpoints, skipped = parse_checkpoint_file(csv_file)
        assert len(checkpoints) == 2
        assert checkpoints[0].title == "1.直接限制"
        assert checkpoints[1].category == checkpoints[0].category

    def test_csv_skip_empty_description(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "大类,违法违规问题,表现形式,处理依��,处罚依据,��理建议,责任主体\n"
            "一、限制条款,1.问题,,法条,,建议,主体\n"
            "一、限制条款,2.问题,有效表现形式,法条,,建议,主体\n",
            encoding="utf-8",
        )
        checkpoints, skipped = parse_checkpoint_file(csv_file)
        assert len(checkpoints) == 1
        assert len(skipped) == 1


class TestUnsupportedFormat:
    """不支持的文件格式应抛出 ValueError。"""

    def test_reject_txt(self, tmp_path: Path) -> None:
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("hello")
        with pytest.raises(ValueError, match="不支持"):
            parse_checkpoint_file(txt_file)
```

- [ ] **Step 2: 运行测试确认失败（模块尚未���现）**

运行:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_checkpoint_import.py -v 2>&1 | head -20
```

预期: `ModuleNotFoundError: No module named 'govdoc.parsers.checkpoint_import'` 或类似的 import error。

- [ ] **Step 3: 实现解析模块**

创建 `govdoc/parsers/checkpoint_import.py`：

```python
"""审查点表格导入解析器。

将 xls/xlsx/csv 格式的审查点表格解析为 GovCheckpoint 列表。
设计基线：docs/superpowers/specs/2026-04-19-checkpoint-import-design.md §4.1
"""

from __future__ import annotations

import csv
import re
import uuid
from pathlib import Path

from govdoc.schemas import (
    CheckpointCategory,
    GovCheckpoint,
    LegalBasis,
    Severity,
)

_HEADER_KEYWORDS = {"违法违规问题", "表现形式", "处理依据"}

_CATEGORY_MAP: list[tuple[list[str], CheckpointCategory]] = [
    (["歧视", "限制", "排斥"], CheckpointCategory.UNREASONABLE_RESTRICTION),
    (["围标", "串标"], CheckpointCategory.COLLUSION),
    (["意向"], CheckpointCategory.INTENTIONAL_BIDDING),
]

_LEGAL_SPLIT_RE = re.compile(r"[，,、;\n]+")


def parse_checkpoint_file(
    path: Path,
) -> tuple[list[GovCheckpoint], list[str]]:
    """解析审查点表格文件。

    Args:
        path: xls/xlsx/csv 文件路径。

    Returns:
        (checkpoints, skipped_reasons) 二元组。

    Raises:
        ValueError: ��件格式不支持。
    """
    suffix = path.suffix.lower()
    if suffix == ".xls":
        rows = _read_xls(path)
    elif suffix == ".xlsx":
        rows = _read_xlsx(path)
    elif suffix == ".csv":
        rows = _read_csv(path)
    else:
        raise ValueError(f"��支持的文件格式: {suffix}，仅支持 .xls / .xlsx / .csv")

    return _rows_to_checkpoints(rows)


def _read_xls(path: Path) -> list[list[str]]:
    """用 xlrd 读取 .xls 文��。"""
    import xlrd

    wb = xlrd.open_workbook(str(path))
    sh = wb.sheet_by_index(0)
    rows: list[list[str]] = []
    for r in range(sh.nrows):
        row = [str(sh.cell_value(r, c)).strip() for c in range(sh.ncols)]
        rows.append(row)
    return rows


def _read_xlsx(path: Path) -> list[list[str]]:
    """用 openpyxl 读取 .xlsx 文件。"""
    import openpyxl

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    sh = wb.active
    rows: list[list[str]] = []
    for row in sh.iter_rows(values_only=True):
        rows.append([str(c).strip() if c is not None else "" for c in row])
    wb.close()
    return rows


def _read_csv(path: Path) -> list[list[str]]:
    """用标准库 csv 读取 .csv 文件。"""
    rows: list[list[str]] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append([c.strip() for c in row])
    return rows


def _is_header_row(row: list[str]) -> bool:
    """判断是否为表头行。"""
    text = "".join(row)
    return any(kw in text for kw in _HEADER_KEYWORDS)


def _classify_category(raw: str) -> CheckpointCategory:
    """根据大类标题关键词映射到 CheckpointCategory。"""
    for keywords, category in _CATEGORY_MAP:
        if any(kw in raw for kw in keywords):
            return category
    return CheckpointCategory.OTHER


def _parse_legal_basis(text: str) -> list[LegalBasis]:
    """将法条引用文本拆��为 LegalBasis 列表。"""
    if not text.strip():
        return []
    parts = _LEGAL_SPLIT_RE.split(text.strip())
    return [
        LegalBasis(law_name=p.strip(), article="", quote="")
        for p in parts
        if p.strip()
    ]


def _rows_to_checkpoints(
    rows: list[list[str]],
) -> tuple[list[GovCheckpoint], list[str]]:
    """将��维行列转为 GovCheckpoint 列表。

    包含 forward-fill、表头跳过、空行过滤。
    """
    checkpoints: list[GovCheckpoint] = []
    skipped: list[str] = []

    header_found = False
    ncols = max((len(r) for r in rows), default=0)
    prev: list[str] = [""] * ncols

    for row_idx, raw_row in enumerate(rows):
        row = raw_row + [""] * (ncols - len(raw_row))

        if not header_found:
            if _is_header_row(row):
                header_found = True
            continue

        # forward-fill
        for i in range(ncols):
            if row[i]:
                prev[i] = row[i]
            else:
                row[i] = prev[i]

        description = row[2] if len(row) > 2 else ""
        if not description.strip():
            skipped.append(f"第{row_idx + 1}行：表现形式为空")
            continue

        category_raw = row[0] if len(row) > 0 else ""
        title = row[1] if len(row) > 1 else ""
        legal_text_1 = row[3] if len(row) > 3 else ""
        legal_text_2 = row[4] if len(row) > 4 else ""

        legal_basis = _parse_legal_basis(legal_text_1) + _parse_legal_basis(legal_text_2)

        cp = GovCheckpoint(
            id=uuid.uuid4().hex,
            category=_classify_category(category_raw),
            title=title or description[:40],
            description=description,
            legal_basis=legal_basis,
            severity=Severity.MAJOR,
            retrieval_hint=description[:80],
        )
        checkpoints.append(cp)

    return checkpoints, skipped
```

- [ ] **Step 4: 运行测试确认通过**

运行:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/test_checkpoint_import.py -v
```

预期: 全部 PASSED。

- [ ] **Step 5: 提交**

```bash
git add govdoc/parsers/checkpoint_import.py tests/unit/test_checkpoint_import.py
git commit -m "feat: 新增审查点表格导入解析模块 + 单元测试"
```

---

## Task 3: API schema + 端点

**Files:**
- Modify: `govdoc/api/schemas.py`
- Modify: `govdoc/api/routes/checkpoints.py`

- [ ] **Step 1: 在 govdoc/api/schemas.py 新增 ImportCheckpointsResponse**

在文件末尾追加：

```python
class ImportCheckpointsResponse(GovDocModel):
    """审查点表格导入响应。"""

    imported_count: int
    skipped_count: int
    skipped_reasons: list[str] = Field(default_factory=list)
    drafts: list[dict[str, str | None]] = Field(default_factory=list)
```

- [ ] **Step 2: 在 govdoc/api/routes/checkpoints.py 新增导入端点**

在文件头部追加 import：

```python
import tempfile
from pathlib import Path

from fastapi import File, UploadFile
```

在 `router` 下新增端点（在现有路由之后）：

```python
_ALLOWED_EXTENSIONS = {".xls", ".xlsx", ".csv"}


@router.post("/import")
async def import_checkpoints(file: UploadFile = File(...)):
    """上传审查点表格（xls/xlsx/csv），批量生成 CheckpointDraft。"""
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {suffix}，仅支持 .xls / .xlsx / .csv",
        )

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        from govdoc.parsers.checkpoint_import import parse_checkpoint_file

        checkpoints, skipped_reasons = parse_checkpoint_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    drafts: list[dict[str, str | None]] = []
    with get_db_session() as session:
        for cp in checkpoints:
            draft = CheckpointDraft(
                payload_json=cp.model_dump_json(),
                status="draft",
            )
            session.add(draft)
            session.flush()
            drafts.append(_serialize_draft(draft))
        session.commit()

    return {
        "imported_count": len(checkpoints),
        "skipped_count": len(skipped_reasons),
        "skipped_reasons": skipped_reasons,
        "drafts": drafts,
    }
```

- [ ] **Step 3: 验证端点注册正确**

运行:
```bash
conda run -n govdoc-auditor-v3 python -c "
from govdoc.api.main import app
routes = [r.path for r in app.routes]
assert '/api/v1/checkpoints/import' in routes, f'路由未��册: {routes}'
print('路由注册 OK')
"
```

预期: `路由注册 OK`

- [ ] **Step 4: 用 Swagger UI 手动验证（启动后端）**

运行:
```bash
conda run -n govdoc-auditor-v3 uvicorn govdoc.api.main:app --host 0.0.0.0 --port 8000
```

在浏览器打开 `http://localhost:8000/docs`，找到 `POST /api/v1/checkpoints/import`，上传 `tests/e2e/data/附件9 处理处罚标准.xls`。

预期: 返回 `imported_count: 52`，`skipped_count: 0`，`drafts` 数组长度 52。

- [ ] **Step 5: 提交**

```bash
git add govdoc/api/schemas.py govdoc/api/routes/checkpoints.py
git commit -m "feat: 新增 POST /api/v1/checkpoints/import 端点"
```

---

## Task 4: 前端 — API 函数 + Context 方法

**Files:**
- Modify: `frontend/src/api/v3.ts`
- Modify: `frontend/src/context/V3WorkbenchContext.tsx`

- [ ] **Step 1: 在 frontend/src/api/v3.ts 新增 importCheckpoints 函数**

在 `/* ── Checkpoints ── */` 区块末尾（`deleteCheckpoint` 之后）追加：

```typescript
export function importCheckpoints(
  file: File,
): Promise<{
  imported_count: number;
  skipped_count: number;
  skipped_reasons: string[];
  drafts: Array<{ id: string; status: string; payload_json: string }>;
}> {
  const form = new FormData();
  form.append("file", file);
  return request("/api/v1/checkpoints/import", {
    method: "POST",
    body: form,
  });
}
```

- [ ] **Step 2: 在 V3WorkbenchContext.tsx 的 interface 中新增 importCheckpointFile 声明**

在 `WorkbenchContextValue` 接口中，`updateCheckpoint` 行之前追加：

```typescript
  // Checkpoint import
  importCheckpointFile: (file: File) => Promise<{ imported_count: number; skipped_count: number }>;
```

- [ ] **Step 3: 在 WorkbenchProvider 中实现 importCheckpointFile**

在 `handleDeleteCheckpoint` 函数之后追加：

```typescript
  async function handleImportCheckpointFile(file: File) {
    const result = await api.importCheckpoints(file);
    await refreshAll();
    return { imported_count: result.imported_count, skipped_count: result.skipped_count };
  }
```

- [ ] **Step 4: 在 context value 对象中注册该方法**

在 `value` 对象中，`updateCheckpoint` 行之前追加：

```typescript
    importCheckpointFile: handleImportCheckpointFile,
```

- [ ] **Step 5: 验证 TypeScript 编译通过**

运行:
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

预期: 无错误。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/api/v3.ts frontend/src/context/V3WorkbenchContext.tsx
git commit -m "feat(frontend): 新增 importCheckpoints API 函数和 context 方法"
```

---

## Task 5: 前端 — AuditLibraryPage 改造

**Files:**
- Modify: `frontend/src/pages/AuditLibraryPage.tsx`

- [ ] **Step 1: 从 context 中解构 importCheckpointFile**

在 `AuditLibraryPage` 函数开头的 `useWorkbench()` 解构中追加 `importCheckpointFile`：

```typescript
  const {
    apiConnected,
    checkpoints,
    extractStatus,
    extractError,
    uploadRuleAndExtract,
    updateCheckpoint,
    deleteCheckpoint,
    importCheckpointFile,  // 新增
  } = useWorkbench();
```

- [ ] **Step 2: 扩展 mode state 支持 "import" 模式**

将 mode 类型从 `"list" | "upload"` ���为 `"list" | "upload" | "import"`：

```typescript
  const [mode, setMode] = useState<"list" | "upload" | "import">("list");
```

新增导入相关 state：

```typescript
  // Import state
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ imported_count: number; skipped_count: number } | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
```

- [ ] **Step 3: 新增 handleImport 函数**

在 `handleUpload` 之后追加：

```typescript
  async function handleImport() {
    if (!importFile) return;
    setImporting(true);
    setImportResult(null);
    setImportError(null);
    try {
      const result = await importCheckpointFile(importFile);
      setImportResult(result);
      setImportFile(null);
    } catch (e: unknown) {
      setImportError(e instanceof Error ? e.message : "导入失败");
    } finally {
      setImporting(false);
    }
  }
```

- [ ] **Step 4: 将 PageHero 的 actions 按钮改为下拉菜���**

替换现有的 `actions` prop，改为下拉菜单交互。在 `mode === "list"` 时展示下拉菜单，其他模式展示"返回列表"按钮：

```tsx
      <PageHero
        eyebrow="审核点库"
        title="审核点管理"
        description="上传法规文件提取审核点，或查看和管理已有审核点。"
        actions={
          mode === "list" ? (
            <div style={{ position: "relative", display: "inline-block" }}>
              <DropdownMenu
                trigger={<Button icon={Upload}>上传 ▾</Button>}
                items={[
                  { label: "AI 提取", onClick: () => setMode("upload") },
                  { label: "导入审查点��格", onClick: () => setMode("import") },
                ]}
              />
            </div>
          ) : (
            <Button tone="secondary" onClick={() => { setMode("list"); setImportResult(null); setImportError(null); }}>
              返回列表
            </Button>
          )
        }
      />
```

- [ ] **Step 5: 在 Ui.tsx 中实现 DropdownMenu 组件**

在 `frontend/src/components/Ui.tsx` 中，先修改 react import 追加 `useState`, `useRef`, `useEffect`：

```typescript
// 改前
import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type PropsWithChildren,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

// 改后
import {
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type PropsWithChildren,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
```

然后在文件末尾追加：

```tsx
export function DropdownMenu({
  trigger,
  items,
}: {
  trigger: ReactNode;
  items: Array<{ label: string; onClick: () => void }>;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} style={{ position: "relative", display: "inline-block" }}>
      <div onClick={() => setOpen((o) => !o)}>{trigger}</div>
      {open && (
        <div className="dropdown-menu">
          {items.map((item) => (
            <button
              key={item.label}
              className="dropdown-item"
              type="button"
              onClick={() => { item.onClick(); setOpen(false); }}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

需要在 `styles.css` 追加对应样式：

```css
.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  z-index: 100;
  min-width: 180px;
  margin-top: 4px;
  padding: 4px 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.dropdown-item {
  display: block;
  width: 100%;
  padding: 8px 16px;
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: var(--text);
}

.dropdown-item:hover {
  background: var(--surface-hover, #f5f5f5);
}
```

- [ ] **Step 6: 在 mode 渲染条件中新增 "import" 模式的 UI**

在现有 `mode === "list"` 和 `mode === "upload"` 之间（三元表达式改为条件分支），新增导入模式面板：

```tsx
      {mode === "import" && (
        <div className="stack-gap">
          <Card>
            <CardHeader title="导入审查点表格" description="上传已整理���审查点表格（.xls / .xlsx / .csv），系统将自动解析并生成草稿审核点。" />
            <div className="modal-form">
              <Field label="审查点文件">
                {importFile ? (
                  <div className="file-chip-list">
                    <div className="file-chip">
                      <div>
                        <strong>{importFile.name}</strong>
                        <span>{(importFile.size / 1024).toFixed(1)} KB</span>
                      </div>
                      <button className="icon-button" type="button" onClick={() => setImportFile(null)}>
                        ×
                      </button>
                    </div>
                  </div>
                ) : (
                  <FileDropzone
                    title="选择审查点表格"
                    subtitle="支持 .xls, .xlsx, .csv"
                    accept=".xls,.xlsx,.csv"
                    onSelect={(files) => setImportFile(files[0] ?? null)}
                  />
                )}
              </Field>
              {importResult && (
                <InlineNotice
                  tone="success"
                  message={`成功导入 ${importResult.imported_count} 条��查点${importResult.skipped_count > 0 ? `，跳过 ${importResult.skipped_count} 条` : ""}`}
                />
              )}
              {importError && (
                <InlineNotice tone="warning" message={importError} />
              )}
              <div className="footer-actions">
                <Button
                  tone="primary"
                  icon={Plus}
                  busy={importing}
                  disabled={!importFile || importing}
                  onClick={handleImport}
                >
                  开始导入
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
```

将现有三元表达式改为条件渲染（`{mode === "list" && (...)}` / `{mode === "upload" && (...)}` / `{mode === "import" && (...)}`）。

- [ ] **Step 7: 验证 TypeScript 编译通过**

运行:
```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

预期: 无错误。

- [ ] **Step 8: 启动前后端，在浏览器中测试完整流程**

终端 1:
```bash
conda run -n govdoc-auditor-v3 uvicorn govdoc.api.main:app --host 0.0.0.0 --port 8000
```

终端 2:
```bash
cd frontend && npx vite --host 0.0.0.0 --port 5173
```

在浏览器 `http://localhost:5173` 操作：
1. 进入"审核点库"页面
2. 点击"上传 ▾"下拉菜单，选择"导入��查点表格"
3. 拖入 `tests/e2e/data/附件9 处理处罚标准.xls`
4. 点击"开始导入"
5. 确认提示"成功导入 52 条审查点"
6. 确认审核点列表自动刷新，显示新导入的草稿审查点

- [ ] **Step 9: 提交**

```bash
git add frontend/src/pages/AuditLibraryPage.tsx frontend/src/components/Ui.tsx frontend/src/styles.css
git commit -m "feat(frontend): 审核点库页面支��导入审查点表格"
```

---

## Task 6: 全量测试 + 最终验证

**Files:**
- Run: 所有现有测试 + 新增测试

- [ ] **Step 1: 运行全部单���测试**

运行:
```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit/ -v
```

预期: 全部 PASSED，无回归。

- [ ] **Step 2: 运行 ruff 格式化和检查**

���行:
```bash
conda run -n govdoc-auditor-v3 ruff format . && conda run -n govdoc-auditor-v3 ruff check . --fix
```

预期: 无��误。

- [ ] **Step 3: 运��前端 TypeScript 检查**

运行:
```bash
cd frontend && npx tsc --noEmit
```

预期: 无错误。

- [ ] **Step 4: 提交格式修正（如有）**

```bash
git add -A && git diff --cached --stat
# 如有变更
git commit -m "style: ruff format + lint fix"
```
