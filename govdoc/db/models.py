"""GovDoc SQLModel 数据模型。

设计基线：`docs/design.md` §5。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def uid() -> str:
    return uuid.uuid4().hex


class Project(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str


class TenderDoc(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    filename: str
    storage_path: str
    markdown_path: str
    qmd_collection: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class RuleSource(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    title: str
    source_path: str
    rule_library_entry_id: str
    added_at: datetime = Field(default_factory=datetime.utcnow)


class CheckpointDraft(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    rule_source_id: str | None = Field(default=None, foreign_key="rulesource.id")
    payload_json: str
    extract_run_id: str | None = Field(default=None)
    status: str = "draft"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CheckpointFinal(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    payload_json: str
    approved_by: str
    approved_at: datetime = Field(default_factory=datetime.utcnow)


class ExtractRun(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    rule_source_id: str = Field(foreign_key="rulesource.id")
    status: str = "pending"
    workspace_archive_path: str | None = None
    workspace_failed_path: str | None = None
    total_usage_json: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditRun(SQLModel, table=True):
    """管道 B 的一次整体执行——编排多个 AuditPointRun。"""

    id: str = Field(default_factory=uid, primary_key=True)
    project_id: str = Field(foreign_key="project.id")
    tender_doc_id: str = Field(foreign_key="tenderdoc.id")
    supplementary_doc_ids: str | None = None  # JSON list[str]，附件文书 ID
    checkpoint_final_ids: str  # JSON list[str]
    # pending / running / partial_ready / draft_ready / finalized / failed / waiting_retry
    status: str = "pending"
    processed_count: int = 0
    total_count: int = 0
    workspace_archive_path: str | None = None
    workspace_failed_path: str | None = None
    total_usage_json: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


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
