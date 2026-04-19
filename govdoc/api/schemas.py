"""FastAPI 请求/响应契约。

这些 schema 只定义 API 形状，不替代 `govdoc.schemas` 的领域模型。
"""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, Field

from govdoc.schemas import GovDocModel, Workpaper


class HealthzResponse(GovDocModel):
    status: str


class CreateProjectRequest(GovDocModel):
    name: str
    created_by: str


class ExtractRunStatusResponse(GovDocModel):
    run_id: str
    status: str
    workspace_archive_path: str | None = None
    workspace_failed_path: str | None = None
    error: str | None = None


class UpdateCheckpointRequest(GovDocModel):
    payload_json: str


class CreateAuditRunRequest(GovDocModel):
    project_id: str
    tender_doc_id: str
    checkpoint_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("checkpoint_ids", "checkpoint_final_ids"),
    )


class UpdateWorkpaperDraftRequest(GovDocModel):
    workpaper: Workpaper


class FinalizeWorkpaperRequest(GovDocModel):
    approved_by: str


class AuditRunProgressResponse(GovDocModel):
    audit_run_id: str
    status: str
    total_count: int = 0
    processed_count: int = 0
    point_runs: list[dict[str, Any]] = Field(default_factory=list)


class GenericMessageResponse(GovDocModel):
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class ImportCheckpointsResponse(GovDocModel):
    """审查点表格导入响应。"""

    imported_count: int
    skipped_count: int
    skipped_reasons: list[str] = Field(default_factory=list)
    drafts: list[dict[str, str | None]] = Field(default_factory=list)
