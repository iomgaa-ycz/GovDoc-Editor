"""PES summarize 阶段输出 schema。"""

from __future__ import annotations

from pydantic import Field

from govdoc.schemas.checkpoints import GovCheckpoint, GovFinding
from govdoc.schemas.common import GovDocModel


class CheckpointListOutput(GovDocModel):
    checkpoints: list[GovCheckpoint] = Field(default_factory=list)


class WorkpaperAuditOutput(GovDocModel):
    findings: list[GovFinding] = Field(default_factory=list)
    summary: str
