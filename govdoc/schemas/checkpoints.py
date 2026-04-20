"""GovDoc 审核点与发现领域模型。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field
from scrivai import ChunkRef

from govdoc.schemas.common import GovDocModel


class CheckpointCategory(StrEnum):
    INTENTIONAL_BIDDING = "意向性招标"
    COLLUSION = "围标串标"
    UNREASONABLE_RESTRICTION = "不合理条件限制或排斥供应商"
    OTHER = "其他违法违规"


class Severity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class VerdictValue(StrEnum):
    COMPLIANT = "合规"
    NON_COMPLIANT = "不合规"
    UNCERTAIN = "存疑"


class LegalBasis(GovDocModel):
    law_name: str
    article: str
    quote: str


class GovCheckpoint(GovDocModel):
    id: str
    category: CheckpointCategory
    title: str
    description: str
    legal_basis: list[LegalBasis] = Field(default_factory=list)
    severity: Severity
    retrieval_hint: str


class GovFindingVerdict(GovDocModel):
    verdict: VerdictValue
    rationale: str
    evidence_quotes: list[str] = Field(default_factory=list)
    suggestion: str = ""


class GovFinding(GovDocModel):
    checkpoint: GovCheckpoint
    verdict: GovFindingVerdict
    evidence_refs: list[ChunkRef] = Field(default_factory=list)
    case_refs: list[str] = Field(default_factory=list)
