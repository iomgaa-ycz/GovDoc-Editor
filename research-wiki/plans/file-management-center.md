---
type: plan
node_id: plan:file-management-center
title: 文件预转换与文件管理中心实施计划
date: 2026-05-26
---

# 文件预转换与文件管理中心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将文件上传与使用解耦——建立文件管理中心，所有文件先上传转换，审核/对比时从已转换文件中选取。

**Architecture:** 新建 Document/Tag/DocumentTag 三张表替代 TenderDoc，合并双 DocumentStore 为单一 MinerU 实例，异步转换 + 虚拟进度条。前端新增文件管理页 + 文件选择器弹窗 + 标签管理组件，改造 AI 审核和文档对比页面为"选文件"模式。

**Tech Stack:** Python 3.11 / FastAPI / SQLModel / Alembic / React 18 / TypeScript / Tailwind / shadcn/ui

---

## File Map

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `govdoc/api/routes/documents.py` | Document CRUD + upload + reconvert API |
| `govdoc/api/routes/tags.py` | Tag CRUD API |

### Backend — Modified Files
| File | Change |
|------|--------|
| `govdoc/db/models.py` | +Document/Tag/DocumentTag; modify AuditRun/CompareRun; -TenderDoc |
| `govdoc/config.py` | AppConfig.ocr_backend default → "mineru" |
| `govdoc/runtime.py` | -`get_compare_document_store()` |
| `govdoc/storage/files.py` | Remove compare subdirs |
| `govdoc/api/main.py` | Register documents_router, tags_router |
| `govdoc/api/routes/audit.py` | tender_doc_id → main_document_id; validate Document |
| `govdoc/api/routes/compare.py` | Accept document_ids JSON; remove UploadFile |
| `govdoc/api/routes/projects.py` | -upload_tender_doc endpoint |
| `govdoc/compare/service.py` | Use single DocumentStore |
| `govdoc/pipelines/audit_tender.py` | TenderDoc → Document |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/api/documents.ts` | Document + Tag API client |
| `frontend/src/pages/FileManagementPage.tsx` | File management page |
| `frontend/src/components/FilePickerModal.tsx` | File picker modal |
| `frontend/src/components/TagPopover.tsx` | Tag management popover |
| `frontend/src/components/VirtualProgressBar.tsx` | Virtual progress bar |
| `frontend/src/components/UploadBar.tsx` | Persistent upload bar |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `frontend/src/types/ui.ts` | +Document/Tag; modify AuditRun; -TenderDoc |
| `frontend/src/App.tsx` | +`/files` route |
| `frontend/src/components/Sidebar.tsx` | 4→5 items; +文件管理 |
| `frontend/src/context/V3WorkbenchContext.tsx` | -uploadTenderDoc; change createAuditRun |
| `frontend/src/api/v3.ts` | -uploadTenderDoc(); change createAuditRun() |
| `frontend/src/api/compare.ts` | compareFiles→compareDocuments |
| `frontend/src/pages/AIReviewHubPage.tsx` | Drawer: FilePickerModal replaces upload |
| `frontend/src/pages/DocCompareHubPage.tsx` | FilePickerModal replaces upload |
| `frontend/src/pages/AIReviewDetailPage.tsx` | Document references |
| `frontend/src/pages/DashboardPage.tsx` | Stats adaptation |
| `frontend/src/adapters/backendToUi.ts` | -TenderDoc |

### Frontend — Delete
| File | Reason |
|------|--------|
| `frontend/src/components/FileDropzone.tsx` | Replaced by UploadBar |

---

### Task 1: Backend — Document / Tag / DocumentTag 数据模型

**Files:**
- Modify: `govdoc/db/models.py`
- Test: `tests/unit/test_document_models.py`

- [ ] **Step 1: Write the model test**

```python
# tests/unit/test_document_models.py
"""Document / Tag / DocumentTag 模型单元测试。"""
from datetime import datetime
import uuid

from govdoc.db.models import Document, Tag, DocumentTag


def test_document_defaults():
    """Document 创建后应有正确默认值。"""
    doc = Document(
        filename="test.pdf",
        file_type="pdf",
        file_size=1024,
        sha256="abc123",
        raw_path="/data/raw/test.pdf",
    )
    assert doc.id is not None
    assert doc.status == "uploading"
    assert doc.markdown_path is None
    assert doc.error_message is None
    assert isinstance(doc.created_at, datetime)
    assert isinstance(doc.updated_at, datetime)


def test_tag_defaults():
    """Tag 创建后应有 id 和 created_at。"""
    tag = Tag(name="测试标签", color="#DBEAFE:#1D4ED8")
    assert tag.id is not None
    assert tag.name == "测试标签"
    assert isinstance(tag.created_at, datetime)


def test_document_tag_association():
    """DocumentTag 关联记录可正常构造。"""
    doc_id = str(uuid.uuid4())
    tag_id = str(uuid.uuid4())
    dt = DocumentTag(document_id=doc_id, tag_id=tag_id)
    assert dt.document_id == doc_id
    assert dt.tag_id == tag_id
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_document_models.py -v
```
Expected: FAIL — `ImportError: cannot import name 'Document'`

- [ ] **Step 3: Add Document, Tag, DocumentTag models**

In `govdoc/db/models.py`, add after existing imports. Use `str` type for id (consistent with existing models which use `uid()` factory):

```python
class Document(SQLModel, table=True):
    """统一文件管理表，替代 TenderDoc。"""
    id: str = Field(default_factory=uid, primary_key=True)
    filename: str
    file_type: str
    file_size: int
    sha256: str
    raw_path: str
    markdown_path: str | None = None
    status: str = "uploading"
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Tag(SQLModel, table=True):
    """文件标签。"""
    id: str = Field(default_factory=uid, primary_key=True)
    name: str = Field(unique=True)
    color: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentTag(SQLModel, table=True):
    """Document ↔ Tag 多对多关联。"""
    document_id: str = Field(foreign_key="document.id", primary_key=True)
    tag_id: str = Field(foreign_key="tag.id", primary_key=True)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_document_models.py -v
```
Expected: PASS

- [ ] **Step 5: Modify AuditRun — rename tender_doc_id → main_document_id**

In `govdoc/db/models.py` AuditRun class (line 71):
```python
# Before:
tender_doc_id: str = Field(foreign_key="tenderdoc.id")
# After:
main_document_id: str = Field(foreign_key="document.id")
```

- [ ] **Step 6: Add document_ids field to CompareRun**

In `govdoc/db/models.py` CompareRun class, add after `file_names_json`:
```python
document_ids: str | None = None  # JSON list[str] of Document IDs
```

- [ ] **Step 7: Delete TenderDoc class**

Remove the entire `TenderDoc` class definition (lines 25-34) from `govdoc/db/models.py`.

- [ ] **Step 8: Run unit tests to check breakage scope**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --tb=short 2>&1 | head -60
```
Note: Some tests will fail from TenderDoc references — record for later tasks.

- [ ] **Step 9: Commit**

```bash
git add govdoc/db/models.py tests/unit/test_document_models.py
git commit -m "feat(db): add Document/Tag/DocumentTag models, remove TenderDoc"
```

---

### Task 2: Backend — Alembic 迁移脚本

**Files:**
- Create: `govdoc/db/migrations/versions/<auto>.py`

- [ ] **Step 1: Generate migration**

```bash
source activate govdoc-auditor-v3 && alembic revision --autogenerate -m "add document tag tables replace tenderdoc"
```

- [ ] **Step 2: Review and add data migration**

Open the generated file. Verify it contains CREATE for document/tag/documenttag, ALTER for auditrun, DROP for tenderdoc. Manually insert data migration between schema changes:

```python
# Inside upgrade(), after creating new tables and before dropping tenderdoc:
conn = op.get_bind()
rows = conn.execute(sa.text(
    "SELECT id, filename, storage_path, markdown_path, uploaded_at FROM tenderdoc"
)).fetchall()
for r in rows:
    ft = r.filename.rsplit(".", 1)[-1].lower() if "." in r.filename else "unknown"
    conn.execute(sa.text(
        "INSERT INTO document (id, filename, file_type, file_size, sha256, "
        "raw_path, markdown_path, status, created_at, updated_at) "
        "VALUES (:id, :fn, :ft, 0, '', :rp, :mp, 'ready', :ca, :ca)"
    ), {"id": r.id, "fn": r.filename, "ft": ft,
        "rp": r.storage_path, "mp": r.markdown_path, "ca": r.uploaded_at})
```

For AuditRun column rename, use `batch_alter_table` (required for SQLite):
```python
with op.batch_alter_table("auditrun") as batch_op:
    batch_op.alter_column("tender_doc_id", new_column_name="main_document_id")
```

- [ ] **Step 3: Apply migration**

```bash
source activate govdoc-auditor-v3 && alembic upgrade head
```

- [ ] **Step 4: Verify**

```bash
source activate govdoc-auditor-v3 && python -c "
from sqlmodel import create_engine, text
e = create_engine('sqlite:///./data/app.sqlite')
with e.connect() as c:
    tables = [r[0] for r in c.execute(text(\"SELECT name FROM sqlite_master WHERE type='table'\")).fetchall()]
    print('document' in tables, 'tag' in tables, 'documenttag' in tables, 'tenderdoc' not in tables)
"
```
Expected: `True True True True`

- [ ] **Step 5: Commit**

```bash
git add govdoc/db/migrations/
git commit -m "feat(db): migration — add document/tag tables, migrate tenderdoc data"
```

---

### Task 3: Backend — 存储层合并 & 配置更新

**Files:**
- Modify: `govdoc/config.py:28`
- Modify: `govdoc/runtime.py:38-48`
- Modify: `govdoc/storage/files.py`
- Test: `tests/unit/test_storage_merge.py`

- [ ] **Step 1: Write test**

```python
# tests/unit/test_storage_merge.py
"""验证 DocumentStore 合并为单一 MinerU 实例。"""
from govdoc.runtime import get_document_store
import govdoc.runtime as rt


def test_single_store_uses_mineru():
    store = get_document_store()
    assert store._ocr_backend == "mineru"


def test_no_compare_store():
    assert not hasattr(rt, "get_compare_document_store")
```

- [ ] **Step 2: Run test — expect fail**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_storage_merge.py -v
```

- [ ] **Step 3: Update config.py — ocr_backend default**

`govdoc/config.py` line ~28: `ocr_backend: str = "glm"` → `ocr_backend: str = "mineru"`

- [ ] **Step 4: Update runtime.py — delete get_compare_document_store**

Delete `get_compare_document_store()` (lines 44-48).

- [ ] **Step 5: Update storage/files.py — remove compare subdirs**

Remove creation of `compare/` and `compare_prepared/` in `__init__` if present.

- [ ] **Step 6: Run test — expect pass**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_storage_merge.py -v
```

- [ ] **Step 7: Commit**

```bash
git add govdoc/config.py govdoc/runtime.py govdoc/storage/files.py tests/unit/test_storage_merge.py
git commit -m "refactor(storage): merge DocumentStore to single MinerU instance"
```

---

### Task 4: Backend — Document API（上传 + CRUD + 批量标签）

**Files:**
- Create: `govdoc/api/routes/documents.py`
- Modify: `govdoc/api/main.py:118-125`
- Test: `tests/unit/test_document_api.py`

- [ ] **Step 1: Write API test**

```python
# tests/unit/test_document_api.py
"""Document API 路由单元测试。"""
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from govdoc.api.main import create_app

app = create_app()
client = TestClient(app)


def test_list_documents_empty():
    resp = client.get("/api/v1/documents/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_upload_document():
    with patch("govdoc.api.routes.documents.get_document_store") as ms:
        ms.return_value = MagicMock()
        ms.return_value.save_raw.return_value = "/tmp/raw/test.pdf"
        resp = client.post(
            "/api/v1/documents/upload",
            files=[("files", ("test.pdf", b"%PDF-fake", "application/pdf"))],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 1
        assert data[0]["filename"] == "test.pdf"
        assert data[0]["status"] in ("converting", "ready")
```

- [ ] **Step 2: Run test — expect fail (404)**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_document_api.py -v
```

- [ ] **Step 3: Create govdoc/api/routes/documents.py**

Full implementation with these endpoints:
- `POST /upload` — multipart, async convert via BackgroundTask, SHA256 dedup
- `GET /` — list with ?status, ?file_type, ?tag_id, ?q filters
- `GET /{doc_id}` — detail with tags
- `DELETE /{doc_id}` — delete doc + files + tag associations
- `POST /{doc_id}/reconvert` — reset status, re-trigger background convert
- `POST /batch-tag` — `{document_ids, tag_ids}`
- `DELETE /{doc_id}/tags/{tag_id}` — remove single tag

Key implementation details:
- `_convert_document(doc_id)` background task: calls `store.get_or_convert(raw_path)`, updates Document status
- SHA256 dedup: check existing Document with same hash before saving
- Tag queries: join DocumentTag + Tag tables

- [ ] **Step 4: Register router in main.py**

Add to `govdoc/api/main.py`:
```python
from govdoc.api.routes.documents import router as documents_router
app.include_router(documents_router)
```

- [ ] **Step 5: Run test — expect pass**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/test_document_api.py -v
```

- [ ] **Step 6: Commit**

```bash
git add govdoc/api/routes/documents.py govdoc/api/main.py tests/unit/test_document_api.py
git commit -m "feat(api): add document upload/CRUD/reconvert/batch-tag endpoints"
```

---

### Task 5: Backend — Tag API

**Files:**
- Create: `govdoc/api/routes/tags.py`
- Modify: `govdoc/api/main.py`

- [ ] **Step 1: Create tags.py**

Three endpoints:
- `GET /api/v1/tags/` — list all tags
- `POST /api/v1/tags/` — create tag `{name, color}`, 409 if duplicate name
- `DELETE /api/v1/tags/{id}` — delete tag + all DocumentTag associations

- [ ] **Step 2: Register in main.py**

```python
from govdoc.api.routes.tags import router as tags_router
app.include_router(tags_router)
```

- [ ] **Step 3: Commit**

```bash
git add govdoc/api/routes/tags.py govdoc/api/main.py
git commit -m "feat(api): add tag CRUD endpoints"
```

---

### Task 6: Backend — 修改 Audit API（TenderDoc → Document）

**Files:**
- Modify: `govdoc/api/routes/audit.py:34-129`
- Modify: `govdoc/pipelines/audit_tender.py`
- Modify: `govdoc/api/routes/projects.py:74-113`

- [ ] **Step 1: Update audit.py — request body and validation**

In `create_audit_run` handler:
1. Change `tender_doc_id` → `main_document_id` in request payload
2. Validate: `session.get(Document, payload.main_document_id)`, check `status == "ready"`
3. Supplementary: validate each as `Document` with `status == "ready"`
4. AuditRun creation: `main_document_id=payload.main_document_id`
5. Update imports: `Document` instead of `TenderDoc`

- [ ] **Step 2: Update audit_tender.py — TenderDoc → Document**

Global replace throughout file:
1. Import `Document` instead of `TenderDoc`
2. `_add_doc_to_collection(doc: TenderDoc)` → `_add_doc_to_collection(doc: Document)`
3. `_ensure_tender_collection(tender_doc: TenderDoc)` → `_ensure_tender_collection(tender_doc: Document)`
4. `_index_tender_doc(tender_doc: TenderDoc)` → `_index_tender_doc(tender_doc: Document)`
5. `session.get(TenderDoc, ...)` → `session.get(Document, ...)`
6. Attribute mapping: `storage_path` not used in pipeline (only `markdown_path`, `filename`, `id`), so no field name changes needed

- [ ] **Step 3: Remove upload_tender_doc from projects.py**

Delete the `upload_tender_doc` endpoint (lines 74-113). Remove `TenderDoc` import. Remove `listTenderDocs` if present.

- [ ] **Step 4: Run audit tests**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --tb=short -k "audit" 2>&1 | head -40
```

- [ ] **Step 5: Commit**

```bash
git add govdoc/api/routes/audit.py govdoc/api/routes/projects.py govdoc/pipelines/audit_tender.py
git commit -m "refactor(audit): replace TenderDoc with Document in audit pipeline"
```

---

### Task 7: Backend — 修改 Compare API（UploadFile → Document ID）

**Files:**
- Modify: `govdoc/api/routes/compare.py:140-193`
- Modify: `govdoc/compare/service.py:204-220`

- [ ] **Step 1: Update compare route**

Replace `compare_uploaded_files` with new handler accepting JSON body `{document_ids: [...]}`:
1. Validate ≥2 documents, all exist and `status == "ready"`
2. Create CompareRun with `document_ids` JSON field
3. Background task receives Document paths instead of uploaded bytes

- [ ] **Step 2: Update compare service — single DocumentStore**

In `govdoc/compare/service.py`:
```python
# Before:
from govdoc.runtime import get_compare_document_store
# After:
from govdoc.runtime import get_document_store
```
Replace all `get_compare_document_store()` calls with `get_document_store()`.

For already-converted documents (status=ready with markdown_path), the compare service can directly use the markdown_path instead of re-converting.

- [ ] **Step 3: Run compare tests**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --tb=short -k "compare" 2>&1 | head -40
```

- [ ] **Step 4: Commit**

```bash
git add govdoc/api/routes/compare.py govdoc/compare/service.py
git commit -m "refactor(compare): accept document_ids instead of file uploads"
```

---

### Task 8: Frontend — 类型定义 + API 客户端

**Files:**
- Modify: `frontend/src/types/ui.ts:124-143`
- Create: `frontend/src/api/documents.ts`
- Modify: `frontend/src/api/v3.ts:59-75, 155-171`
- Modify: `frontend/src/api/compare.ts:125-132`

- [ ] **Step 1: Update types/ui.ts**

Add after existing types:
```typescript
export type DocumentStatus = "uploading" | "converting" | "ready" | "failed";

export interface DocumentTag {
  id: string;
  name: string;
  color: string;
}

export interface GovDocument {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  sha256: string;
  raw_path: string;
  markdown_path: string | null;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  tags: DocumentTag[];
}

export interface Tag {
  id: string;
  name: string;
  color: string;
  created_at: string;
}
```

Remove `TenderDoc` interface (lines 124-130). Update `AuditRun` (lines 132-143):
```typescript
main_document_id: string;  // was tender_doc_id
```

- [ ] **Step 2: Create documents.ts**

Full API client with functions:
- `uploadDocuments(files: File[]): Promise<GovDocument[]>`
- `listDocuments(params?): Promise<GovDocument[]>`
- `getDocument(id): Promise<GovDocument>`
- `deleteDocument(id): Promise<void>`
- `reconvertDocument(id): Promise<{id, status}>`
- `batchTagDocuments(docIds, tagIds): Promise<{added}>`
- `removeDocumentTag(docId, tagId): Promise<void>`
- `listTags(): Promise<Tag[]>`
- `createTag(name, color): Promise<Tag>`
- `deleteTag(id): Promise<void>`

- [ ] **Step 3: Update v3.ts**

Delete `uploadTenderDoc()` (lines 59-69), `listTenderDocs()` (lines 71-75). Change `createAuditRun()`:
```typescript
export async function createAuditRun(
  projectId: string,
  mainDocumentId: string,
  supplementaryDocumentIds: string[],
  checkpointIds: string[],
)
```
Body: `{project_id, main_document_id, supplementary_document_ids, checkpoint_ids}`

- [ ] **Step 4: Update compare.ts**

Replace `compareFiles(files: File[])` with:
```typescript
export async function compareDocuments(documentIds: string[]): Promise<CompareSubmitResponse>
```
Body: `{document_ids: documentIds}`, method: POST, Content-Type: application/json.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/types/ui.ts src/api/documents.ts src/api/v3.ts src/api/compare.ts
git commit -m "feat(frontend): add Document/Tag types and API client"
```

---

### Task 9: Frontend — 共享组件

**Files:**
- Create: `frontend/src/components/VirtualProgressBar.tsx`
- Create: `frontend/src/components/UploadBar.tsx`
- Create: `frontend/src/components/TagPopover.tsx`
- Create: `frontend/src/components/FilePickerModal.tsx`

- [ ] **Step 1: VirtualProgressBar**

Props: `{createdAt: string, status: string}`. Renders thin blue progress bar. Progress formula: `1 - exp(-elapsed/1800)`, updates every 1s. Shows 100% when status=ready, hidden when not converting.

- [ ] **Step 2: UploadBar**

Props: `{onUpload: (files: File[]) => void, uploading?: boolean}`. Compact horizontal bar with cloud-upload icon, text "拖拽 PDF 或 Word 文件到此处上传", "选择文件" button. Drag-and-drop support. Reference: Screen/FileManagement upload zone.

- [ ] **Step 3: TagPopover**

Props: `{documentIds: string[], allTags: Tag[], documentTags: DocumentTag[], onToggleTag, onCreateTag}`. Popover with search input, checkbox list of tags (colored pills), "创建新标签" action at bottom. Reference: Component/TagPopover.

- [ ] **Step 4: FilePickerModal**

Props: `{open, onClose, onConfirm: (ids: string[]) => void, mode: "single"|"multi", initialSelected?: string[]}`. Dialog with search input, type filter chips (全部/PDF/Word), tag filter dropdown, scrollable file list with checkboxes, footer with count + cancel/confirm. Internally fetches `listDocuments({status: "ready"})` and `listTags()`. Reference: Modal/FilePicker.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/components/VirtualProgressBar.tsx src/components/UploadBar.tsx src/components/TagPopover.tsx src/components/FilePickerModal.tsx
git commit -m "feat(frontend): add VirtualProgressBar, UploadBar, TagPopover, FilePickerModal"
```

---

### Task 10: Frontend — FileManagementPage

**Files:**
- Create: `frontend/src/pages/FileManagementPage.tsx`

- [ ] **Step 1: Build page**

Page layout (reference: Screen/FileManagement + Screen/FileManagement-Empty):
1. Header: "文件管理" h1 + subtitle
2. UploadBar component (always visible)
3. Stats row: 4 MetricCard components — 总文件/已就绪/转换中/失败 (computed from doc list)
4. Filter bar: search input + type chips (全部/PDF/Word) + tag filter pills with ×
5. File table: checkbox column, filename (icon + name), type badge, size, tags (pills), status badge + VirtualProgressBar, date, actions (tag icon → TagPopover, trash → delete, refresh-cw → reconvert for failed)
6. Empty state: inbox icon + "暂无文件" + hint text (when filtered results empty)

State: `documents`, `tags`, `selectedIds`, `filters` (search, type, tagIds). Polling: 5s if any converting, else 30s.

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/pages/FileManagementPage.tsx
git commit -m "feat(frontend): add FileManagementPage"
```

---

### Task 11: Frontend — 改造 AI 审核（Drawer + Context）

**Files:**
- Modify: `frontend/src/context/V3WorkbenchContext.tsx`
- Modify: `frontend/src/pages/AIReviewHubPage.tsx`

- [ ] **Step 1: Update V3WorkbenchContext**

1. Remove `auditInputDocs` state, `handleUploadTenderDoc`, `uploadAuditInputDocs`, `resetProjectDocs`
2. Change `handleCreateAuditRun(projectId, tenderDocId, ...)` → `handleCreateAuditRun(projectId, mainDocumentId, ...)`
3. Remove all `TenderDoc` imports

- [ ] **Step 2: Rewrite drawer content in AIReviewHubPage**

Replace file upload sections with:
1. "招标文书" section: "选择招标文书" button → FilePickerModal(single). Selected doc shown as green card with file-check icon, filename, size, "更换" link
2. "补充文件" section: File list + "从文件库添加" button → FilePickerModal(multi). Each file row with × remove
3. Yellow hint: "没有找到需要的文件？请先到「文件管理」页面上传"
4. Submit: `createAuditRun(projectId, mainDocId, suppDocIds, checkpointIds)`

Reference: Screen/AIReview-Hub-V2-DrawerOpen

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/context/V3WorkbenchContext.tsx src/pages/AIReviewHubPage.tsx
git commit -m "refactor(frontend): AI review uses FilePickerModal instead of upload"
```

---

### Task 12: Frontend — 改造文档对比

**Files:**
- Modify: `frontend/src/pages/DocCompareHubPage.tsx`

- [ ] **Step 1: Replace upload with file picker**

1. Remove `files: File[]` state + FileDropzone usage
2. Add `selectedDocIds: string[]` and `selectedDocs: GovDocument[]` state
3. "从文件库添加" button → FilePickerModal(multi)
4. Selected files as cards (filename, size, tag pills, × remove)
5. Submit: `compareDocuments(selectedDocIds)`
6. Empty state: git-compare-arrows icon + "从文件库选择文件" button

Reference: Screen/DocCompare-Hub-V2 + Screen/DocCompare-Hub-V2-Empty

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/pages/DocCompareHubPage.tsx
git commit -m "refactor(frontend): doc compare uses FilePickerModal"
```

---

### Task 13: Frontend — 导航 + 路由 + 清理

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/AIReviewDetailPage.tsx`
- Modify: `frontend/src/adapters/backendToUi.ts`
- Delete: `frontend/src/components/FileDropzone.tsx`

- [ ] **Step 1: Update Sidebar — 5 items**

```typescript
const navItems = [
  { to: "/", label: "工作台总览", icon: LayoutDashboard },
  { to: "/files", label: "文件管理", icon: HardDrive },
  { to: "/audit-library", label: "审核点库", icon: LibraryBig },
  { to: "/ai-review", label: "AI 审核", icon: Bot },
  { to: "/compare", label: "文档对比", icon: GitCompareArrows },
];
```
Add `import { HardDrive } from "lucide-react"`.

- [ ] **Step 2: Update App.tsx**

```typescript
import FileManagementPage from "./pages/FileManagementPage";
// Add route:
<Route path="/files" element={<FileManagementPage />} />
```

- [ ] **Step 3: Update AIReviewDetailPage**

Replace `tender_doc_id` references with `main_document_id`.

- [ ] **Step 4: Update backendToUi.ts**

Remove TenderDoc parsing. Keep `WorkpaperPayload.tender_doc_path` as-is (template field name, not a DB FK).

- [ ] **Step 5: Delete FileDropzone.tsx**

```bash
rm frontend/src/components/FileDropzone.tsx
```

- [ ] **Step 6: TypeScript build check**

```bash
cd frontend && npx tsc --noEmit
```
Fix all compile errors.

- [ ] **Step 7: Commit**

```bash
cd frontend && git add -A
git commit -m "refactor(frontend): update nav/routes, cleanup TenderDoc references"
```

---

### Task 14: 集成验证

- [ ] **Step 1: Full backend test suite**

```bash
source activate govdoc-auditor-v3 && python -m pytest tests/unit/ -v --tb=short 2>&1 | tail -30
```
Fix remaining failures.

- [ ] **Step 2: Frontend test suite**

```bash
cd frontend && npm run test
```
Fix remaining failures.

- [ ] **Step 3: Lint + format**

```bash
source activate govdoc-auditor-v3 && ruff format . && ruff check . --fix
```

- [ ] **Step 4: Manual E2E verification**

Start backend (port 8002) + frontend (port 5173). Verify:
1. ✅ 文件管理页：上传 PDF → 转换中 + 进度条 → 就绪
2. ✅ 文件管理页：创建标签 → 打标签 → 按标签筛选
3. ✅ AI 审核：新建 → 选主文件 → 选补充文件 → 开始
4. ✅ 文档对比：选文件 → 开始对比
5. ✅ 导航栏：5 项，高亮正确

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "test: fix remaining failures after file management refactor"
```
