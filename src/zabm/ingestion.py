from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from datetime import date
from importlib.metadata import version as package_version
from itertools import pairwise
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

PARSER_VERSION = "pdf-ingestion-v8"
FONTTOOLS_VERSION = package_version("fonttools")
PYPDF_VERSION = package_version("pypdf")
PROFILE_SCHEMA_VERSION = "1"
SUPPORTED_PROFILE_VERSIONS = frozenset({"1"})
DEFAULT_INGESTION_PROFILES = (
    Path(__file__).resolve().parents[2] / "data" / "ingestion" / "profiles-v1.json"
)

PageKind = Literal[
    "cover",
    "contents",
    "index",
    "contact",
    "legal",
    "advertisement",
    "navigation",
    "table",
    "figure",
    "warning",
    "heading",
    "paragraph",
    "procedure-step",
    "unknown",
]
PageIngestionOutcome = Literal[
    "answer-eligible",
    "transcription-required",
    "transcription-verified",
    "excluded",
    "uncertain",
]
EvidencePlane = Literal["pdf-text", "verified-transcription"]
StepRejectionReason = Literal[
    "source-reference",
    "table-value",
    "figure-callout",
    "missing-action-text",
    "mixed-column",
    "missing-procedure-heading",
    "numbering-discontinuous",
    "non-procedure-block",
    "evidence-mismatch",
]
ReadingOrder = Literal["left-to-right", "right-to-left"]
EndBoundaryStrategy = Literal["explicit-marker", "section-boundary"]


class IngestionProfileError(ValueError):
    pass


def normalize_pdf_text(text: str) -> str:
    normalized_lines = [
        " ".join(unicodedata.normalize("NFKC", line).replace("\u00ad", "").split())
        for line in text.splitlines()
    ]
    joined = ""
    for line in normalized_lines:
        if not line:
            continue
        if (
            joined
            and joined.endswith("-")
            and len(joined) >= 2
            and joined[-2].isalpha()
            and line[0].islower()
        ):
            joined = f"{joined[:-1]}{line}"
        else:
            joined = f"{joined} {line}".strip()
    return " ".join(joined.split())


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RejectedStepCandidate(_ContractModel):
    line_id: str
    text: str
    reason: StepRejectionReason


class IngestionProfileReference(_ContractModel):
    id: str = Field(min_length=1)
    version: str = Field(min_length=1)


class ProfileSelector(_ContractModel):
    metadata: dict[str, str] = Field(default_factory=dict[str, str])
    fallback: bool = False

    @model_validator(mode="after")
    def validate_selector(self) -> ProfileSelector:
        if any(not key.strip() or not value.strip() for key, value in self.metadata.items()):
            raise ValueError("profile selector metadata keys and values must not be blank")
        if not self.fallback and not self.metadata:
            raise ValueError("a non-fallback profile selector requires metadata")
        if self.fallback and self.metadata:
            raise ValueError("a fallback profile selector cannot also require metadata")
        return self


class NormalizedBox(_ContractModel):
    x_min: float = Field(ge=0, le=1)
    y_min: float = Field(ge=0, le=1)
    x_max: float = Field(ge=0, le=1)
    y_max: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_extent(self) -> NormalizedBox:
        if self.x_max <= self.x_min:
            raise ValueError("x_max must be greater than x_min")
        if self.y_max <= self.y_min:
            raise ValueError("y_max must be greater than y_min")
        return self


class PageBox(_ContractModel):
    x_min: float = Field(ge=0)
    y_min: float = Field(ge=0)
    x_max: float = Field(gt=0)
    y_max: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_extent(self) -> PageBox:
        if self.x_max <= self.x_min:
            raise ValueError("page x_max must be greater than x_min")
        if self.y_max <= self.y_min:
            raise ValueError("page y_max must be greater than y_min")
        return self


class HumanTranscriptionVerification(_ContractModel):
    status: str = ""
    verified_by: str = ""
    verified_at: date | None = None


class TranscriptionSourceLocation(_ContractModel):
    physical_page: int = Field(ge=1)
    printed_page: int = Field(ge=1)
    section: str = Field(min_length=1)
    heading_path: list[str] = Field(min_length=1)
    box: PageBox


class TranscribedWarning(_ContractModel):
    severity: Literal["warning", "notice"]
    text: str = Field(min_length=1)


class TranscribedStep(_ContractModel):
    number: int = Field(ge=1)
    text: str = Field(min_length=1)
    source_box: PageBox
    warnings: list[TranscribedWarning] = Field(default_factory=list[TranscribedWarning])


class ProcedureTranscription(_ContractModel):
    id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    location: TranscriptionSourceLocation
    steps: list[TranscribedStep] = Field(min_length=1)
    end_boundary: str = Field(min_length=1)
    verification: HumanTranscriptionVerification

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) is None:
            raise ValueError(
                "transcription id must be lowercase alphanumeric words separated by hyphens"
            )
        return value


class ProcedureTranscriptionFile(_ContractModel):
    artifact_version: Literal["verified-transcriptions-v1"]
    transcriptions: list[ProcedureTranscription] = Field(
        default_factory=list[ProcedureTranscription]
    )

    @model_validator(mode="after")
    def validate_transcriptions(self) -> ProcedureTranscriptionFile:
        ids = [transcription.id for transcription in self.transcriptions]
        if len(ids) != len(set(ids)):
            raise ValueError("verified procedures require unique transcriptions")
        return self


class PageRegion(_ContractModel):
    physical_pages: list[int] = Field(min_length=1)
    box: NormalizedBox

    @field_validator("physical_pages")
    @classmethod
    def validate_pages(cls, pages: list[int]) -> list[int]:
        if any(page < 1 for page in pages):
            raise ValueError("physical page numbers must be positive")
        if len(pages) != len(set(pages)):
            raise ValueError("physical page numbers must be unique")
        return sorted(pages)


class PageClassificationOverride(_ContractModel):
    physical_page: int = Field(ge=1)
    kind: PageKind
    reason: str = Field(min_length=1)


class PageClassificationOverrides(_ContractModel):
    exceptions: list[PageClassificationOverride] = Field(
        default_factory=list[PageClassificationOverride]
    )

    @model_validator(mode="after")
    def validate_unique_pages(self) -> PageClassificationOverrides:
        pages = [item.physical_page for item in self.exceptions]
        if len(pages) != len(set(pages)):
            raise ValueError("page classification exceptions must use physical pages once")
        return self


class ColumnBand(_ContractModel):
    id: str = Field(min_length=1)
    x_min: float = Field(ge=0, le=1)
    x_max: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_extent(self) -> ColumnBand:
        if self.x_max <= self.x_min:
            raise ValueError("column x_max must be greater than x_min")
        return self


class LayoutProfile(_ContractModel):
    columns: list[ColumnBand] = Field(default_factory=list[ColumnBand])
    reading_order: ReadingOrder = "left-to-right"

    @model_validator(mode="after")
    def validate_columns(self) -> LayoutProfile:
        ids = [column.id for column in self.columns]
        if len(ids) != len(set(ids)):
            raise ValueError("layout column IDs must be unique")
        ordered = sorted(self.columns, key=lambda column: column.x_min)
        for left, right in pairwise(ordered):
            if right.x_min < left.x_max:
                raise ValueError(f"layout columns {left.id!r} and {right.id!r} overlap")
        return self


class LanguageRegion(_ContractModel):
    language: str = Field(min_length=1)
    box: NormalizedBox


class LanguageProfile(_ContractModel):
    primary_language: str = Field(min_length=1)
    regions: list[LanguageRegion] = Field(default_factory=list[LanguageRegion])


class HeadingRule(_ContractModel):
    pattern: str = Field(min_length=1)
    level: int = Field(ge=1, le=6)
    title_group: int = Field(default=1, ge=0)

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, pattern: str) -> str:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"heading pattern is not a valid regular expression: {exc}") from exc
        return pattern

    @model_validator(mode="after")
    def validate_title_group(self) -> HeadingRule:
        if re.compile(self.pattern).groups < self.title_group:
            raise ValueError("heading title_group exceeds the pattern's capture groups")
        return self


class HeadingProfile(_ContractModel):
    rules: list[HeadingRule] = Field(default_factory=list[HeadingRule])
    infer_hierarchy: bool = True


class TableProfile(_ContractModel):
    excluded_regions: list[PageRegion] = Field(default_factory=list[PageRegion])


class FigureProfile(_ContractModel):
    excluded_regions: list[PageRegion] = Field(default_factory=list[PageRegion])
    requires_human_transcription: Literal[True] = True


class EndBoundaryProfile(_ContractModel):
    strategy: EndBoundaryStrategy = "explicit-marker"
    markers: list[str] = Field(min_length=1)
    section_boundary_reviewed_by: str | None = None

    @field_validator("markers")
    @classmethod
    def validate_markers(cls, markers: list[str]) -> list[str]:
        cleaned = [marker.strip() for marker in markers]
        if any(not marker for marker in cleaned):
            raise ValueError("procedure end markers must not be blank")
        return cleaned

    @model_validator(mode="after")
    def validate_section_boundary_review(self) -> EndBoundaryProfile:
        if self.strategy != "section-boundary":
            return self
        if self.section_boundary_reviewed_by is None:
            raise ValueError("section-boundary strategy requires a maintainer review reference")
        if not self.section_boundary_reviewed_by.strip():
            raise ValueError("section-boundary review reference must not be blank")
        return self


class DocumentProfile(_ContractModel):
    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    selector: ProfileSelector
    page_classification: PageClassificationOverrides = Field(
        default_factory=PageClassificationOverrides
    )
    layout: LayoutProfile = Field(default_factory=LayoutProfile)
    language: LanguageProfile
    headings: HeadingProfile = Field(default_factory=HeadingProfile)
    tables: TableProfile = Field(default_factory=TableProfile)
    figures: FigureProfile = Field(default_factory=FigureProfile)
    end_boundaries: EndBoundaryProfile
    action_aliases: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])

    @field_validator("action_aliases")
    @classmethod
    def validate_aliases(cls, aliases: dict[str, list[str]]) -> dict[str, list[str]]:
        for action, variants in aliases.items():
            if not action.strip():
                raise ValueError("action alias keys must not be blank")
            if not variants or any(not variant.strip() for variant in variants):
                raise ValueError(f"action alias {action!r} must contain non-blank aliases")
        return aliases


class IngestionProfilesFile(_ContractModel):
    profile_schema_version: str
    profile_manifest_version: str = Field(min_length=1)
    profiles: list[DocumentProfile] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_profiles(self) -> IngestionProfilesFile:
        keys = [(profile.id, profile.version) for profile in self.profiles]
        if len(keys) != len(set(keys)):
            raise ValueError("ingestion profiles must have unique id and version pairs")
        fallbacks = [profile for profile in self.profiles if profile.selector.fallback]
        if len(fallbacks) != 1:
            raise ValueError("exactly one ingestion profile must be the fallback")
        return self


class IngestionProfileProvenance(_ContractModel):
    profile_id: str
    profile_version: str
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SelectedProfileProvenance(IngestionProfileProvenance):
    document_id: str


class IngestionProvenance(_ContractModel):
    parser_version: str
    fonttools_version: str
    pypdf_version: str
    profile_schema_version: str
    profile_manifest_version: str
    profile_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    transcription_evidence_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    profiles: list[SelectedProfileProvenance]


class PdfPageObservation(_ContractModel):
    document_id: str
    physical_page: int = Field(ge=1)
    page_width: float = Field(gt=0)
    page_height: float = Field(gt=0)
    text: str


class LayoutSpan(_ContractModel):
    span_id: str
    line_id: str
    document_id: str
    physical_page: int = Field(ge=1)
    column_id: str
    raw_text: str
    text: str
    box: NormalizedBox
    page_box: PageBox
    font_name: str | None = None
    font_size: float | None = None
    font_weight: int | None = None
    bold: bool = False
    italic: bool = False
    language: str | None = None
    evidence_plane: EvidencePlane = "pdf-text"


class SourceEvidenceSpan(_ContractModel):
    span_id: str
    line_id: str
    document_id: str
    physical_page: int = Field(ge=1)
    column_id: str
    language: str | None = None
    evidence_plane: EvidencePlane = "pdf-text"
    raw_text: str
    normalized_text: str
    box: NormalizedBox
    page_box: PageBox


class SourceExcerpt(_ContractModel):
    document_id: str
    physical_page: int = Field(ge=1)
    printed_page: int = Field(ge=1)
    section: str = Field(min_length=1)
    heading_path: list[str] = Field(min_length=1)
    evidence_plane: EvidencePlane = "pdf-text"
    span_ids: list[str] = Field(min_length=1)
    spans: list[SourceEvidenceSpan] = Field(min_length=1)
    raw_text: str
    normalized_text: str


class LayoutStageResult(_ContractModel):
    document_id: str
    physical_page: int = Field(ge=1)
    page_width: float = Field(gt=0)
    page_height: float = Field(gt=0)
    columns: list[ColumnBand]
    spans: list[LayoutSpan]
    reading_order: list[str]
    languages: list[str]


class BlockClassification(_ContractModel):
    block_id: str
    kind: PageKind
    text: str
    span_ids: list[str]
    confidence: float = Field(ge=0, le=1)
    uncertainty: str | None = None


class PageBlockClassificationResult(_ContractModel):
    document_id: str
    physical_page: int = Field(ge=1)
    page_kind: PageKind
    confidence: float = Field(ge=0, le=1)
    blocks: list[BlockClassification]
    uncertain: bool
    rejection_reason: str | None = None


class HeadingNode(_ContractModel):
    heading_id: str
    title: str
    level: int = Field(ge=1, le=6)
    heading_path: list[str] = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    parent_heading_id: str | None = None


class HeadingHierarchyResult(_ContractModel):
    document_id: str
    headings: list[HeadingNode]


class ProcedureCandidate(_ContractModel):
    candidate_id: str
    document_id: str
    title: str
    heading_path: list[str] = Field(min_length=1)
    step_span_ids: list[str] = Field(min_length=1)
    pages: list[int] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list[str])


class ProcedureCompletenessResult(_ContractModel):
    candidate_id: str
    complete: bool
    start_boundary: str
    end_boundary: str | None
    end_strategy: EndBoundaryStrategy | None
    issues: list[str] = Field(default_factory=list[str])


class EvidenceVerificationResult(_ContractModel):
    candidate_id: str
    verified: bool
    verified_span_ids: list[str] = Field(default_factory=list[str])
    issues: list[str] = Field(default_factory=list[str])


class PageBlockClassificationStage(Protocol):
    def classify(
        self,
        observation: PdfPageObservation,
        layout: LayoutStageResult,
        profile: DocumentProfile,
    ) -> PageBlockClassificationResult: ...


class LayoutSpanStage(Protocol):
    def extract(
        self,
        observation: PdfPageObservation,
        profile: DocumentProfile,
    ) -> LayoutStageResult: ...


class HeadingHierarchyStage(Protocol):
    def reconstruct(
        self,
        layout: LayoutStageResult,
        classification: PageBlockClassificationResult,
        profile: DocumentProfile,
    ) -> HeadingHierarchyResult: ...


class ProcedureCandidateStage(Protocol):
    def extract(
        self,
        headings: HeadingHierarchyResult,
        classification: PageBlockClassificationResult,
        profile: DocumentProfile,
    ) -> list[ProcedureCandidate]: ...


class CompletenessStage(Protocol):
    def verify(
        self,
        candidate: ProcedureCandidate,
        profile: DocumentProfile,
    ) -> ProcedureCompletenessResult: ...


class EvidenceVerificationStage(Protocol):
    def verify(
        self,
        candidate: ProcedureCandidate,
        completeness: ProcedureCompletenessResult,
        profile: DocumentProfile,
    ) -> EvidenceVerificationResult: ...


def load_ingestion_profiles(path: Path) -> IngestionProfilesFile:
    try:
        profiles = IngestionProfilesFile.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise IngestionProfileError(f"invalid ingestion profile manifest {path}: {exc}") from exc
    if profiles.profile_schema_version != PROFILE_SCHEMA_VERSION:
        raise IngestionProfileError(
            f"unsupported ingestion profile schema version "
            f"{profiles.profile_schema_version!r} in {path}; "
            f"supported version is {PROFILE_SCHEMA_VERSION!r}"
        )
    for profile in profiles.profiles:
        _validate_supported_version(profile.id, profile.version)
    return profiles


def load_procedure_transcriptions(path: Path) -> ProcedureTranscriptionFile:
    return ProcedureTranscriptionFile.model_validate_json(path.read_text(encoding="utf-8"))


def resolve_document_profile(
    profiles: IngestionProfilesFile,
    *,
    source_id: str,
    metadata: Mapping[str, str],
    reference: IngestionProfileReference | None,
) -> DocumentProfile:
    if reference is not None:
        _validate_supported_version(reference.id, reference.version, source_id=source_id)
        for profile in profiles.profiles:
            if profile.id == reference.id and profile.version == reference.version:
                return profile
        available = ", ".join(f"{profile.id}@{profile.version}" for profile in profiles.profiles)
        raise IngestionProfileError(
            f"source {source_id} references unknown ingestion profile "
            f"{reference.id}@{reference.version}; available profiles: {available}"
        )

    candidates = [
        profile
        for profile in profiles.profiles
        if not profile.selector.fallback
        and all(metadata.get(key) == value for key, value in profile.selector.metadata.items())
    ]
    if candidates:
        most_specific = max(len(profile.selector.metadata) for profile in candidates)
        matches = [
            profile for profile in candidates if len(profile.selector.metadata) == most_specific
        ]
        if len(matches) > 1:
            names = ", ".join(f"{profile.id}@{profile.version}" for profile in matches)
            raise IngestionProfileError(
                f"source {source_id} matches multiple ingestion profiles at the same "
                f"specificity: {names}; add an explicit ingestion_profile reference"
            )
        return matches[0]

    return next(profile for profile in profiles.profiles if profile.selector.fallback)


def profile_sha256(profile: DocumentProfile) -> str:
    canonical = json.dumps(
        profile.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_supported_version(
    profile_id: str,
    version: str,
    *,
    source_id: str | None = None,
) -> None:
    if version in SUPPORTED_PROFILE_VERSIONS:
        return
    subject = (
        f"source {source_id} references"
        if source_id is not None
        else f"ingestion profile {profile_id!r} has"
    )
    raise IngestionProfileError(
        f"{subject} unsupported ingestion profile version {version!r}; supported versions: "
        f"{', '.join(sorted(SUPPORTED_PROFILE_VERSIONS))}"
    )
