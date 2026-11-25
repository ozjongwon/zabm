from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

EvidenceIntent = Literal["specification", "compatibility", "procedure", "out_of_scope"]


class ProviderIdentity(BaseModel):
    provider: str
    model: str
    embedding_model: str
    configuration: str


class RouteEntity(BaseModel):
    kind: Literal[
        "manufacturer",
        "model",
        "component",
        "attribute",
        "side",
        "task",
        "component_a",
        "component_b",
        "other",
    ]
    text: str = Field(min_length=1, max_length=200)


class RoutingMetadata(BaseModel):
    routing_version: str
    strategy: Literal["model", "prototype"]
    intent: Literal[
        "specification",
        "compatibility",
        "procedure",
        "out_of_scope",
        "ambiguous",
    ]
    normalized_question: str = Field(min_length=1, max_length=1000)
    entities: list[RouteEntity] = Field(
        default_factory=list[RouteEntity],
        max_length=32,
    )
    missing_fields: list[str] = Field(default_factory=list[str], max_length=20)
    ambiguous_fields: list[str] = Field(default_factory=list[str], max_length=20)
    candidate_intents: list[EvidenceIntent] = Field(
        default_factory=list[EvidenceIntent],
        max_length=4,
    )


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


class ProcedureMatchProvenance(BaseModel):
    basis: Literal["literal-title", "action-alias"]
    canonical_action: str | None = None
    heading_action: str | None = None
    question_action: str | None = None
    profile_id: str
    profile_version: str


class ProcedureAnswer(BaseModel):
    title: str
    heading_path: list[str]
    steps: list[ProcedureStep]
    match: ProcedureMatchProvenance | None = None


class LocalizationMetadata(BaseModel):
    requested_language: Literal["en", "ko"]
    active_language: Literal["en", "ko"]
    status: Literal["translated", "disabled", "fallback"]
    review_id: str | None = None
    reason: str | None = None


class LocalizedClaim(BaseModel):
    claim_id: str
    text: str


class LocalizedProcedureStep(BaseModel):
    number: int
    text: str
    warnings: list[ProcedureWarning]


class LocalizedProcedure(BaseModel):
    title: str
    steps: list[LocalizedProcedureStep]


class LocalizedAnswer(BaseModel):
    claims: list[LocalizedClaim]
    conditions: list[str]
    procedure: LocalizedProcedure | None = None
    clarification_message: str | None = None
    failure_message: str | None = None


class CanonicalResponse(BaseModel):
    request_id: str
    timestamp: datetime
    response_type: Literal[
        "specification",
        "compatibility",
        "procedure",
        "out_of_scope",
        "ambiguous",
    ]
    language: Literal["en", "ko"]
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
    routing: RoutingMetadata | None = None
    source_pack_id: str
    localization: LocalizationMetadata | None = None
    localized: LocalizedAnswer | None = None
