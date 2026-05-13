---
type: plan
node_id: plan:multi-file-audit
title: 多文件审核功能实施计划
date: 2026-05-13
migrated_from: docs/superpowers/plans/2026-04-26-multi-file-audit-plan.md
tags: ["migrated"]
---

# 多文件审核工程计划：主招标文书 + 附件

## 背景

当前系统按单文件审核建模：

- `AuditRun.tender_doc_id` 只能关联一个 `TenderDoc`
- 前端一次只上传一个招标文书
- 管道 workspace 只注入 `data/tender.md`
- qmd 临时 collection 只索引主招标文书

目标是支持用户在前端上传一个主招标文书，以及多个补充文件、变更公告、答疑纪要等附件，并将这些文件作为同一次审核的固定输入包进行检索、阅读、判断和复现。

主文书和附件需要保留不同语义：

- 主文书是审核对象的基准文件，继续由 `AuditRun.tender_doc_id` 表示。
- 附件是本次审核输入包的补充上下文，可能修正、解释或覆盖主文书条款。
- 一次 `AuditRun` 必须锁定主文书和附件 ID 列表，避免重试或复现时被项目下其他文件污染。

## 现有可复用能力

- `FileDropzone` 已支持 `multiple` prop。
- `TenderDoc` 已支持同一 `project_id` 下多个文书。
- `DocumentStore` 已支持多文件存储和转换。
- qmd collection 的 `add_document` 可按 `doc_id` 幂等区分文档。
- 后端上传路由可以保持单文件接口，前端循环调用。

## 设计原则

1. 保持向后兼容：保留 `AuditRun.tender_doc_id` 作为主文书 FK。
2. MVP 不引入中间表：附件 ID 用 JSON list 存入 `AuditRun.supplementary_doc_ids`。
3. 明确输入边界：创建 `AuditRun` 时校验并保存本次附件 ID，后续运行和重试都使用这组固定输入。
4. qmd 和 workspace 双路径覆盖：qmd 正常时搜索整个输入包，qmd 不可用时 agent 也能读取 `supp_*.md`。
5. 前端区分主文书上传区和附件上传区，避免用“第一个文件是主文书”的隐式规则。

## 后端改动

### 1. `govdoc/db/models.py`

在 `AuditRun` 中新增附件字段：

```python
class AuditRun(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    tender_doc_id: str = Field(foreign_key="tenderdoc.id")
    supplementary_doc_ids: str | None = None  # JSON list[str]，附件文书 ID
    checkpoint_final_ids: str  # JSON list[str]
```

说明：

- `tender_doc_id` 继续表示主招标文书。
- `supplementary_doc_ids` 保存附件 `TenderDoc.id` 列表。
- 该字段不加 FK 约束，因此 API 层和 pipeline 层需要校验。

### 2. Alembic 迁移

生成并执行迁移：

```bash
conda run -n govdoc-auditor-v3 alembic revision --autogenerate -m "add supplementary_doc_ids to auditrun"
conda run -n govdoc-auditor-v3 alembic upgrade head
```

迁移预期是在 `auditrun` 表增加 nullable string column：

```python
op.add_column("auditrun", sa.Column("supplementary_doc_ids", sa.String(), nullable=True))
```

### 3. `govdoc/api/schemas.py`

扩展 `CreateAuditRunRequest`：

```python
class CreateAuditRunRequest(GovDocModel):
    project_id: str
    tender_doc_id: str
    supplementary_doc_ids: list[str] = Field(default_factory=list)
    checkpoint_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("checkpoint_ids", "checkpoint_final_ids"),
    )
```

注意：`supplementary_doc_ids` 使用 `Field(default_factory=list)`，保持和 `checkpoint_ids` 一致，避免 mutable default 风险。

### 4. `govdoc/api/routes/audit.py`

需要在路由文件中引入 `TenderDoc`，用于主文书和附件校验：

```python
from govdoc.db.models import AuditPointRun, AuditRun, CheckpointFinal, TenderDoc
```

在 `create_audit_run` 创建 `AuditRun` 前增加文书校验：

```python
main_doc = session.get(TenderDoc, payload.tender_doc_id)
if main_doc is None or main_doc.project_id != payload.project_id:
    raise HTTPException(status_code=400, detail="主文书不存在或不属于该项目")

seen = {payload.tender_doc_id}
supplementary_doc_ids: list[str] = []
for doc_id in payload.supplementary_doc_ids:
    if doc_id in seen:
        raise HTTPException(status_code=400, detail=f"附件 ID 重复或与主文书冲突: {doc_id}")
    doc = session.get(TenderDoc, doc_id)
    if doc is None or doc.project_id != payload.project_id:
        raise HTTPException(status_code=400, detail=f"附件不存在或不属于该项目: {doc_id}")
    seen.add(doc_id)
    supplementary_doc_ids.append(doc_id)
```

创建 `AuditRun` 时保存附件关联：

```python
audit_run = AuditRun(
    project_id=payload.project_id,
    tender_doc_id=payload.tender_doc_id,
    supplementary_doc_ids=json.dumps(supplementary_doc_ids, ensure_ascii=False),
    checkpoint_final_ids=json.dumps(payload.checkpoint_ids, ensure_ascii=False),
    total_count=len(payload.checkpoint_ids),
)
```

`list_audit_runs` 和 `get_audit_run` 也应返回 `supplementary_doc_ids`，保持后端响应、前端类型和后续历史展示一致：

```python
def _load_supplementary_doc_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []
```

响应字段示例：

```python
{
    "id": r.id,
    "project_id": r.project_id,
    "tender_doc_id": r.tender_doc_id,
    "supplementary_doc_ids": _load_supplementary_doc_ids(r.supplementary_doc_ids),
    "status": r.status,
    "processed_count": r.processed_count,
    "total_count": r.total_count,
    "error": r.error,
    "created_at": str(r.created_at),
}
```

## 管道改动

### 5. `govdoc/pipelines/audit_tender.py`

#### 5.1 加载本次审核输入包

在 `run_audit` 读取主文书后，解析附件 ID：

```python
tender_doc = session.get(TenderDoc, audit_run.tender_doc_id)
if tender_doc is None:
    raise ValueError(f"未找到 TenderDoc: {audit_run.tender_doc_id}")

supp_ids = json.loads(audit_run.supplementary_doc_ids or "[]")
supplementary_docs: list[TenderDoc] = []
for sid in supp_ids:
    doc = session.get(TenderDoc, sid)
    if doc is None:
        raise ValueError(f"未找到附件 TenderDoc: {sid}")
    supplementary_docs.append(doc)
```

不要静默丢弃缺失附件。API 层虽然会校验，但 pipeline 层应对历史脏数据或手工 DB 修改保持可见失败。

#### 5.2 qmd 索引主文书和附件

当前 `_ensure_tender_collection` 有主文书已存在即提前返回的逻辑。多文件场景下需要逐文档幂等检查，避免附件未入库。

当前函数职责分两层：

- `_index_tender_doc` 是外壳，负责 replay 判断和 qmd 异常降级。
- `_ensure_tender_collection` 是实际写 qmd 的地方，当前的 `coll.add_document(...)` 在这里。

因此实现时两层都要扩展参数：`_index_tender_doc` 接收 `supplementary_docs`，再传给 `_ensure_tender_collection`；真正的逐文件入库仍放在 `_ensure_tender_collection` 内部。

建议抽出 helper：

```python
def _add_doc_to_collection(
    coll: Any,
    audit_run_id: str,
    doc: TenderDoc,
    source_type: str,
) -> None:
    if coll.get_document(doc.id) is not None:
        return
    md_path = Path(doc.markdown_path).expanduser().resolve()
    if not md_path.exists():
        logger.warning("文书 markdown 不存在，跳过 qmd 索引: %s", md_path)
        return
    coll.add_document(
        doc.id,
        md_path.read_text(encoding="utf-8"),
        metadata={
            "audit_run": audit_run_id,
            "source": doc.filename,
            "filename": doc.filename,
            "source_type": source_type,
        },
    )
```

然后让 `_ensure_tender_collection` 接收附件：

```python
def _ensure_tender_collection(
    audit_run_id: str,
    tender_doc: TenderDoc,
    supplementary_docs: Sequence[TenderDoc] = (),
    *,
    qmd_client: Any | None = None,
) -> str:
    collection_name = f"run_{audit_run_id}_tender"
    client = qmd_client or get_qmd()
    coll = client.collection(collection_name)

    _add_doc_to_collection(coll, audit_run_id, tender_doc, "main")
    for doc in supplementary_docs:
        _add_doc_to_collection(coll, audit_run_id, doc, "supplementary")

    return collection_name
```

`source` 是旧字段，`filename` 和 `source_type` 是新增字段。保留 `source` 可以降低旧逻辑或历史测试依赖 metadata 字段时的兼容风险。

`_index_tender_doc` 同步扩展参数，并在 replay 模式仍只返回占位 collection 名，不触发真实 qmd：

```python
def _index_tender_doc(
    audit_run: AuditRun,
    tender_doc: TenderDoc,
    *,
    supplementary_docs: Sequence[TenderDoc] = (),
    replay: bool,
) -> str | None:
    if replay:
        return f"run_{audit_run.id}_tender"
    try:
        return _ensure_tender_collection(
            audit_run.id,
            tender_doc,
            supplementary_docs=supplementary_docs,
        )
    except Exception:
        return None
```

#### 5.3 workspace 注入多文档

`_run_single_point` 增加参数：

```python
async def _run_single_point(
    point_run: AuditPointRun,
    checkpoint: GovCheckpoint,
    tender_doc: TenderDoc,
    *,
    supplementary_docs: Sequence[TenderDoc] = (),
    audit_run: AuditRun,
    tender_collection: str | None,
    ...
) -> tuple[Any, Any]:
```

构造 `data_inputs`：

```python
data_inputs = {
    "tender.md": Path(tender_doc.markdown_path).expanduser().resolve(),
    "checkpoints.json": checkpoint_path,
}

for index, doc in enumerate(supplementary_docs):
    data_inputs[f"supp_{index}.md"] = Path(doc.markdown_path).expanduser().resolve()
```

#### 5.4 写入 `documents.json` manifest

新增 manifest，让 agent 知道 `supp_0.md` 对应哪个原始文件：

```python
manifest = [
    {"path": "tender.md", "filename": tender_doc.filename, "source_type": "main"},
    *[
        {
            "path": f"supp_{index}.md",
            "filename": doc.filename,
            "source_type": "supplementary",
        }
        for index, doc in enumerate(supplementary_docs)
    ],
]
```

按 `write_single_checkpoint_json` 的模式新增 `write_documents_manifest_json(audit_run.id, manifest)`，写入临时文件后返回路径：

```python
def write_documents_manifest_json(
    audit_run_id: str,
    manifest: list[dict[str, str]],
) -> Path:
    import tempfile

    tmp = tempfile.mkdtemp(prefix=f"audit_{audit_run_id}_")
    path = Path(tmp) / "documents.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
```

然后加入 `data_inputs`：

```python
data_inputs["documents.json"] = manifest_path
```

workspace 最终应包含：

```text
data/
  tender.md
  supp_0.md
  supp_1.md
  checkpoints.json
  documents.json
```

#### 5.5 动态 task prompt

将单文书 prompt：

```text
审核 data/tender.md，针对 data/checkpoints.json 中的唯一审核点「...」生成一条 GovFinding。
```

改为：

```python
files_desc = "data/tender.md"
if supplementary_docs:
    files_desc += "、" + "、".join(
        f"data/supp_{index}.md" for index in range(len(supplementary_docs))
    )

task_prompt = (
    f"审核 {files_desc}，参考 data/documents.json 中的文件说明，"
    f"针对 data/checkpoints.json 中的唯一审核点「{checkpoint.title}」生成一条 GovFinding。"
)
```

#### 5.6 工作底稿暂不展示附件列表

MVP 不修改 `_assemble_workpaper_draft` 和 `Workpaper` schema。原因：

- 工作底稿展示附件列表需要同步修改 `govdoc/schemas/workpaper.py`
- 前端 `WorkpaperPayload` 类型也要扩展
- docx 模板和 `finalize.py` markdown 输出也要改

本轮只保证附件参与审核和证据定位。附件列表展示后续单独迭代。

### 6. `govdoc/pipelines/pes_overrides.py`

qmd 可用时，agent 通过同一个 collection 检索主文书和附件。qmd 不可用时，现有 fallback 只读 `../data/tender.md`，需要改成包含附件：

在 auditor 的 `plan` 和 `execute` 阶段中，将现有 fallback 文本：

```text
如果 qmd 检索不可用，退回到 Read ../data/tender.md + Grep 搜索
```

替换为：

```text
如果 qmd 检索不可用，先 Read ../data/documents.json，再 Read ../data/tender.md 以及所有 ../data/supp_*.md，并用 Grep 搜索主文书和附件
```

两处都要改：

- `plan` 阶段：制定审核策略时需要能定位附件中的相关段落。
- `execute` 阶段：生成 finding 前需要能核实附件证据。

## 前端改动

`tenderDocs: Record<string, TenderDoc>` 的消费方要一次性改完，避免旧单文件状态和新多文件状态并存。需要同步检查：

| 文件 | 需要处理的点 |
| --- | --- |
| `frontend/src/context/V3WorkbenchContext.tsx` | 状态定义、初始化、上传写入、`createAuditRun` 签名 |
| `frontend/src/pages/AIReviewPage.tsx` | 从 context 读取当前项目输入包，传给上传面板，控制审核点选择器显示 |
| `frontend/src/hooks/useProjectWorkflow.ts` | 管理待上传主文书和附件文件，处理失败重试 |
| `frontend/src/hooks/useAuditRun.ts` | 从 `auditInputDocs` 读取 doc IDs，不再读取单个 `tenderDoc` |
| `frontend/src/components/TenderUploadPanel.tsx` | 展示主文书/附件两个上传区，以及已上传成功的 doc 列表 |

### 7. `frontend/src/api/v3.ts`

扩展 `createAuditRun`：

```ts
export function createAuditRun(
  projectId: string,
  tenderDocId: string,
  supplementaryDocIds: string[],
  checkpointIds: string[],
): Promise<{ audit_run_id: string; total_count: number; status: string }> {
  return request("/api/v1/audit/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      tender_doc_id: tenderDocId,
      supplementary_doc_ids: supplementaryDocIds,
      checkpoint_ids: checkpointIds,
    }),
  });
}
```

### 8. `frontend/src/types/ui.ts`

后端 `list_audit_runs` 和 `get_audit_run` 会返回附件 ID，前端 `AuditRun` 类型要同步增加字段：

```ts
export interface AuditRun {
  id: string;
  project_id: string;
  tender_doc_id: string;
  supplementary_doc_ids?: string[];
  status: AuditRunStatus;
  processed_count: number;
  total_count: number;
  error: string | null;
  created_at: string;
}
```

字段保持可选，兼容旧接口响应、测试 fixture 或历史 mock 数据。

### 9. `frontend/src/context/V3WorkbenchContext.tsx`

当前状态：

```ts
tenderDocs: Record<string, TenderDoc>;
```

只能保存每个项目一个文书，附件上传会覆盖之前的文书。改为按项目保存本次审核输入包：

```ts
export interface AuditInputDocs {
  mainDoc?: TenderDoc;
  supplementaryDocs: TenderDoc[];
}

auditInputDocs: Record<string, AuditInputDocs>;
```

上传成功后写入：

```ts
setAuditInputDocs((prev) => ({
  ...prev,
  [projectId]: {
    mainDoc,
    supplementaryDocs,
  },
}));
```

兼容说明：

- 页面刚加载或刷新后，项目下历史 `TenderDoc` 没有主/附件角色信息。
- MVP 可以保留现有 `listTenderDocs` 拉取逻辑作为“最近一个文书”的兼容展示，或不自动恢复主/附件选择。
- 本轮明确要求：上传完成后直接启动审核时，context 必须保留 `mainDoc + supplementaryDocs`。
- 历史审核输入恢复和重新选择主/附件，后续可用单独 UI 或持久化 draft 处理。

`createAuditRun` context 方法改为：

```ts
createAuditRun: (
  projectId: string,
  tenderDocId: string,
  supplementaryDocIds: string[],
  checkpointIds: string[],
) => Promise<{ audit_run_id: string }>;
```

调用 API 时传入附件 ID，并在本地新增的 `AuditRun` 对象中可选保存 `supplementary_doc_ids`。

### 10. `frontend/src/pages/AIReviewPage.tsx`

`AIReviewPage` 目前直接消费 `tenderDocs`，并把单个 `tenderDoc` 传给 `TenderUploadPanel`。多文件后这里也必须同步修改。

当前逻辑：

```ts
const tenderDoc = activeProject ? tenderDocs[activeProject.id] : undefined;
```

改为读取本次审核输入包：

```ts
const inputDocs = activeProject ? auditInputDocs[activeProject.id] : undefined;
const mainDoc = inputDocs?.mainDoc;
const supplementaryDocs = inputDocs?.supplementaryDocs ?? [];
```

传给 `TenderUploadPanel` 时区分“已上传成功的文书记录”和“用户当前选中的本地文件”：

```tsx
<TenderUploadPanel
  mainDoc={mainDoc}
  supplementaryDocs={supplementaryDocs}
  mainTenderFile={wf.mainTenderFile}
  setMainTenderFile={wf.setMainTenderFile}
  supplementaryFiles={wf.supplementaryFiles}
  setSupplementaryFiles={wf.setSupplementaryFiles}
  ...
/>
```

原先用 `tenderDoc` 判断是否显示审核点选择器，改为用 `mainDoc`：

```tsx
{mainDoc && !auditProgress && (
  <CheckpointPicker ... />
)}
```

需要同步清理 `AIReviewPage` 中对 `tenderDocs` 和 `tenderDoc` 的旧引用。

### 11. `frontend/src/hooks/useProjectWorkflow.ts`

将待上传文件状态从单文件改为主文件 + 附件：

```ts
mainTenderFile: File | null;
supplementaryFiles: File[];
setMainTenderFile: (file: File | null) => void;
setSupplementaryFiles: (files: File[]) => void;
```

上传流程需要区分“已上传成功的 `TenderDoc`”和“待上传的 `File`”。失败时不要清空文件状态；如果主文书已经上传成功，重试时应复用已有 `mainDoc`，避免重复创建主文书 `TenderDoc`。

推荐把上传组合封装在 context 方法中，例如 `uploadAuditInputDocs(projectId, mainFile, supplementaryFiles)`，由 context 保存部分成功结果。hook 侧流程可以是：

```ts
async function handleUploadTender(): Promise<void> {
  if (!activeProject || !mainTenderFile) return;
  setUploadingTender(true);
  try {
    await uploadAuditInputDocs(activeProject.id, mainTenderFile, supplementaryFiles);
    setMainTenderFile(null);
    setSupplementaryFiles([]);
  } finally {
    setUploadingTender(false);
  }
}
```

context 内部上传时应尽量复用已成功上传的部分：

```ts
const existing = auditInputDocs[projectId];
const mainDoc = existing?.mainDoc ?? await uploadTenderDoc(projectId, mainFile);
setAuditInputDocs((prev) => ({
  ...prev,
  [projectId]: { mainDoc, supplementaryDocs: existing?.supplementaryDocs ?? [] },
}));

const supplementaryDocs = [...(existing?.supplementaryDocs ?? [])];
for (const file of supplementaryFiles.slice(supplementaryDocs.length)) {
  const doc = await uploadTenderDoc(projectId, file);
  supplementaryDocs.push(doc);
  setAuditInputDocs((prev) => ({
    ...prev,
    [projectId]: { mainDoc, supplementaryDocs: [...supplementaryDocs] },
  }));
}
```

以上 `slice(supplementaryDocs.length)` 只适用于“附件列表未重新排序、未替换”的简单 MVP。若后续支持附件删除、重排、替换，应改成按本地文件指纹维护上传状态。

最低要求：

- 主文书上传成功但附件失败时，context 要保留 `mainDoc`。
- 重试时不要再次上传已经成功的主文书。
- 上传全部成功后再清空 `mainTenderFile` 和 `supplementaryFiles`。
- 如果要更精确地避免附件重复，后续可为每个本地附件维护上传状态或按文件名/大小/最后修改时间做匹配。

### 12. `frontend/src/components/TenderUploadPanel.tsx`

保持展示组件定位，状态通过 props 传入，不在组件内部持有核心状态。

props 从：

```ts
tenderFile: File | null;
setTenderFile: (f: File | null) => void;
```

改为：

```ts
mainDoc: TenderDoc | undefined;
supplementaryDocs: TenderDoc[];
mainTenderFile: File | null;
setMainTenderFile: (file: File | null) => void;
supplementaryFiles: File[];
setSupplementaryFiles: (files: File[]) => void;
```

这里要明确两组状态：

- `mainTenderFile` / `supplementaryFiles` 是用户选择但尚未上传的本地 `File`。
- `mainDoc` / `supplementaryDocs` 是已经上传成功、后端返回的 `TenderDoc`。

展示“已上传”状态时使用 `mainDoc` 和 `supplementaryDocs`，不要用 `File` 冒充后端文书记录。

界面拆成两个上传区：

```text
上传主招标文书
[ 单文件上传区 multiple=false ]

上传补充文件 / 变更公告 / 答疑纪要
[ 多文件上传区 multiple=true ]
```

交互要求：

- 没有主文书时，上传按钮 disabled 或不显示。
- 附件区可以为空。
- 主文书 chip 和附件 chip 分开展示。
- 附件多选时使用 `multiple`。
- 重新选择附件时可整体替换当前附件列表；如需追加/删除单个附件，后续可增强。

### 13. `frontend/src/hooks/useAuditRun.ts`

`useAuditRun` 不管理 `File` 对象，只读取已上传后的 doc IDs。

流程：

```ts
const inputDocs = activeProject ? auditInputDocs[activeProject.id] : undefined;
const mainDoc = inputDocs?.mainDoc;
const supplementaryDocIds = inputDocs?.supplementaryDocs.map((doc) => doc.id) ?? [];

if (!activeProject || !mainDoc || selectedCpIds.length === 0) return;

await createAuditRun(
  activeProject.id,
  mainDoc.id,
  supplementaryDocIds,
  selectedCpIds,
);
```

### 14. 结果页与工作底稿页展示兼容

当前 `AuditResultsPage` 和 `WorkpaperPage` 是全局选择 `AuditRun`，下拉项主要展示 run id 和状态，不按项目分组，也不展示主文书名和附件名。本轮多文件审核不强制改这两个页面，因为核心链路依赖的是 `audit_run_id`、`point_runs`、`finding_json` 和 `workpaper_json`，不会因为附件字段缺失展示而阻塞审核运行。

本轮只要求新建的 `AuditRun` 数据结构兼容附件。结果页和底稿页的展示优化放到后续迭代：

- 下拉项展示项目名、主文书名、附件数量或附件名。
- 切换历史 run 时主动加载对应 `AuditRunProgress`，避免显示旧的 `auditProgress`。
- 工作底稿元信息展示本次审核输入包。
- 证据展示中尽量显示来源文件名。

## 不改文件

| 文件 | 理由 |
| --- | --- |
| `govdoc/storage/files.py` | 已支持多文件存储和转换 |
| `govdoc/api/routes/projects.py` | 上传路由保持单文件，前端循环调用即可 |
| `agents/gov-auditor.yaml` | qmd-search 已接入，阶段 prompt 在 `pes_overrides.py` 调整 |
| `skills/gov-locate-evidence/SKILL.md` | MVP 不改 skill 指引 |
| `govdoc/schemas/workpaper.py` | MVP 不展示附件列表，避免扩大 schema 和模板改动面 |
| `govdoc/pipelines/finalize.py` | 工作底稿 final 输出暂不展示附件列表 |

## 测试与验证

### 1. DB 迁移

```bash
conda run -n govdoc-auditor-v3 alembic upgrade head
```

### 2. 后端测试

```bash
conda run -n govdoc-auditor-v3 python -m pytest tests/unit tests/contract -v
```

建议新增或更新测试：

- API 创建审核时校验主文书不存在、附件不存在、跨项目附件、重复附件、附件包含主文书。
- `list_audit_runs` 和 `get_audit_run` 返回 `supplementary_doc_ids`，空值返回 `[]`。
- `_ensure_tender_collection` 同时索引主文书和附件，主文书已存在时附件仍会添加。
- `_add_doc_to_collection` 遇到缺失 markdown 文件时记录 warning，不静默吞掉。
- `_run_single_point` 的 workspace `data_inputs` 包含 `tender.md`、`supp_0.md`、`documents.json`。
- `pes_overrides.py` 的 plan 和 execute fallback 文本都包含 `documents.json` 和 `supp_*.md`。
- replay 模式仍不触发真实 qmd。

### 3. 前端测试与构建

```bash
cd frontend && npm test && npm run build
```

建议新增或更新测试：

- 上传面板渲染主文书单文件区和附件多文件区。
- 只有主文书时可以上传；附件为空不阻塞。
- 上传主文书 + 多附件后 context 保存 `mainDoc + supplementaryDocs`。
- 主文书上传成功但附件失败后，重试不会重复上传主文书。
- `AIReviewPage` 从 `auditInputDocs` 读取 `mainDoc`，并用 `mainDoc` 控制 `CheckpointPicker` 显示。
- 启动审核时 API body 包含 `tender_doc_id` 和 `supplementary_doc_ids`。
- `AuditRun` 前端类型包含可选 `supplementary_doc_ids`，本地新增 run 时字段形状一致。

### 4. 手动端到端验证

1. 前端上传 1 个主招标文书 + 1 到 2 个附件。
2. 启动审核。
3. 检查 workspace `data/` 下存在：
   - `tender.md`
   - `supp_0.md`
   - `documents.json`
   - `checkpoints.json`
4. 检查 trajectory 中 plan 或 execute 阶段 qmd-search 能搜到附件内容。
5. 检查 qmd hit metadata 中附件包含：
   - `source`
   - `filename`
   - `source_type: "supplementary"`
6. 临时让 qmd 不可用时，确认 agent fallback prompt 会读取 `supp_*.md`。

## 已知限制

- 页面刷新后，本次未启动审核的主文书/附件角色不会可靠恢复，因为 `TenderDoc` 本身没有角色字段。
- 工作底稿 JSON、docx 和 final markdown 暂不展示附件列表。
- 附件与主文书条款冲突时，本轮只提供共同上下文，不实现自动版本优先级判定。
- 附件文件名只通过 `documents.json` 和 qmd metadata 暴露，`GovFinding.evidence_refs` 是否能反映来源取决于 agent 输出质量。

## 后续迭代候选

- 增加“审核输入草稿”持久化模型，保存上传后但未启动审核的主文书/附件角色。
- 工作底稿 schema 增加 `supplementary_doc_paths` 或 `source_documents`。
- UI 支持从项目历史文书中重新选择主文书和附件。
- 附件支持单个删除、重排、标注类型（变更公告、答疑纪要、补遗文件）。
- 对附件优先级建模，例如变更公告覆盖主文件同名条款。
