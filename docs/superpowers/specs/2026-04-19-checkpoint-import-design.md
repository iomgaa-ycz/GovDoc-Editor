# 设计：直接导入已整理审查点（xls/xlsx/csv）

> 日期：2026-04-19
> 状态：待实施

## 1. 背景与目标

当前审查点只能通过管道 A（上传法规文件 → AI 提取）生成。用户已有整理好的审查点表格（如 `附件9 处理处罚标准.xls`），需要直接上传导入，跳过 AI 提取环节。

**目标**：新增"导入审查点表格"功能，用户上传 xls/xlsx/csv 文件，后端解析后批量生成 `CheckpointDraft`，进入标准草稿审核流程。

## 2. 决策记录

| 决策点 | 结论 |
|---|---|
| 导入后状态 | 进入 `CheckpointDraft`（草稿），需人工确认 |
| 列映射方式 | 固定映射，缺失字段用默认值填充 |
| 支持格式 | `.xls` + `.xlsx` + `.csv` |
| 行粒度 | 每一行"表现形式"生成一个独立审查点 |
| 合并单元格 | 向上回溯填充（forward-fill） |
| 前端入口 | 现有"上传法规提取"按钮改为下拉菜单，新增"导入审查点表格"选项 |
| 解析位置 | 后端解析（可复用于 CLI） |

## 3. 样例文件结构

文件：`tests/e2e/data/附件9 处理处罚标准.xls`，55 行 × 7 列。

| 列索引 | 列名 | 说明 |
|---|---|---|
| 0 | （大类标题） | 如"一、采购文件设置差别歧视条款"，合并单元格 |
| 1 | 违法违规问题 | 如"1.直接或变相对外地企业进入本地市场设置阻碍"，可合并 |
| 2 | 表现形式 | 具体表现，每行一条，作为审查点主体 |
| 3 | 处理依据 | 法条引用 |
| 4 | 处罚依据 | 法条引用 |
| 5 | 处理建议 | 如"给予警告" |
| 6 | 责任主体 | 如"采购人、代理机构" |

合并单元格特征：col[0] 和 col[1] 可能为空，表示沿用上方行的值。

## 4. 后端设计

### 4.1 新增解析模块 `govdoc/parsers/checkpoint_import.py`

**职责**：读取文件 → 统一为二维行列 → forward-fill → 固定映射 → 输出 `list[GovCheckpoint]`。

**解析器选择**：
- `.xls` → `xlrd`
- `.xlsx` → `openpyxl`
- `.csv` → 标准库 `csv`

**固定列映射**：

| xls 列 | → GovCheckpoint 字段 | 映射规则 |
|---|---|---|
| col[0] 大类标题 | `category` | 关键词匹配（见下表） |
| col[1] 违法违规问题 | `title` | 直接取值 |
| col[2] 表现形式 | `description` | 直接取值 |
| col[3] 处理依据 | `legal_basis[]` | 正则拆分法条引用 |
| col[4] 处罚依据 | `legal_basis[]`（追加） | 同上 |
| col[5] 处理建议 | 不映射（丢弃，用户可在草稿阶段手动补充） |
| col[6] 责任主体 | 不映射（丢弃，同上） |
| — | `severity` | 默认 `"major"` |
| — | `retrieval_hint` | 取 `description` 前 80 字符 |
| — | `id` | 自动生成 uuid |

**category 关键词映射**：

| 大类标题包含 | → CheckpointCategory |
|---|---|
| "歧视" 或 "限制" 或 "排斥" | `UNREASONABLE_RESTRICTION` |
| "围标" 或 "串标" | `COLLUSION` |
| "意向" | `INTENTIONAL_BIDDING` |
| 其余 | `OTHER` |

**forward-fill 逻辑**：
```
prev_values = [""] * ncols
for row in rows:
    for i in range(ncols):
        if row[i].strip():
            prev_values[i] = row[i].strip()
        else:
            row[i] = prev_values[i]
```

**过滤规则**：跳过表头行（自动检测含"违法违规问题"或"表现形式"的行为表头）和 `description`（col[2]）为空的行。

**legal_basis 解析**：对 col[3] 和 col[4] 的文本，用正则按中文逗号/顿号/换行拆分，每段生成一个 `LegalBasis(law_name=段落文本, article="", quote="")`。

### 4.2 API 端点

```
POST /api/v1/checkpoints/import
Content-Type: multipart/form-data
Body: file (UploadFile)
```

**响应 200**：
```json
{
  "imported_count": 42,
  "skipped_count": 3,
  "skipped_reasons": ["第5行：表现形式为空"],
  "drafts": [{"id": "xxx", "status": "draft", "payload_json": "..."}]
}
```

**响应 400**：文件格式不支持。

**流程**：
1. 校验文件扩展名（`.xls` / `.xlsx` / `.csv`），否则返回 400
2. 保存到临时文件
3. 调用 `parse_checkpoint_file(path)` → `list[GovCheckpoint]` + `list[str]`（跳过原因）
4. 为每个 `GovCheckpoint` 创建 `CheckpointDraft`（`rule_source_id=None`, `extract_run_id=None`）
5. 批量写入 DB
6. 清理临时文件
7. 返回结果

### 4.3 DB 模型改动

`govdoc/db/models.py` 中 `CheckpointDraft`：

```python
# 改前
rule_source_id: str = Field(foreign_key="rulesource.id")
extract_run_id: str

# 改后
rule_source_id: str | None = Field(default=None, foreign_key="rulesource.id")
extract_run_id: str | None = Field(default=None)
```

需要配套 Alembic 迁移脚本。

### 4.4 API schema

`govdoc/api/schemas.py` 新增：

```python
class ImportCheckpointsResponse(GovDocModel):
    imported_count: int
    skipped_count: int
    skipped_reasons: list[str] = Field(default_factory=list)
    drafts: list[dict[str, str | None]] = Field(default_factory=list)
```

## 5. 前端设计

### 5.1 `frontend/src/api/v3.ts`

新增：

```typescript
export function importCheckpoints(file: File): Promise<{
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

### 5.2 `frontend/src/pages/AuditLibraryPage.tsx`

现有"上传法规提取"按钮改为下拉菜单：

```
[上传 ▾]
  ├─ AI 提取       → 进入现有上传模式（mode="upload"）
  └─ 导入审查点表格 → 进入新导入模式（mode="import"）
```

新 `mode="import"` 的 UI：
- `FileDropzone`（accept=`.xls,.xlsx,.csv`）
- "开始导入"按钮
- 结果：`InlineNotice` 显示"成功导入 N 条，跳过 M 条"
- 自动刷新审查点列表

### 5.3 `frontend/src/context/V3WorkbenchContext.tsx`

新增 `importCheckpointFile(file: File)` 方法，内部调用 `importCheckpoints()` API + 刷新 checkpoints 列表。

## 6. 文件变更清单

| 文件 | 操作 | 变更内容 |
|---|---|---|
| `govdoc/parsers/checkpoint_import.py` | [NEW] | 解析模块：xls/xlsx/csv → GovCheckpoint |
| `govdoc/api/routes/checkpoints.py` | [MODIFY] | 新增 `POST /import` 端点 |
| `govdoc/api/schemas.py` | [MODIFY] | 新增 `ImportCheckpointsResponse` |
| `govdoc/db/models.py` | [MODIFY] | `CheckpointDraft.rule_source_id`/`extract_run_id` 改为可选 |
| `govdoc/db/migrations/` | [NEW] | Alembic 迁移脚本 |
| `frontend/src/api/v3.ts` | [MODIFY] | 新增 `importCheckpoints()` |
| `frontend/src/pages/AuditLibraryPage.tsx` | [MODIFY] | 上传按钮改下拉 + 新增导入模式 |
| `frontend/src/context/V3WorkbenchContext.tsx` | [MODIFY] | 新增 `importCheckpointFile()` |
| `tests/unit/test_checkpoint_import.py` | [NEW] | 解析模块单元测试 |

## 7. 验证计划

1. **单元测试**：用样例文件 `tests/e2e/data/附件9 处理处罚标准.xls` 验证解析结果
   - 检查总条数（应约 50 条，去除表头和空行）
   - 检查 forward-fill 正确性
   - 检查 category 映射正确性
   - 检查 legal_basis 解析
2. **API 测试**：通过 Swagger UI 上传文件，验证返回结果
3. **前端测试**：在浏览器中操作下拉菜单 → 选文件 → 导入 → 确认列表刷新
