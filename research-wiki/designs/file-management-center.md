---
type: design
node_id: design:file-management-center
title: 文件预转换与文件管理中心架构改造
date: 2026-05-26
---

# 文件预转换与文件管理中心架构改造

## 1. 背景与动机

招标文书常达 1000+ 页，当前"即用即转"模式导致审核/对比时等待过长。文件存储碎片化：审核走 `TenderDoc` 表 + `DocumentStore(glm)`，对比走独立目录 + `DocumentStore(mineru)`，两条路径互不相通。

**核心改变**：文件上传与使用解耦——先上传转换，后选择使用。

## 2. 决策记录

| 决策点 | 选择 | 理由 |
|---|---|---|
| 文件与 Project 关系 | 完全独立，标签组织 | 一个文件可在多个审核任务中复用 |
| OCR 后端 | 统一 MinerU | 本地执行，不依赖网络/代理，速度更快 |
| DocumentStore 实例 | 合并为一个 | 统一 OCR 后端后无需双实例 |
| TenderDoc 表 | 删除，替换为 Document | 不保留向后兼容 |
| Project 概念 | 保留，作为 AuditRun 分组 | 律师按案件分组管理审核任务 |
| 进度反馈 | 虚拟进度条（60min 渐进） | 无法获取 MinerU 真实进度 |
| 交付方式 | 一次性全部改完 | 避免新旧并存的复杂性 |

**否决方案**：渐进式改造（保留双 DocumentStore + 旧表并存）——增加长期维护成本，与"不要增量式改动"原则矛盾。

## 3. 数据模型

### 3.1 新建表

```python
class Document(SQLModel, table=True):
    """统一文件管理表，替代 TenderDoc。"""
    id: uuid.UUID
    filename: str               # 原始文件名
    file_type: str              # "pdf" | "docx" | "doc"
    file_size: int              # 字节数
    sha256: str                 # 内容哈希（去重）
    raw_path: str               # 原始文件路径
    markdown_path: str | None   # 转换后 Markdown 路径
    status: str                 # "uploading" | "converting" | "ready" | "failed"
    error_message: str | None   # 失败原因
    created_at: datetime
    updated_at: datetime

class Tag(SQLModel, table=True):
    """文件标签。"""
    id: uuid.UUID
    name: str                   # UNIQUE
    color: str                  # "bg_hex:text_hex" 如 "#DBEAFE:#1D4ED8"
    created_at: datetime

class DocumentTag(SQLModel, table=True):
    """Document ↔ Tag 多对多关联。"""
    document_id: uuid.UUID      # FK → Document
    tag_id: uuid.UUID           # FK → Tag
```

### 3.2 修改表

```python
class AuditRun:
    project_id: uuid.UUID           # FK → Project（保留）
    main_document_id: uuid.UUID     # FK → Document（替代 tender_doc_id）
    supplementary_document_ids: str  # JSON [doc_id, ...]（改为 Document ID）

class CompareRun:
    document_ids: str               # JSON [doc_id, ...]（新增）
```

### 3.3 删除表

- `TenderDoc` — 由 `Document` 完全替代

### 3.4 迁移策略

Alembic 迁移脚本：
1. 创建 Document / Tag / DocumentTag 表
2. 将 TenderDoc 数据迁移至 Document（status=ready）
3. 更新 AuditRun 外键（tender_doc_id → main_document_id）
4. 删除 TenderDoc 表

## 4. 存储层

### 4.1 DocumentStore 合并

- 删除 `get_compare_document_store()`，保留单个 `get_document_store()`
- OCR 后端固定为 `mineru`
- 存储结构：`storage_root/raw/` + `storage_root/prepared/{sha256}.md`
- 删除 `compare/` 和 `compare_prepared/` 子目录

### 4.2 异步转换流程

```
POST /documents/upload（multipart，支持多文件）
  1. 保存原始文件至 raw/
  2. 计算 SHA256，检查去重
     └─ 已存在 → 复用 markdown_path，status = ready
  3. 写入 Document 记录（status = converting）
  4. 提交 BackgroundTask 执行转换
  5. 立即返回 [{id, filename, status}, ...]

BackgroundTask:
  ├─ document_store.get_or_convert(raw_path)
  ├─ 成功 → Document.markdown_path = path, status = ready
  └─ 失败 → Document.status = failed, error_message = str(e)
```

### 4.3 虚拟进度条

前端根据 `created_at` 和当前时间计算：

```typescript
const elapsed = (Date.now() - createdAt) / 1000;
const progress = 1 - Math.exp(-elapsed / 1800); // 1800s = 30min 半衰期
// status === "ready" 时直接显示 100%
```

轮询策略：前 5 分钟每 5s，之后每 30s。

## 5. API 设计

### 5.1 新增路由

**`/api/v1/documents/`**

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/upload` | 上传文件（multipart 多文件） |
| GET | `/` | 列表。`?status=ready&tag_id=x&file_type=pdf&q=keyword` |
| GET | `/{id}` | 单个文档详情（含标签列表） |
| DELETE | `/{id}` | 删除文档 + 清理文件 |
| POST | `/{id}/reconvert` | 重新转换（重置 status） |
| POST | `/batch-tag` | 批量打标签 `{document_ids, tag_ids}` |
| DELETE | `/{id}/tags/{tag_id}` | 移除标签 |

**`/api/v1/tags/`**

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 所有标签 |
| POST | `/` | 创建标签 `{name, color}` |
| DELETE | `/{id}` | 删除标签 |

### 5.2 修改路由

| 原接口 | 变化 |
|---|---|
| `POST /projects/{pid}/tender-doc` | **删除** |
| `POST /audit-runs/` | body: `{project_id, main_document_id, supplementary_document_ids, checkpoint_ids}` |
| `POST /compare/` | body: `{document_ids}` 替代 `files: UploadFile[]` |

## 6. 前端改造

### 6.1 导航

5 项：工作台总览 → 文件管理 → 审核点库 → AI 审核 → 文档对比

### 6.2 新增文件（6 个）

| 文件 | 说明 |
|---|---|
| `pages/FileManagementPage.tsx` | 常驻上传区 + 统计卡片 + 筛选栏 + 文件表格 |
| `components/FilePickerModal.tsx` | 文件选择弹窗（搜索/类型/标签筛选/单选或多选） |
| `components/TagPopover.tsx` | 标签管理（搜索/创建/勾选） |
| `components/VirtualProgressBar.tsx` | 虚拟进度条 |
| `components/UploadBar.tsx` | 文件管理页常驻拖拽上传区 |
| `api/documents.ts` | Document + Tag API 客户端 |

### 6.3 修改文件（12 个）

| 文件 | 改动 |
|---|---|
| `App.tsx` | +`/files` 路由，-`/workpaper` `-/audit-results` 独立路由 |
| `Sidebar.tsx` | 6→5 项，+文件管理，-审核结果 -工作底稿 |
| `V3WorkbenchContext.tsx` | -uploadTenderDoc；+documents/tags 状态；改 createAuditRun 参数 |
| `api/v3.ts` | -uploadTenderDoc()；改 createAuditRun()；-listTenderDocs() |
| `api/compare.ts` | compareFiles→compareDocuments(ids[]) |
| `types/ui.ts` | +Document/Tag 类型；改 AuditRun；-TenderDoc 类型 |
| `AIReviewHubPage.tsx` | 文档名从 Document 获取 |
| `AIReviewDrawer.tsx` | 删上传区→FilePickerModal；+提示"去文件管理上传" |
| `AIReviewDetailPage.tsx` | 文档引用→Document |
| `DocCompareHubPage.tsx` | 删上传区→FilePickerModal；+文件卡片展示 |
| `DocCompareDetailPage.tsx` | 文件引用→Document ID |
| `DashboardPage.tsx` | 统计接口适配 Document |
| `backendToUi.ts` | -TenderDoc 适配；+Document 解析 |

### 6.4 删除

- `FileDropzone.tsx`（上传能力迁移到 UploadBar）

## 7. 视觉设计

Pencil 设计稿：`pencil/pencil-new.pen`

已完成 15 个屏幕 + 5 个组件/弹窗的完整设计，包含所有页面状态（空/有数据）。
