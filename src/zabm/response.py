from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


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
    code: Literal["not_found"]
    message: str


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


class CanonicalResponse(BaseModel):
    request_id: str
    timestamp: datetime
    response_type: Literal["specification", "compatibility"]
    language: Literal["en"]
    status: Literal["supported", "not_found"]
    failure: Failure | None = None
    claims: list[Claim] = Field(default_factory=list[Claim])
    specification: SpecificationAnswer | None = None
    compatibility: CompatibilityAnswer | None = None
    citations: list[StoredCitation] = Field(default_factory=list[StoredCitation])
    source_pack_id: str
