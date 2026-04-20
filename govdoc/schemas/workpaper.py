"""GovDoc 工作底稿领域模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from govdoc.schemas.checkpoints import GovFinding
from govdoc.schemas.common import GovDocModel


class Workpaper(GovDocModel):
    project_id: str
    tender_doc_path: str
    findings: list[GovFinding] = Field(default_factory=list)
    summary: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    final: bool = False
