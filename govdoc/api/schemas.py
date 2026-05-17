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


class CreateAuditRunRequest(GovDocModel):
    project_id: str
    tender_doc_id: str
    created_by: str = "system"
    supplementary_doc_ids: list[str] = Field(default_factory=list)
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
