"""FastAPI 请求/响应契约。

这些 schema 只定义 API 形状，不替代 `govdoc.schemas` 的领域模型。
"""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, Field

from govdoc.schemas import GovDocModel, Workpaper


class CreateProjectRequest(GovDocModel):
    name: str
    created_by: str


class UpdateCheckpointRequest(GovDocModel):
    payload_json: str
    modified_by: str = "system"


class CreateCheckpointLibraryRequest(GovDocModel):
    name: str
    description: str | None = None
    created_by: str = "system"


class UpdateCheckpointLibraryRequest(GovDocModel):
    name: str | None = None
    description: str | None = None
    modified_by: str = "system"


class LibraryCheckpointIdsRequest(GovDocModel):
    checkpoint_ids: list[str] = Field(default_factory=list)
    actor: str = "system"


class BatchAddCheckpointsToLibrariesRequest(GovDocModel):
    library_ids: list[str] = Field(default_factory=list)
    checkpoint_ids: list[str] = Field(default_factory=list)
    actor: str = "system"


class CreateAuditRunRequest(GovDocModel):
    project_id: str
    main_document_id: str = Field(
        validation_alias=AliasChoices("main_document_id", "tender_doc_id")
    )
    created_by: str = "system"
    supplementary_document_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("supplementary_document_ids", "supplementary_doc_ids"),
    )
    checkpoint_library_id: str | None = None
    checkpoint_ids: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("checkpoint_ids", "checkpoint_final_ids"),
    )


class UpdateWorkpaperDraftRequest(GovDocModel):
    workpaper: Workpaper
    modified_by: str = "system"


class FinalizeWorkpaperRequest(GovDocModel):
    approved_by: str


class AuditRunProgressResponse(GovDocModel):
    audit_run_id: str
    status: str
    total_count: int = 0
    processed_count: int = 0
    point_runs: list[dict[str, Any]] = Field(default_factory=list)
