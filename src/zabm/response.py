from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProviderIdentity(BaseModel):
    provider: str
    model: str
    embedding_model: str
    configuration: str


DEFAULT_PROVIDER_IDENTITY = ProviderIdentity(
    provider="local-deterministic",
    model="evidence-renderer-v1",
    embedding_model="canonical-alias-index-v1",
    configuration="offline-v1",
)


def default_provider_identity() -> ProviderIdentity:
    return DEFAULT_PROVIDER_IDENTITY.model_copy()


class SpecificationValue(BaseModel):
    minimum: float
    maximum: float | None = None
    unit: str
    display: str


class StoredCitation(BaseModel):
    document_id: str
    title: str
    manufacturer: str
    printed_page: int
    physical_page: int
    section: str
    retrieval_date: date
    source_manifest_version: str


class Failure(BaseModel):
    code: Literal["not_found", "conflicting_evidence", "out_of_scope"]
    message: str


class Clarification(BaseModel):
    message: str
    missing_information: list[str]


class Claim(BaseModel):
    claim_id: str
    text: str
    evidence_ids: list[str]


class SpecificationAnswer(BaseModel):
    manufacturer: str
    model: str
    component: str
    attribute: str
    value: SpecificationValue
    conditions: list[str]


class CompatibilityComponent(BaseModel):
    manufacturer: str
    name: str
    aliases: list[str] = Field(default_factory=list[str])


class CompatibilityAnswer(BaseModel):
    outcome: Literal["compatible", "not_compatible", "unknown", "not_found"]
    component_a: CompatibilityComponent | None
    component_b: CompatibilityComponent | None
    conditions: list[str]


class ConflictCandidate(BaseModel):
    claim_id: str
    claim: str
    evidence_ids: list[str]
    excerpts: list[str]
    citations: list[StoredCitation] = Field(min_length=1)
    selected: bool = False


class PrecedenceDecision(BaseModel):
    kind: Literal["model_scope", "supersession", "revision_date", "manufacturer_scope"]
    reason: str
    supersedes: list[str]
    excerpt: str
    citation: StoredCitation


class ConflictReport(BaseModel):
    candidates: list[ConflictCandidate] = Field(min_length=2)
    precedence_established: bool = False
    precedence: PrecedenceDecision | None = None
    selected_claim_id: str | None = None
    rejected_claim_ids: list[str] = Field(default_factory=list[str])


class ProcedureWarning(BaseModel):
    severity: Literal["warning", "notice"]
    text: str


class ProcedureStep(BaseModel):
    number: int
    text: str
    warnings: list[ProcedureWarning] = Field(default_factory=list[ProcedureWarning])
    citation: StoredCitation


class ProcedureAnswer(BaseModel):
    title: str
    heading_path: list[str]
    steps: list[ProcedureStep]


class CanonicalResponse(BaseModel):
    request_id: str
    timestamp: datetime
    response_type: Literal["specification", "compatibility", "procedure", "out_of_scope"]
    language: Literal["en"]
    status: Literal[
        "supported",
        "clarification_required",
        "not_found",
        "conflicting_evidence",
        "out_of_scope",
    ]
    failure: Failure | None = None
    clarification: Clarification | None = None
    claims: list[Claim] = Field(default_factory=list[Claim])
    specification: SpecificationAnswer | None = None
    compatibility: CompatibilityAnswer | None = None
    procedure: ProcedureAnswer | None = None
    conflicts: ConflictReport | None = None
    citations: list[StoredCitation] = Field(default_factory=list[StoredCitation])
    provider: ProviderIdentity = Field(default_factory=default_provider_identity)
    source_pack_id: str
