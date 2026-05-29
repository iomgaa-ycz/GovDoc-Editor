"""GovDoc SQLModel 数据模型。

设计基线：`docs/design.md` §5。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def uid() -> str:
    return uuid.uuid4().hex


class Project(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str


class RuleSource(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    title: str
    source_path: str
    rule_library_entry_id: str
    added_at: datetime = Field(default_factory=datetime.utcnow)


class CheckpointFinal(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    payload_json: str
    approved_by: str
    approved_at: datetime = Field(default_factory=datetime.utcnow)
    # active = 正常可用；archived = 被审查任务引用但用户已"删除"
    status: str = "active"


class CheckpointLibrary(SQLModel, table=True):
    """审核点库——将审核点组织到可复用的集合中。"""

    id: str = Field(default_factory=uid, primary_key=True)
    name: str
    description: str | None = None
    created_by: str = "system"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CheckpointLibraryItem(SQLModel, table=True):
    """审核点库与审核点的多对多关联。"""

    __table_args__ = (
        UniqueConstraint(
            "library_id",
            "checkpoint_final_id",
            name="uq_checkpointlibraryitem_library_checkpoint",
        ),
    )

    id: str = Field(default_factory=uid, primary_key=True)
    library_id: str = Field(foreign_key="checkpointlibrary.id")
    # 不加 foreign_key：审核点被删除后关联记录保留，用于展示"已删除"状态
    checkpoint_final_id: str
    added_by: str = "system"
    added_at: datetime = Field(default_factory=datetime.utcnow)


class ExtractRun(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    rule_source_id: str = Field(foreign_key="rulesource.id")
    # pending / running / draft_ready / completed / failed / interrupted
    status: str = "pending"
    workspace_archive_path: str | None = None
    workspace_failed_path: str | None = None
    total_usage_json: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    heartbeat_at: datetime | None = None
    started_at: datetime | None = None
    current_phase: str | None = None


class AuditRun(SQLModel, table=True):
    """管道 B 的一次整体执行——编排多个 AuditPointRun。"""

    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    main_document_id: str = Field(foreign_key="document.id")
    supplementary_doc_ids: str | None = None  # JSON list[str]，附件文书 ID
    checkpoint_final_ids: str  # JSON list[str]
    checkpoint_library_id: str | None = None
    checkpoint_library_name_snapshot: str | None = None
    # pending / running / partial_ready / draft_ready / finalized / failed / waiting_retry / cancelled / interrupted
    status: str = "pending"
    processed_count: int = 0
    total_count: int = 0
    workspace_archive_path: str | None = None
    workspace_failed_path: str | None = None
    total_usage_json: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    heartbeat_at: datetime | None = None
    created_by: str | None = None


class AuditPointRun(SQLModel, table=True):
    """管道 B 中单个审核点的执行——对应一个独立 workspace。"""

    id: str = Field(default_factory=uid, primary_key=True)
    audit_run_id: str = Field(foreign_key="auditrun.id")
    checkpoint_final_id: str = Field(foreign_key="checkpointfinal.id")
    # pending / running / completed / failed / waiting_retry
    status: str = "pending"
    workspace_archive_path: str | None = None
    workspace_failed_path: str | None = None
    usage_json: str | None = None
    error: str | None = None
    finding_json: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    started_at: datetime | None = None
    # plan / execute / summarize — PES 当前阶段
    current_phase: str | None = None


class WorkpaperDraft(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    audit_run_id: str = Field(foreign_key="auditrun.id")
    workpaper_json: str
    docx_path: str
    version: int = 1


class WorkpaperFinal(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    audit_run_id: str = Field(foreign_key="auditrun.id")
    workpaper_json: str
    docx_path: str
    approved_by: str
    approved_at: datetime = Field(default_factory=datetime.utcnow)
    case_library_entry_id: str | None = None


class ActivityLog(SQLModel, table=True):
    """操作审计日志——记录所有用户操作的 before/after。"""

    id: str = Field(default_factory=uid, primary_key=True)
    actor: str
    action: (
        str  # upload_tender_doc / create_audit_run / update_checkpoint / delete_checkpoint / ...
    )
    target_type: str  # Document / AuditRun / CheckpointFinal / WorkpaperDraft / ...
    target_id: str
    before_json: str | None = None
    after_json: str | None = None
    request_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CompareRun(SQLModel, table=True):
    """文档对比任务执行记录。"""

    id: str = Field(default_factory=uid, primary_key=True)
    status: str = "pending"  # pending / running / completed / failed
    file_count: int = 0
    file_names_json: str | None = None  # JSON list[str]
    document_ids: str | None = None
    progress_json: str | None = None  # JSON: {"phase": "matching", "step": "paragraph"}
    result_path: str | None = None  # review.json 路径
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


class Comment(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    target_type: str
    target_id: str
    author: str
    text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    username: str
    display_name: str
    role: str = "reviewer"


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
    """Document 与 Tag 的多对多关联。"""

    document_id: str = Field(foreign_key="document.id", primary_key=True)
    tag_id: str = Field(foreign_key="tag.id", primary_key=True)
