from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from pypdf import PdfReader

from zabm.classification import DeterministicPageBlockClassifier, page_allows_procedure_extraction
from zabm.headings import DeterministicHeadingReconstructor
from zabm.ingestion import (
    DEFAULT_INGESTION_PROFILES,
    FONTTOOLS_VERSION,
    PARSER_VERSION,
    PYPDF_VERSION,
    BlockClassification,
    ColumnBand,
    DocumentProfile,
    EndBoundaryProfile,
    EndBoundaryStrategy,
    EvidencePlane,
    HeadingNode,
    HumanTranscriptionVerification,
    IngestionProfileProvenance,
    IngestionProfilesFile,
    IngestionProvenance,
    LayoutSpan,
    LayoutStageResult,
    NormalizedBox,
    PageBlockClassificationResult,
    PageBox,
    PageIngestionOutcome,
    PageKind,
    PdfPageObservation,
    ProcedureTranscription,
    RejectedStepCandidate,
    SelectedProfileProvenance,
    SourceEvidenceSpan,
    SourceExcerpt,
    StepRejectionReason,
    TranscriptionSourceLocation,
    load_ingestion_profiles,
    load_procedure_transcriptions,
    normalize_pdf_text,
    profile_sha256,
    resolve_document_profile,
)
from zabm.matching import identity_matches, tokens, unknown_tokens
from zabm.response import (
    CanonicalResponse,
    Claim,
    Clarification,
    Failure,
    ProcedureAnswer,
    ProcedureStep,
    ProcedureWarning,
    StoredCitation,
)
from zabm.specifications import (
    file_sha256,
    load_source_manifest,
    write_json,
)

logger = logging.getLogger("zabm.rag")

_ProcedureGroupingKey = tuple[str, str, tuple[str, ...], int]

WARNING_HEADINGS: dict[str, Literal["warning", "notice"]] = {
    "NOTICE": "notice",
    "WARNING": "warning",
}
STEP_NUMBER = re.compile(r"^\d{1,2}$")
INLINE_STEP = re.compile(r"^(\d{1,2})\s+(.+)$")
SERVICE_HEADING = re.compile(r"^(?:\d+/)?\d+ Hour Service\s+(.+)$", re.IGNORECASE)
PROCEDURE_HEADING_ACTIONS = (
    "adjust",
    "align",
    "assemble",
    "bleed",
    "bring",
    "carry",
    "center",
    "change",
    "check",
    "clamp",
    "clean",
    "close",
    "connect",
    "cut",
    "deflate",
    "depress",
    "disconnect",
    "engage",
    "fasten",
    "fill",
    "fit",
    "hold",
    "inflate",
    "insert",
    "inspect",
    "install",
    "keep",
    "lift",
    "loosen",
    "lubricate",
    "measure",
    "mount",
    "move",
    "open",
    "overhaul",
    "place",
    "pour",
    "press",
    "protect",
    "pull",
    "push",
    "release",
    "remove",
    "repair",
    "replace",
    "route",
    "rotate",
    "service",
    "set",
    "shorten",
    "slide",
    "snap",
    "spin",
    "stop",
    "support",
    "tighten",
    "thread",
    "turn",
    "unbolt",
    "unclip",
    "unplug",
    "wipe",
    "work",
)
PROCEDURE_HEADING_ACTION_FORMS = {
    "adjust": {"adjustment", "adjustments"},
    "align": {"alignment", "alignments"},
    "assemble": {"assembly", "assemblies"},
    "bleed": {"bled"},
    "cut": {"cutting"},
    "fit": {"fitted", "fitting"},
    "hold": {"held"},
    "install": {"installation", "installations"},
    "inspect": {"inspection", "inspections"},
    "lubricate": {"lubrication"},
    "remove": {"removal", "removals"},
    "replace": {"replacement", "replacements"},
    "set": {"setting"},
    "stop": {"stopping"},
}
NAVIGATION_CUE = re.compile(
    r"^(?:proceed to|this concludes|stop here|end of procedure)\b",
    re.IGNORECASE,
)
TRUNCATION_CUE = re.compile(
    r"\b(?:partial|truncated|preview|remaining steps omitted|continued on)\b",
    re.IGNORECASE,
)
PROCEDURE_STOPWORDS = {
    "a",
    "an",
    "and",
    "do",
    "for",
    "how",
    "i",
    "in",
    "install",
    "installation",
    "of",
    "on",
    "perform",
    "procedure",
    "remove",
    "removal",
    "replace",
    "replacement",
    "steps",
    "the",
    "to",
}
PROCEDURE_QUERY_VOCAB = (
    "adjust assemble bleed disassemble how install installation perform prepare procedure "
    "remove removal replace replacement service step steps task walk through"
)


class EvidenceBlock(BaseModel):
    kind: Literal["heading", "paragraph", "table", "warning", "step"]
    text: str
    heading_path: list[str]
    cells: list[str] = Field(default_factory=list[str])
    classified_kind: PageKind = "paragraph"
    classification_confidence: float = 0.0
    classification_uncertainty: str | None = None


class StoredProcedureWarning(ProcedureWarning):
    evidence: SourceExcerpt


class StoredProcedureStep(BaseModel):
    number: int
    text: str
    warnings: list[StoredProcedureWarning] = Field(default_factory=list[StoredProcedureWarning])
    citation: StoredCitation
    evidence: SourceExcerpt


class RetrievalPage(BaseModel):
    physical_page: int
    printed_page: int
    section: str
    heading_path: list[str]
    page_width: float
    page_height: float
    extraction_language: str
    columns: list[ColumnBand] = Field(default_factory=list[ColumnBand])
    spans: list[LayoutSpan] = Field(default_factory=list[LayoutSpan])
    unverified_transcriptions: list[ProcedureTranscription] = Field(
        default_factory=list[ProcedureTranscription]
    )
    verified_transcription_spans: list[LayoutSpan] = Field(default_factory=list[LayoutSpan])
    verified_transcription_ids: list[str] = Field(default_factory=list[str])
    reading_order: list[str] = Field(default_factory=list[str])
    languages: list[str] = Field(default_factory=list[str])
    page_kind: PageKind = "unknown"
    ingestion_outcome: PageIngestionOutcome = "answer-eligible"
    ingestion_outcome_reason: str | None = None
    classification_confidence: float = 0.0
    classification_uncertain: bool = True
    classification_uncertainty: str | None = None
    text: str
    blocks: list[EvidenceBlock]
    rejected_step_candidates: list[RejectedStepCandidate] = Field(
        default_factory=list[RejectedStepCandidate]
    )


class RetrievalSource(BaseModel):
    document_id: str
    title: str
    manufacturer: str
    ingestion_profile: IngestionProfileProvenance
    pages: list[RetrievalPage]


class ProcedureEndEvidence(BaseModel):
    text: str
    after_step: int
    strategy: EndBoundaryStrategy = "explicit-marker"


class TranscriptionEvidence(BaseModel):
    transcription_id: str
    source_location: TranscriptionSourceLocation
    verification: HumanTranscriptionVerification


class ProcedureGroupingDecision(BaseModel):
    decision: Literal["merged", "kept-separate", "rejected"]
    reason: str
    pages: list[int] = Field(min_length=1)


class StoredProcedure(BaseModel):
    procedure_id: str
    document_id: str
    title: str
    heading_path: list[str]
    start_boundary: str
    end_boundary: str | None
    end_strategy: EndBoundaryStrategy | None
    page_numbers: list[int]
    steps: list[StoredProcedureStep]
    end_evidence: list[ProcedureEndEvidence] = Field(default_factory=list[ProcedureEndEvidence])
    completeness_notes: list[str] = Field(default_factory=list[str])
    validation_issues: list[str] = Field(default_factory=list[str])
    grouping_decisions: list[ProcedureGroupingDecision] = Field(
        default_factory=list[ProcedureGroupingDecision]
    )
    evidence_plane: EvidencePlane = "pdf-text"
    verified_transcription: TranscriptionEvidence | None = None


class RetrievalCatalog(BaseModel):
    source_pack_id: str
    ingestion_provenance: IngestionProvenance
    sources: list[RetrievalSource]
    procedures: list[StoredProcedure]


class PageAlignmentReport(BaseModel):
    document_count: int
    physical_page_count: int
    parsed_page_count: int
    text_page_count: int
    missing_text_pages: list[str]


class TranscriptionRequiredPage(BaseModel):
    document_id: str
    physical_page: int
    printed_page: int
    page_kind: PageKind
    reason: str


class RetrievalIngestReport(BaseModel):
    source_pack_id: str
    ingestion_provenance: IngestionProvenance
    page_count: int
    page_alignment: PageAlignmentReport
    table_row_count: int
    warning_count: int
    procedure_count: int
    eligible_procedure_count: int
    verified_transcription_count: int = 0
    transcription_required_pages: list[TranscriptionRequiredPage] = Field(
        default_factory=list[TranscriptionRequiredPage]
    )
    validation_issues: list[str]


class ProcedureEvidenceMatch(BaseModel):
    procedure_id: str
    title: str
    heading_path: list[str]
    complete: bool
    validation_issues: list[str]
    grouping_decisions: list[ProcedureGroupingDecision] = Field(
        default_factory=list[ProcedureGroupingDecision]
    )
    pages: list[RetrievalPage]
    steps: list[StoredProcedureStep]


class ProcedureEvidenceInspection(BaseModel):
    source_pack_id: str
    question: str
    matches: list[ProcedureEvidenceMatch]


@dataclass
class _Fragment:
    text: str
    raw_text: str
    x: float
    y: float
    width: float
    height: float
    span_id: str
    line_id: str
    column_id: str
    language: str
    font_name: str | None
    font_size: float | None
    font_weight: int | None
    bold: bool
    italic: bool


@dataclass
class _Line:
    spans: list[LayoutSpan]

    @property
    def column_id(self) -> str:
        return self.spans[0].column_id if self.spans else ""

    @property
    def y(self) -> float:
        return self.spans[0].page_box.y_min if self.spans else 0.0

    @property
    def x(self) -> float:
        return self.spans[0].page_box.x_min if self.spans else 0.0

    @property
    def text(self) -> str:
        return normalize_pdf_text(" ".join(span.text for span in self.spans))

    @property
    def raw_text(self) -> str:
        return " ".join(span.raw_text for span in self.spans)


def _source_excerpt(
    spans: list[LayoutSpan],
    *,
    printed_page: int,
    section: str,
    heading_path: list[str],
) -> SourceExcerpt:
    raw_text = _excerpt_raw_text(spans)
    first = spans[0]
    return SourceExcerpt(
        document_id=first.document_id,
        physical_page=first.physical_page,
        printed_page=printed_page,
        section=section,
        heading_path=heading_path,
        evidence_plane=first.evidence_plane,
        span_ids=[span.span_id for span in spans],
        spans=[_source_evidence_span(span) for span in spans],
        raw_text=raw_text,
        normalized_text=normalize_pdf_text(raw_text),
    )


def _source_evidence_span(span: LayoutSpan) -> SourceEvidenceSpan:
    return SourceEvidenceSpan(
        span_id=span.span_id,
        line_id=span.line_id,
        document_id=span.document_id,
        physical_page=span.physical_page,
        column_id=span.column_id,
        language=span.language,
        evidence_plane=span.evidence_plane,
        raw_text=span.raw_text,
        normalized_text=span.text,
        box=span.box,
        page_box=span.page_box,
    )


def _verified_transcription_procedures(
    source: RetrievalSource,
    transcriptions: Sequence[ProcedureTranscription],
    *,
    retrieval_date: date,
    manifest_version: str,
) -> list[StoredProcedure]:
    pages_by_number = {page.physical_page: page for page in source.pages}
    procedures: list[StoredProcedure] = []
    for transcription in transcriptions:
        verification = transcription.verification
        location = transcription.location
        page = pages_by_number.get(location.physical_page)
        if page is None:
            raise ValueError(
                f"verified transcription {transcription.id} references missing physical "
                f"page {location.physical_page}"
            )
        if verification.status.strip() != "human_verified":
            page.unverified_transcriptions.append(transcription)
            continue
        if not verification.verified_by.strip():
            raise ValueError(f"verified transcription {transcription.id} requires a named reviewer")
        if verification.verified_at is None:
            raise ValueError(
                f"verified transcription {transcription.id} requires a verification date"
            )
        if not transcription.title.strip():
            raise ValueError(f"verified transcription {transcription.id} requires a title")
        if not location.section.strip():
            raise ValueError(f"verified transcription {transcription.id} requires a source section")
        if any(not heading.strip() for heading in location.heading_path):
            raise ValueError(
                f"verified transcription {transcription.id} has a blank heading path entry"
            )
        if page.printed_page != location.printed_page:
            raise ValueError(
                f"verified transcription {transcription.id} printed page "
                f"{location.printed_page} does not match source page {page.printed_page}"
            )
        _validate_transcription_box(
            location.box,
            page=page,
            label=f"verified transcription {transcription.id} source location",
        )
        step_numbers = [step.number for step in transcription.steps]
        if step_numbers != list(range(1, len(step_numbers) + 1)):
            raise ValueError(
                f"verified transcription {transcription.id} steps must be contiguous from 1"
            )
        if not normalize_pdf_text(transcription.end_boundary):
            raise ValueError(
                f"verified transcription {transcription.id} requires end-boundary text"
            )

        transcription_spans: list[LayoutSpan] = []
        heading_text = normalize_pdf_text(transcription.title)
        heading_line_id = (
            f"{source.document_id}:p{page.physical_page}:"
            f"transcription:{_slug(transcription.id)}:heading"
        )
        transcription_spans.append(
            _transcription_layout_span(
                source=source,
                page=page,
                transcription_id=transcription.id,
                line_id=heading_line_id,
                span_index=0,
                raw_text=heading_text,
                box=location.box,
            )
        )

        procedure_steps: list[StoredProcedureStep] = []
        for step in transcription.steps:
            _validate_transcription_box(
                step.source_box,
                page=page,
                label=f"verified transcription {transcription.id} step {step.number}",
            )
            _validate_box_containment(
                step.source_box,
                location.box,
                label=f"verified transcription {transcription.id} step {step.number}",
            )
            step_text = normalize_pdf_text(step.text)
            if not step_text:
                raise ValueError(
                    f"verified transcription {transcription.id} step {step.number} has no text"
                )
            step_line_id = (
                f"{source.document_id}:p{page.physical_page}:"
                f"transcription:{_slug(transcription.id)}:step-{step.number}"
            )
            step_span = _transcription_layout_span(
                source=source,
                page=page,
                transcription_id=transcription.id,
                line_id=step_line_id,
                span_index=0,
                raw_text=f"{step.number} {step_text}",
                box=step.source_box,
            )
            transcription_spans.append(step_span)
            warnings: list[StoredProcedureWarning] = []
            for warning_index, warning in enumerate(step.warnings, start=1):
                warning_text = normalize_pdf_text(warning.text)
                if not warning_text:
                    raise ValueError(
                        f"verified transcription {transcription.id} step {step.number} "
                        f"warning {warning_index} has no text"
                    )
                warning_line_id = f"{step_line_id}:warning-{warning_index}"
                warning_heading_span = _transcription_layout_span(
                    source=source,
                    page=page,
                    transcription_id=transcription.id,
                    line_id=warning_line_id,
                    span_index=0,
                    raw_text=warning.severity.upper(),
                    box=step.source_box,
                )
                warning_body_span = _transcription_layout_span(
                    source=source,
                    page=page,
                    transcription_id=transcription.id,
                    line_id=f"{warning_line_id}:body",
                    span_index=0,
                    raw_text=warning_text,
                    box=step.source_box,
                )
                transcription_spans.extend([warning_heading_span, warning_body_span])
                warnings.append(
                    StoredProcedureWarning(
                        severity=warning.severity,
                        text=warning_text,
                        evidence=_source_excerpt(
                            [warning_heading_span, warning_body_span],
                            printed_page=page.printed_page,
                            section=location.section,
                            heading_path=list(location.heading_path),
                        ),
                    )
                )

            citation = StoredCitation(
                document_id=source.document_id,
                title=source.title,
                manufacturer=source.manufacturer,
                printed_page=page.printed_page,
                physical_page=page.physical_page,
                section=location.section,
                retrieval_date=retrieval_date,
                source_manifest_version=manifest_version,
            )
            procedure_steps.append(
                StoredProcedureStep(
                    number=step.number,
                    text=step_text,
                    warnings=warnings,
                    citation=citation,
                    evidence=_source_excerpt(
                        [step_span],
                        printed_page=page.printed_page,
                        section=location.section,
                        heading_path=list(location.heading_path),
                    ),
                )
            )

        end_text = normalize_pdf_text(transcription.end_boundary)
        end_line_id = (
            f"{source.document_id}:p{page.physical_page}:"
            f"transcription:{_slug(transcription.id)}:end"
        )
        transcription_spans.append(
            _transcription_layout_span(
                source=source,
                page=page,
                transcription_id=transcription.id,
                line_id=end_line_id,
                span_index=0,
                raw_text=end_text,
                box=location.box,
            )
        )
        page.verified_transcription_spans.extend(transcription_spans)
        page.verified_transcription_ids.append(transcription.id)
        page.reading_order.extend(span.span_id for span in transcription_spans)
        page.ingestion_outcome = "transcription-verified"
        page.ingestion_outcome_reason = "human-verified transcription accepted"
        procedures.append(
            StoredProcedure(
                procedure_id=(
                    f"{source.document_id}#{_slug(transcription.title)}-"
                    f"transcription-{_slug(transcription.id)}-p{page.physical_page}"
                ),
                document_id=source.document_id,
                title=transcription.title,
                heading_path=list(location.heading_path),
                start_boundary=" > ".join(location.heading_path),
                end_boundary=end_text,
                end_strategy="explicit-marker",
                page_numbers=[page.physical_page],
                steps=procedure_steps,
                end_evidence=[
                    ProcedureEndEvidence(
                        text=end_text,
                        after_step=procedure_steps[-1].number,
                    )
                ],
                evidence_plane="verified-transcription",
                verified_transcription=TranscriptionEvidence(
                    transcription_id=transcription.id,
                    source_location=location,
                    verification=verification,
                ),
            )
        )
    return procedures


def _transcription_layout_span(
    *,
    source: RetrievalSource,
    page: RetrievalPage,
    transcription_id: str,
    line_id: str,
    span_index: int,
    raw_text: str,
    box: PageBox,
) -> LayoutSpan:
    normalized_text = normalize_pdf_text(raw_text)
    if not normalized_text:
        raise ValueError(f"verified transcription {transcription_id} contains blank evidence text")
    return LayoutSpan(
        span_id=f"{line_id}:s{span_index}",
        line_id=line_id,
        document_id=source.document_id,
        physical_page=page.physical_page,
        column_id=f"transcription:{_slug(transcription_id)}",
        raw_text=raw_text,
        text=normalized_text,
        box=_normalized_box(
            box.x_min,
            box.x_max,
            box.y_min,
            box.y_max,
            page.page_width,
            page.page_height,
        ),
        page_box=box,
        language=page.extraction_language,
        evidence_plane="verified-transcription",
    )


def _validate_transcription_box(
    box: PageBox,
    *,
    page: RetrievalPage,
    label: str,
) -> None:
    tolerance = 1e-6
    if (
        box.x_min < -tolerance
        or box.y_min < -tolerance
        or box.x_max > page.page_width + tolerance
        or box.y_max > page.page_height + tolerance
    ):
        raise ValueError(f"{label} lies outside physical page {page.physical_page}")


def _validate_box_containment(box: PageBox, container: PageBox, *, label: str) -> None:
    tolerance = 1e-6
    if (
        box.x_min < container.x_min - tolerance
        or box.y_min < container.y_min - tolerance
        or box.x_max > container.x_max + tolerance
        or box.y_max > container.y_max + tolerance
    ):
        raise ValueError(f"{label} lies outside the verified source location")


def _excerpt_raw_text(spans: Sequence[LayoutSpan | SourceEvidenceSpan]) -> str:
    line_groups: list[list[LayoutSpan | SourceEvidenceSpan]] = []
    for span in spans:
        if not line_groups or line_groups[-1][0].line_id != span.line_id:
            line_groups.append([span])
        else:
            line_groups[-1].append(span)
    return "\n".join(" ".join(span.raw_text for span in line_spans) for line_spans in line_groups)


def _source_excerpt_issues(
    excerpt: SourceExcerpt,
    citation: StoredCitation,
    *,
    source_document_id: str,
    source_spans: Sequence[LayoutSpan] | None,
    source_printed_page: int | None,
    expected_text: str,
    expected_kind: Literal["step", "warning"],
    expected_heading_path: Sequence[str],
    expected_evidence_plane: EvidencePlane = "pdf-text",
) -> list[str]:
    issues: list[str] = []
    if excerpt.document_id != source_document_id:
        issues.append("evidence excerpt document does not match its source")
    if citation.document_id != source_document_id:
        issues.append("citation document does not match its source")
    if citation.document_id != excerpt.document_id:
        issues.append("citation document does not match the evidence excerpt")
    if citation.physical_page != excerpt.physical_page:
        issues.append("citation physical page does not match the evidence excerpt")
    if citation.printed_page != excerpt.printed_page:
        issues.append("citation printed page does not match the evidence excerpt")
    if source_spans is None:
        issues.append(f"physical page {citation.physical_page} has no catalog spans")
    elif source_printed_page != citation.printed_page:
        issues.append(
            f"printed page {citation.printed_page} does not match source page {source_printed_page}"
        )
    if citation.section != excerpt.section:
        issues.append("citation section does not match the evidence excerpt")
    if list(excerpt.heading_path) != list(expected_heading_path):
        issues.append("evidence excerpt heading path does not match its procedure")
    if excerpt.evidence_plane != expected_evidence_plane:
        issues.append("evidence excerpt uses the wrong evidence plane")

    excerpt_span_ids = [span.span_id for span in excerpt.spans]
    if excerpt.span_ids != excerpt_span_ids:
        issues.append("evidence excerpt span identifiers do not match its spans")
    if len(set(excerpt.span_ids)) != len(excerpt.span_ids):
        issues.append("evidence excerpt repeats a source span")
    if len({span.column_id for span in excerpt.spans}) > 1:
        issues.append("evidence excerpt crosses source columns")
    languages = {span.language for span in excerpt.spans if span.language is not None}
    if len(languages) > 1:
        issues.append("evidence excerpt mixes source languages")
    if any(span.evidence_plane != expected_evidence_plane for span in excerpt.spans):
        issues.append("evidence excerpt spans use the wrong evidence plane")

    resolved_spans: list[LayoutSpan] = []
    if source_spans is not None:
        spans_by_id = {span.span_id: span for span in source_spans}
        positions = {span.span_id: index for index, span in enumerate(source_spans)}
        for evidence_span in excerpt.spans:
            source_span = spans_by_id.get(evidence_span.span_id)
            if source_span is None:
                issues.append(
                    f"evidence excerpt span {evidence_span.span_id} does not resolve "
                    "on the cited physical page"
                )
                continue
            expected_span = _source_evidence_span(source_span)
            if evidence_span != expected_span:
                issues.append(
                    f"evidence excerpt span {evidence_span.span_id} does not match "
                    "its catalog source"
                )
            else:
                resolved_spans.append(source_span)
        resolved_positions = [
            positions[span.span_id] for span in resolved_spans if span.span_id in positions
        ]
        if resolved_positions != sorted(set(resolved_positions)):
            issues.append("evidence excerpt spans do not follow source reading order")

    resolved_raw_text = _excerpt_raw_text(resolved_spans or excerpt.spans)
    if excerpt.raw_text != resolved_raw_text:
        issues.append("evidence excerpt raw text does not resolve from its source spans")
    if excerpt.normalized_text != normalize_pdf_text(resolved_raw_text):
        issues.append("evidence excerpt normalized text does not resolve from its source spans")

    expected_normalized_text = normalize_pdf_text(expected_text)
    if expected_kind == "step":
        step_text = re.sub(r"^\d{1,2}\s+", "", excerpt.normalized_text, count=1)
        if step_text != expected_normalized_text:
            issues.append("evidence excerpt does not resolve to the stored step text")
    else:
        raw_lines = resolved_raw_text.splitlines()
        heading = raw_lines[0] if raw_lines else ""
        if _warning_severity(heading) is None:
            issues.append("warning evidence does not resolve to a warning heading")
        warning_body = normalize_pdf_text("\n".join(raw_lines[1:]))
        if warning_body != expected_normalized_text:
            issues.append("evidence excerpt does not resolve to the stored warning text")
    return issues


def resolve_procedure_evidence(
    procedure: StoredProcedure,
    sources: Iterable[RetrievalSource],
) -> StoredProcedure:
    source_pages: dict[int, RetrievalPage] = {}
    for source in sources:
        if source.document_id == procedure.document_id:
            source_pages = {page.physical_page: page for page in source.pages}
            break
    accepted_steps: list[StoredProcedureStep] = []
    evidence_issues: list[str] = []
    for step in procedure.steps:
        page = source_pages.get(step.citation.physical_page)
        source_spans = (
            page.verified_transcription_spans
            if page is not None and procedure.evidence_plane == "verified-transcription"
            else page.spans
            if page is not None
            else None
        )
        step_issues = _source_excerpt_issues(
            step.evidence,
            step.citation,
            source_document_id=procedure.document_id,
            source_spans=source_spans,
            source_printed_page=page.printed_page if page is not None else None,
            expected_text=step.text,
            expected_kind="step",
            expected_heading_path=procedure.heading_path,
            expected_evidence_plane=procedure.evidence_plane,
        )
        for warning in step.warnings:
            step_issues.extend(
                _source_excerpt_issues(
                    warning.evidence,
                    step.citation,
                    source_document_id=procedure.document_id,
                    source_spans=source_spans,
                    source_printed_page=page.printed_page if page is not None else None,
                    expected_text=warning.text,
                    expected_kind="warning",
                    expected_heading_path=procedure.heading_path,
                    expected_evidence_plane=procedure.evidence_plane,
                )
            )
        if step_issues:
            evidence_issues.extend(
                f"step {step.number}: {issue}" for issue in dict.fromkeys(step_issues)
            )
        else:
            accepted_steps.append(step)

    if not evidence_issues:
        return procedure
    return procedure.model_copy(
        update={
            "steps": accepted_steps,
            "validation_issues": list(
                dict.fromkeys([*procedure.validation_issues, *evidence_issues])
            ),
        },
        deep=True,
    )


@dataclass
class _StepStart:
    number: int
    number_line_index: int
    line_index: int
    text: str


@dataclass
class _ParsedStep:
    step: StoredProcedureStep
    section_sequence: int
    section_title: str
    heading_path: list[str]
    line_index: int
    section_level: int


@dataclass
class _HeadingEvent:
    physical_page: int
    line_index: int
    level: int
    heading_path: list[str]


@dataclass
class _TextEvent:
    physical_page: int
    line_index: int
    text: str


@dataclass
class _PageParse:
    page: RetrievalPage
    steps: list[_ParsedStep]
    step_issues: dict[int, list[str]]
    end_evidence: dict[int, list[ProcedureEndEvidence]]
    completeness_notes: dict[int, list[str]]
    heading_events: list[_HeadingEvent]
    end_marker_events: list[_TextEvent]
    completeness_note_events: list[_TextEvent]
    section_paths: dict[int, list[str]]
    heading_stack: list[HeadingNode]
    document_id: str


def ingest_retrieval(
    manifest_path: Path,
    pdf_dir: Path,
    data_dir: Path,
    ingestion_profiles_path: Path | None = None,
    *,
    ingestion_profiles: IngestionProfilesFile | None = None,
    transcriptions_path: Path | None = None,
    requested_language: str | None = None,
) -> RetrievalIngestReport:
    manifest = load_source_manifest(manifest_path)
    if ingestion_profiles is not None and ingestion_profiles_path is None:
        raise ValueError("preloaded ingestion profiles require their source manifest path")
    profile_path = ingestion_profiles_path or DEFAULT_INGESTION_PROFILES
    profiles = ingestion_profiles or load_ingestion_profiles(profile_path)
    transcription_file = (
        load_procedure_transcriptions(transcriptions_path)
        if transcriptions_path is not None
        else None
    )
    transcriptions = transcription_file.transcriptions if transcription_file is not None else []
    known_document_ids = {source.id for source in manifest.sources}
    unknown_document_ids = sorted(
        {transcription.document_id for transcription in transcriptions} - known_document_ids
    )
    if unknown_document_ids:
        raise ValueError(
            "verified transcriptions reference unknown document(s): "
            + ", ".join(unknown_document_ids)
        )
    sources: list[RetrievalSource] = []
    procedures: list[StoredProcedure] = []
    verified_transcription_count = 0
    validation_issues: list[str] = []
    selected_profiles: list[SelectedProfileProvenance] = []

    for source in manifest.sources:
        selected_profile = resolve_document_profile(
            profiles,
            source_id=source.id,
            metadata=source.ingestion_metadata,
            reference=source.ingestion_profile,
        )
        selected_sha256 = profile_sha256(selected_profile)
        profile_provenance = IngestionProfileProvenance(
            profile_id=selected_profile.id,
            profile_version=selected_profile.version,
            profile_sha256=selected_sha256,
        )
        selected_profiles.append(
            SelectedProfileProvenance(
                document_id=source.id,
                **profile_provenance.model_dump(),
            )
        )
        source_path = pdf_dir / f"{source.id}.pdf"
        if not source_path.is_file():
            raise OSError(f"source {source.id} has not been downloaded")
        if file_sha256(source_path) != source.sha256:
            raise OSError(f"source {source.id} does not match the manifest hash")

        reader = PdfReader(source_path)
        parsed_pages: list[_PageParse] = []
        preceding_headings: list[HeadingNode] = []
        for index, page in enumerate(reader.pages, start=1):
            parsed_page = _parse_page(
                page,
                physical_page=index,
                source_id=source.id,
                source_title=source.title,
                manufacturer=source.manufacturer,
                retrieval_date=source.retrieval_date,
                manifest_version=manifest.manifest_version,
                profile=selected_profile,
                requested_language=requested_language,
                preceding_headings=preceding_headings,
            )
            parsed_pages.append(parsed_page)
            preceding_headings = parsed_page.heading_stack
        retrieval_source = RetrievalSource(
            document_id=source.id,
            title=source.title,
            manufacturer=source.manufacturer,
            ingestion_profile=profile_provenance,
            pages=[parsed.page for parsed in parsed_pages],
        )
        sources.append(retrieval_source)
        verified_transcriptions = _verified_transcription_procedures(
            retrieval_source,
            [
                transcription
                for transcription in transcriptions
                if transcription.document_id == source.id
            ],
            retrieval_date=source.retrieval_date,
            manifest_version=manifest.manifest_version,
        )
        verified_transcription_count += len(verified_transcriptions)
        procedures.extend(verified_transcriptions)
        for procedure in _group_procedures(parsed_pages, selected_profile.end_boundaries):
            resolved_procedure = resolve_procedure_evidence(procedure, sources)
            procedures.append(resolved_procedure)
            validation_issues.extend(
                f"{resolved_procedure.procedure_id}: {issue}"
                for issue in resolved_procedure.validation_issues
            )

    ingestion_provenance = IngestionProvenance(
        parser_version=PARSER_VERSION,
        fonttools_version=FONTTOOLS_VERSION,
        pypdf_version=PYPDF_VERSION,
        profile_schema_version=profiles.profile_schema_version,
        profile_manifest_version=profiles.profile_manifest_version,
        profile_manifest_sha256=file_sha256(profile_path),
        transcription_evidence_sha256=(
            file_sha256(transcriptions_path) if transcriptions_path is not None else None
        ),
        profiles=selected_profiles,
    )
    catalog = RetrievalCatalog(
        source_pack_id=manifest.manifest_version,
        ingestion_provenance=ingestion_provenance,
        sources=sources,
        procedures=procedures,
    )
    generated_dir = data_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    write_json(generated_dir / "retrieval.json", catalog.model_dump(mode="json"))

    pages = [page for source in sources for page in source.pages]
    complete_procedure_count = sum(
        not procedure.validation_issues and not procedure_completeness_issues(procedure)
        for procedure in procedures
    )
    return RetrievalIngestReport(
        source_pack_id=manifest.manifest_version,
        ingestion_provenance=ingestion_provenance,
        page_count=len(pages),
        page_alignment=PageAlignmentReport(
            document_count=len(sources),
            physical_page_count=sum(len(source.pages) for source in sources),
            parsed_page_count=len(pages),
            text_page_count=sum(bool(page.text.strip()) for page in pages),
            missing_text_pages=[
                f"{source.document_id}:{page.physical_page}"
                for source in sources
                for page in source.pages
                if not page.text.strip()
            ],
        ),
        table_row_count=sum(block.kind == "table" for page in pages for block in page.blocks),
        warning_count=sum(block.kind == "warning" for page in pages for block in page.blocks),
        procedure_count=len(procedures),
        eligible_procedure_count=complete_procedure_count,
        verified_transcription_count=verified_transcription_count,
        transcription_required_pages=[
            TranscriptionRequiredPage(
                document_id=source.document_id,
                physical_page=page.physical_page,
                printed_page=page.printed_page,
                page_kind=page.page_kind,
                reason=page.ingestion_outcome_reason or "transcription is required",
            )
            for source in sources
            for page in source.pages
            if page.ingestion_outcome == "transcription-required"
        ],
        validation_issues=validation_issues,
    )


def answer_procedure(question: str, data_dir: Path) -> CanonicalResponse:
    catalog_path = data_dir / "generated" / "retrieval.json"
    if not catalog_path.is_file():
        return _not_found(
            "Retrieval evidence has not been ingested. Run `zabm download` and "
            "`zabm ingest` first.",
            source_pack_id="unknown",
        )

    catalog = RetrievalCatalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
    matches = [
        procedure
        for procedure in catalog.procedures
        if _matches_question(procedure.title, question)
    ]
    logger.debug(
        "procedure-query question=%s match_count=%d matches=%s",
        question,
        len(matches),
        [
            (
                procedure.procedure_id,
                procedure.title,
                procedure.page_numbers,
                procedure.validation_issues,
            )
            for procedure in matches
        ],
    )
    if not matches:
        if not unknown_tokens(
            question,
            identifiers=[],
            supporting=[PROCEDURE_QUERY_VOCAB],
        ):
            return _clarification_required(source_pack_id=catalog.source_pack_id)
        return _not_found(
            "No complete source-defined service procedure matches this task.",
            source_pack_id=catalog.source_pack_id,
        )
    if len(matches) > 1:
        return _clarification_required(
            source_pack_id=catalog.source_pack_id,
        )

    procedure = resolve_procedure_evidence(matches[0], catalog.sources)
    issues = procedure_completeness_issues(procedure)
    if issues:
        return _not_found(
            f"only partial procedure evidence was available: {issues[0]}",
            source_pack_id=catalog.source_pack_id,
        )

    claims = [
        Claim(
            claim_id=f"{procedure.procedure_id}#step-{step.number}",
            text=f"Step {step.number}: {step.text}",
            evidence_ids=[f"{procedure.procedure_id}#step-{step.number}"],
        )
        for step in procedure.steps
    ]
    for step in procedure.steps:
        claims.extend(
            Claim(
                claim_id=f"{procedure.procedure_id}#step-{step.number}-warning-{index}",
                text=f"{warning.severity.capitalize()}: {warning.text}",
                evidence_ids=[f"{procedure.procedure_id}#step-{step.number}"],
            )
            for index, warning in enumerate(step.warnings, start=1)
        )

    citations = _unique_citations(step.citation for step in procedure.steps)
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type="procedure",
        language="en",
        status="supported",
        claims=claims,
        procedure=ProcedureAnswer(
            title=procedure.title,
            heading_path=procedure.heading_path,
            steps=[
                ProcedureStep(
                    number=step.number,
                    text=step.text,
                    warnings=[
                        ProcedureWarning(severity=warning.severity, text=warning.text)
                        for warning in step.warnings
                    ],
                    citation=step.citation,
                )
                for step in procedure.steps
            ],
        ),
        citations=citations,
        source_pack_id=catalog.source_pack_id,
    )


def inspect_procedure_evidence(question: str, data_dir: Path) -> ProcedureEvidenceInspection:
    catalog_path = data_dir / "generated" / "retrieval.json"
    if not catalog_path.is_file():
        return ProcedureEvidenceInspection(
            source_pack_id="unknown",
            question=question,
            matches=[],
        )

    catalog = RetrievalCatalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
    pages_by_source = {
        source.document_id: {page.physical_page: page for page in source.pages}
        for source in catalog.sources
    }
    matches: list[ProcedureEvidenceMatch] = []
    for procedure in catalog.procedures:
        if not _matches_question(procedure.title, question):
            continue
        resolved = resolve_procedure_evidence(procedure, catalog.sources)
        issues = procedure_completeness_issues(resolved)
        matches.append(
            ProcedureEvidenceMatch(
                procedure_id=procedure.procedure_id,
                title=procedure.title,
                heading_path=procedure.heading_path,
                complete=not issues,
                validation_issues=issues,
                grouping_decisions=resolved.grouping_decisions,
                pages=[
                    pages_by_source[procedure.document_id][page_number]
                    for page_number in procedure.page_numbers
                ],
                steps=resolved.steps,
            )
        )
    return ProcedureEvidenceInspection(
        source_pack_id=catalog.source_pack_id,
        question=question,
        matches=matches,
    )


def _parse_page(
    page: Any,
    *,
    physical_page: int,
    source_id: str,
    source_title: str,
    manufacturer: str,
    retrieval_date: date,
    manifest_version: str,
    profile: DocumentProfile,
    requested_language: str | None,
    preceding_headings: Sequence[HeadingNode],
) -> _PageParse:
    raw_text = page.extract_text() or ""
    layout = _page_layout(
        page,
        document_id=source_id,
        physical_page=physical_page,
        profile=profile,
    )
    extraction_language = requested_language or profile.language.primary_language
    lines = _lines_from_layout(layout, language=extraction_language)
    primary_lines = (
        lines
        if extraction_language == profile.language.primary_language
        else _lines_from_layout(layout, language=profile.language.primary_language)
    )
    classification = DeterministicPageBlockClassifier().classify(
        PdfPageObservation(
            document_id=source_id,
            physical_page=physical_page,
            page_width=float(page.mediabox.width),
            page_height=float(page.mediabox.height),
            text=raw_text,
        ),
        layout,
        profile,
    )
    heading_hierarchy = DeterministicHeadingReconstructor().reconstruct(
        layout,
        classification,
        profile,
        preceding_headings=preceding_headings,
    )
    headings_by_span = {
        span_id: heading
        for heading in heading_hierarchy.headings
        for span_id in heading.source_span_ids
    }
    blocks_by_span = {
        span_id: block for block in classification.blocks for span_id in block.span_ids
    }
    extraction_allowed = page_allows_procedure_extraction(
        classification.page_kind,
        uncertain=classification.uncertain,
    )
    footer_lines = [line for line in lines if line.y < 35]
    content_lines = [line for line in lines if line.y >= 35]
    content_classifications = [
        blocks_by_span[line.spans[0].span_id] for line in lines if line.y >= 35
    ]
    footer_number = next(
        (
            int(fragment.text)
            for line in footer_lines
            for fragment in line.spans
            if STEP_NUMBER.fullmatch(fragment.text)
        ),
        physical_page,
    )

    primary_content_lines = [line for line in primary_lines if line.y >= 35]
    context_line = primary_content_lines[0] if primary_content_lines else None
    top_text = context_line.text if context_line is not None else source_title
    top_number, top_title = _printed_page_and_title(top_text, physical_page)
    preceding_heading = preceding_headings[-1] if preceding_headings else None
    section_title = (
        heading_hierarchy.headings[0].title
        if heading_hierarchy.headings
        else preceding_heading.title
        if preceding_heading is not None
        else top_title
    )
    printed_page = footer_number if footer_lines else top_number
    heading_path = (
        list(heading_hierarchy.headings[0].heading_path)
        if heading_hierarchy.headings
        else list(preceding_heading.heading_path)
        if preceding_heading is not None
        else [section_title]
    )
    blocks: list[EvidenceBlock] = []
    steps: list[_ParsedStep] = []
    step_issues: dict[int, list[str]] = {}
    end_evidence: dict[int, list[ProcedureEndEvidence]] = {}
    completeness_notes: dict[int, list[str]] = {}
    heading_events: list[_HeadingEvent] = []
    end_marker_events: list[_TextEvent] = []
    completeness_note_events: list[_TextEvent] = []
    current_title: str = section_title
    current_path: list[str] = heading_path
    initial_heading = (
        heading_hierarchy.headings[0] if heading_hierarchy.headings else preceding_heading
    )
    current_level = initial_heading.level if initial_heading is not None else 1
    section_sequence = 0
    section_paths = {section_sequence: list(current_path)}
    current_step: StoredProcedureStep | None = None
    pending_warnings: list[StoredProcedureWarning] = []
    emitted_numbering_issues: set[int] = set()

    allowed_step_lines: set[int] = (
        {
            index
            for index, block in enumerate(content_classifications)
            if block.kind == "procedure-step"
        }
        if extraction_allowed
        else set()
    )
    section_context = preceding_heading.title if preceding_heading is not None else top_title
    section_contexts: list[str] = []
    section_ids: list[int] = []
    section_id = 0
    for line in content_lines:
        heading = next(
            (
                headings_by_span[span.span_id]
                for span in line.spans
                if span.span_id in headings_by_span
            ),
            None,
        )
        if heading is not None:
            section_context = heading.title
            section_id += 1
        section_contexts.append(section_context)
        section_ids.append(section_id)
    step_starts, rejected_step_candidates, numbering_issues = _step_starts(
        content_lines,
        classifications=content_classifications,
        allowed=allowed_step_lines,
        section_contexts=section_contexts,
        section_ids=section_ids,
        profile=profile,
    )
    start_by_index = {start.line_index: start for start in step_starts}
    index = 0
    heading_count = 0
    while index < len(content_lines):
        line = content_lines[index]
        heading = next(
            (
                headings_by_span[span.span_id]
                for span in line.spans
                if span.span_id in headings_by_span
            ),
            None,
        )
        if heading is not None:
            next_path = list(heading.heading_path)
            if heading_count > 0 or next_path != current_path:
                section_sequence += 1
            heading_events.append(
                _HeadingEvent(
                    physical_page=physical_page,
                    line_index=index,
                    level=heading.level,
                    heading_path=next_path,
                )
            )
            heading_count += 1
            current_title = heading.title
            current_path = next_path
            current_level = heading.level
            section_paths[section_sequence] = list(current_path)
            current_step = None
            pending_warnings.clear()
            blocks.append(
                _classified_evidence(
                    EvidenceBlock(
                        kind="heading",
                        text=line.text,
                        heading_path=list(current_path),
                    ),
                    content_classifications[index],
                )
            )
            index += 1
            continue

        line_text = line.text
        if NAVIGATION_CUE.match(line_text) or TRUNCATION_CUE.search(line_text):
            completeness_notes.setdefault(section_sequence, []).append(line_text)
            completeness_note_events.append(
                _TextEvent(
                    physical_page=physical_page,
                    line_index=index,
                    text=line_text,
                )
            )
        if _matches_procedure_end(line_text, profile.end_boundaries.markers):
            end_marker_events.append(
                _TextEvent(
                    physical_page=physical_page,
                    line_index=index,
                    text=line_text,
                )
            )
            section_numbers = [
                parsed_step.step.number
                for parsed_step in steps
                if parsed_step.section_sequence == section_sequence
            ]
            end_evidence.setdefault(section_sequence, []).append(
                ProcedureEndEvidence(
                    text=line_text,
                    after_step=section_numbers[-1] if section_numbers else 0,
                )
            )

        warning_severity = _warning_severity(line.text)
        if warning_severity is not None:
            warning_classification = content_classifications[index]
            warning_text, index, warning_spans = _collect_warning(
                content_lines,
                index,
                column_id=line.column_id,
                markers=profile.end_boundaries.markers,
            )
            blocks.append(
                _classified_evidence(
                    EvidenceBlock(
                        kind="warning",
                        text=warning_text,
                        heading_path=list(current_path),
                    ),
                    warning_classification,
                )
            )
            warning = StoredProcedureWarning(
                severity=warning_severity,
                text=warning_text,
                evidence=_source_excerpt(
                    warning_spans,
                    printed_page=printed_page,
                    section=current_title,
                    heading_path=list(current_path),
                ),
            )
            warning_issues = _source_excerpt_issues(
                warning.evidence,
                StoredCitation(
                    document_id=source_id,
                    title=source_title,
                    manufacturer=manufacturer,
                    printed_page=printed_page,
                    physical_page=physical_page,
                    section=current_title,
                    retrieval_date=retrieval_date,
                    source_manifest_version=manifest_version,
                ),
                source_document_id=source_id,
                source_spans=layout.spans,
                source_printed_page=printed_page,
                expected_text=warning_text,
                expected_kind="warning",
                expected_heading_path=current_path,
            )
            if current_step is None:
                if not warning_issues:
                    pending_warnings.append(warning)
                else:
                    pending_warnings.clear()
            else:
                if warning_issues:
                    step_issues.setdefault(section_sequence, []).extend(
                        f"step {current_step.number}: {issue}" for issue in warning_issues
                    )
                    steps[:] = [parsed for parsed in steps if parsed.step is not current_step]
                    current_step = None
                else:
                    current_step.warnings.append(warning)
            continue

        step = start_by_index.get(index)
        if step is not None:
            step_column_id = content_lines[step.line_index].column_id
            body_lines: list[str] = [step.text]
            body_spans: list[LayoutSpan] = list(content_lines[step.line_index].spans)
            index += 1
            while index < len(content_lines) and index not in start_by_index:
                candidate = content_lines[index]
                if candidate.column_id != step_column_id:
                    break
                candidate_classification = content_classifications[index]
                if (
                    _warning_severity(candidate.text) is not None
                    or SERVICE_HEADING.fullmatch(candidate.text) is not None
                    or candidate_classification.kind in {"figure", "table", "warning", "heading"}
                    or any(span.span_id in headings_by_span for span in candidate.spans)
                    or INLINE_STEP.match(candidate.text) is not None
                    or STEP_NUMBER.fullmatch(candidate.text) is not None
                ):
                    break
                candidate_text = candidate.text
                if NAVIGATION_CUE.match(candidate_text) or TRUNCATION_CUE.search(candidate_text):
                    completeness_notes.setdefault(section_sequence, []).append(candidate_text)
                    completeness_note_events.append(
                        _TextEvent(
                            physical_page=physical_page,
                            line_index=index,
                            text=candidate_text,
                        )
                    )
                if _matches_procedure_end(candidate_text, profile.end_boundaries.markers):
                    end_marker_events.append(
                        _TextEvent(
                            physical_page=physical_page,
                            line_index=index,
                            text=candidate_text,
                        )
                    )
                    end_evidence.setdefault(section_sequence, []).append(
                        ProcedureEndEvidence(text=candidate_text, after_step=step.number)
                    )
                    index += 1
                    break
                if (
                    candidate_text
                    and not STEP_NUMBER.fullmatch(candidate_text)
                    and "Proceed to" not in candidate_text
                    and not NAVIGATION_CUE.match(candidate_text)
                ):
                    body_lines.append(candidate_text)
                    body_spans.extend(candidate.spans)
                index += 1
            text = normalize_pdf_text("\n".join(body_lines))
            citation = StoredCitation(
                document_id=source_id,
                title=source_title,
                manufacturer=manufacturer,
                printed_page=printed_page,
                physical_page=physical_page,
                section=current_title,
                retrieval_date=retrieval_date,
                source_manifest_version=manifest_version,
            )
            evidence = _source_excerpt(
                body_spans,
                printed_page=printed_page,
                section=current_title,
                heading_path=list(current_path),
            )
            procedure_step = StoredProcedureStep(
                number=step.number,
                text=text,
                warnings=list(pending_warnings),
                citation=citation,
                evidence=evidence,
            )
            issues = _source_excerpt_issues(
                procedure_step.evidence,
                procedure_step.citation,
                source_document_id=source_id,
                source_spans=layout.spans,
                source_printed_page=printed_page,
                expected_text=procedure_step.text,
                expected_kind="step",
                expected_heading_path=current_path,
            )
            pending_warnings.clear()
            section_id = section_ids[step.number_line_index]
            if section_id in numbering_issues and section_id not in emitted_numbering_issues:
                step_issues.setdefault(section_sequence, []).append(numbering_issues[section_id])
                emitted_numbering_issues.add(section_id)
            step_issues.setdefault(section_sequence, []).extend(
                f"step {step.number}: {issue}" for issue in issues
            )
            if issues:
                logger.debug(
                    "procedure-evidence-rejected document=%s page=%d step=%d issues=%s",
                    source_id,
                    physical_page,
                    step.number,
                    issues,
                )
            blocks.append(
                _classified_evidence(
                    EvidenceBlock(kind="step", text=text, heading_path=list(current_path)),
                    content_classifications[step.number_line_index],
                )
            )
            if issues:
                current_step = None
                rejected_step_candidates.append(
                    RejectedStepCandidate(
                        line_id=content_lines[step.number_line_index].spans[0].line_id,
                        text=step.text,
                        reason="evidence-mismatch",
                    )
                )
                continue
            steps.append(
                _ParsedStep(
                    step=procedure_step,
                    section_sequence=section_sequence,
                    section_title=current_title,
                    heading_path=list(current_path),
                    line_index=step.line_index,
                    section_level=current_level,
                )
            )
            current_step = procedure_step
            continue

        raw_line_text = line.raw_text
        spaced_cells = [cell.strip() for cell in re.split(r"\s{2,}", raw_line_text) if cell.strip()]
        cells = (
            spaced_cells
            if len(spaced_cells) >= 3
            else [span.text for span in line.spans if span.text]
        )
        kind: Literal["paragraph", "table"] = (
            "table" if len(cells) >= 3 and _has_table_spacing(line, spaced_cells) else "paragraph"
        )
        blocks.append(
            _classified_evidence(
                EvidenceBlock(
                    kind=kind,
                    text=line.text,
                    heading_path=list(current_path),
                    cells=cells if kind == "table" else [],
                ),
                content_classifications[index],
            )
        )
        index += 1

    ingestion_outcome, ingestion_outcome_reason = _page_ingestion_outcome(classification)
    page_model = RetrievalPage(
        physical_page=physical_page,
        printed_page=printed_page,
        section=section_title,
        heading_path=current_path,
        page_width=layout.page_width,
        page_height=layout.page_height,
        extraction_language=extraction_language,
        columns=layout.columns,
        spans=layout.spans,
        reading_order=layout.reading_order,
        languages=layout.languages,
        page_kind=classification.page_kind,
        ingestion_outcome=ingestion_outcome,
        ingestion_outcome_reason=ingestion_outcome_reason,
        classification_confidence=classification.confidence,
        classification_uncertain=classification.uncertain,
        classification_uncertainty=classification.rejection_reason,
        text=raw_text,
        blocks=blocks,
        rejected_step_candidates=rejected_step_candidates,
    )
    return _PageParse(
        page=page_model,
        steps=steps,
        step_issues=step_issues,
        end_evidence=end_evidence,
        completeness_notes=completeness_notes,
        heading_events=heading_events,
        end_marker_events=end_marker_events,
        completeness_note_events=completeness_note_events,
        section_paths=section_paths,
        heading_stack=_active_heading_stack(
            heading_hierarchy.headings,
            preceding_headings,
        ),
        document_id=source_id,
    )


def _active_heading_stack(
    current: Sequence[HeadingNode],
    preceding: Sequence[HeadingNode],
) -> list[HeadingNode]:
    if not current:
        return list(preceding)
    headings_by_id = {heading.heading_id: heading for heading in [*preceding, *current]}
    stack: list[HeadingNode] = []
    seen: set[str] = set()
    cursor: HeadingNode | None = current[-1]
    while cursor is not None and cursor.heading_id not in seen:
        stack.append(cursor)
        seen.add(cursor.heading_id)
        cursor = (
            headings_by_id.get(cursor.parent_heading_id)
            if cursor.parent_heading_id is not None
            else None
        )
    stack.reverse()
    return stack


def _classified_evidence(
    block: EvidenceBlock,
    classification: BlockClassification,
) -> EvidenceBlock:
    return block.model_copy(
        update={
            "classified_kind": classification.kind,
            "classification_confidence": classification.confidence,
            "classification_uncertainty": classification.uncertainty,
        }
    )


def _page_ingestion_outcome(
    classification: PageBlockClassificationResult,
) -> tuple[PageIngestionOutcome, str | None]:
    if classification.page_kind == "figure":
        return (
            "transcription-required",
            "figure and scanned content requires human-verified transcription",
        )
    content_blocks = [block for block in classification.blocks if block.kind != "heading"]
    if content_blocks and all(block.kind == "figure" for block in content_blocks):
        return (
            "transcription-required",
            "callout-only content requires human-verified transcription",
        )
    if classification.uncertain and classification.rejection_reason == (
        "the page has no extractable text"
    ):
        return (
            "transcription-required",
            "scanned content has no extractable text and requires human-verified transcription",
        )
    if classification.uncertain:
        return (
            "uncertain",
            classification.rejection_reason or "page classification is uncertain",
        )
    return "answer-eligible", None


def _page_layout(
    page: Any,
    *,
    document_id: str,
    physical_page: int,
    profile: DocumentProfile,
) -> LayoutStageResult:
    page_width = float(page.mediabox.width)
    page_height = float(page.mediabox.height)
    fragments = _extract_text_fragments(page)
    columns = (
        list(profile.layout.columns)
        if profile.layout.columns
        else _detect_columns(fragments, page_width=page_width)
    )
    for fragment in fragments:
        fragment.column_id = _column_for_fragment(
            fragment,
            columns,
            page_width=page_width,
        ).id
        fragment.language = _fragment_language(
            fragment,
            profile,
            page_width=page_width,
            page_height=page_height,
        )
    ordered_columns = sorted(
        columns,
        key=lambda column: column.x_min,
        reverse=profile.layout.reading_order == "right-to-left",
    )
    spans: list[LayoutSpan] = []
    line_index = 0
    for column in ordered_columns:
        column_fragments = sorted(
            (fragment for fragment in fragments if fragment.column_id == column.id),
            key=lambda fragment: (-fragment.y, fragment.x),
        )
        lines: list[list[_Fragment]] = []
        for fragment in column_fragments:
            if lines and abs(lines[-1][0].y - fragment.y) <= 1.5:
                lines[-1].append(fragment)
            else:
                lines.append([fragment])
        for line_fragments in lines:
            line_fragments.sort(key=lambda fragment: fragment.x)
            line_id = f"{document_id}:p{physical_page}:l{line_index}"
            for span_index, fragment in enumerate(line_fragments):
                span_id = f"{line_id}:s{span_index}"
                fragment.span_id = span_id
                fragment.line_id = line_id
                spans.append(
                    LayoutSpan(
                        span_id=span_id,
                        line_id=line_id,
                        document_id=document_id,
                        physical_page=physical_page,
                        column_id=column.id,
                        raw_text=fragment.raw_text,
                        text=fragment.text,
                        box=_normalized_box(
                            fragment.x,
                            fragment.x + fragment.width,
                            fragment.y - fragment.height * 0.2,
                            fragment.y + fragment.height * 0.9,
                            page_width,
                            page_height,
                        ),
                        page_box=PageBox(
                            x_min=fragment.x,
                            x_max=fragment.x + fragment.width,
                            y_min=fragment.y - fragment.height * 0.2,
                            y_max=fragment.y + fragment.height * 0.9,
                        ),
                        font_name=fragment.font_name,
                        font_size=fragment.font_size,
                        font_weight=fragment.font_weight,
                        bold=fragment.bold,
                        italic=fragment.italic,
                        language=fragment.language,
                    )
                )
            line_index += 1
    languages = list(dict.fromkeys(span.language for span in spans if span.language is not None))
    return LayoutStageResult(
        document_id=document_id,
        physical_page=physical_page,
        page_width=page_width,
        page_height=page_height,
        columns=columns,
        spans=spans,
        reading_order=[span.span_id for span in spans],
        languages=languages,
    )


def _extract_text_fragments(page: Any) -> list[_Fragment]:
    fragments: list[_Fragment] = []

    def visitor(text: str, cm: Any, tm: Any, font_dict: Any, font_size: Any) -> None:
        if not text.strip():
            return
        x, y, scale_x, scale_y = _text_position(cm, tm)
        font_name, font_weight, bold, italic = _font_metadata(font_dict)
        size = float(font_size or 10.0)
        line_height = max(1.0, size * max(scale_y, 0.1))
        for offset, part in enumerate(text.splitlines()):
            raw_text = part.strip()
            normalized = normalize_pdf_text(raw_text)
            if not normalized:
                continue
            fragments.append(
                _Fragment(
                    text=normalized,
                    raw_text=raw_text,
                    x=x,
                    y=y - offset * line_height,
                    width=max(1.0, size * max(scale_x, 0.1) * len(normalized) * 0.52),
                    height=line_height,
                    span_id="",
                    line_id="",
                    column_id="",
                    language="",
                    font_name=font_name,
                    font_size=size,
                    font_weight=font_weight,
                    bold=bold,
                    italic=italic,
                )
            )

    page.extract_text(visitor_text=visitor)
    return fragments


def _lines_from_layout(layout: LayoutStageResult, *, language: str) -> list[_Line]:
    lines: dict[str, list[LayoutSpan]] = {}
    for span in layout.spans:
        if span.language != language:
            continue
        lines.setdefault(span.line_id, []).append(span)
    return [_Line(spans=spans) for spans in lines.values()]


def _text_position(cm: Any, tm: Any) -> tuple[float, float, float, float]:
    cm_values = [float(value) for value in cm[:6]]
    tm_values = [float(value) for value in tm[:6]]
    x = tm_values[4] * cm_values[0] + tm_values[5] * cm_values[2] + cm_values[4]
    y = tm_values[4] * cm_values[1] + tm_values[5] * cm_values[3] + cm_values[5]
    scale_x = abs(tm_values[0] * cm_values[0]) + abs(tm_values[1] * cm_values[2])
    scale_y = abs(tm_values[2] * cm_values[1]) + abs(tm_values[3] * cm_values[3])
    return x, y, max(scale_x, 0.1), max(scale_y, 0.1)


def _font_metadata(font_dict: Any) -> tuple[str | None, int | None, bool, bool]:
    if font_dict is None:
        return None, None, False, False
    descriptor = font_dict.get("/FontDescriptor")
    if descriptor is not None:
        descriptor = descriptor.get_object()
    base_font = _pdf_name(font_dict.get("/BaseFont"))
    descriptor_name = _pdf_name(descriptor.get("/FontName")) if descriptor is not None else None
    font_name = base_font or descriptor_name
    normalized_name = (font_name or "").casefold()
    weight_value = descriptor.get("/FontWeight") if descriptor is not None else None
    try:
        font_weight = int(weight_value) if weight_value is not None else None
    except (TypeError, ValueError):
        font_weight = None
    flags = 0
    italic_angle = 0.0
    stem_v = 0.0
    if descriptor is not None:
        try:
            flags = int(descriptor.get("/Flags", 0))
        except (TypeError, ValueError):
            flags = 0
        try:
            italic_angle = float(descriptor.get("/ItalicAngle", 0))
        except (TypeError, ValueError):
            italic_angle = 0.0
        try:
            stem_v = float(descriptor.get("/StemV", 0))
        except (TypeError, ValueError):
            stem_v = 0.0
    bold = (
        (font_weight is not None and font_weight >= 600)
        or bool(flags & (1 << 18))
        or stem_v >= 120
        or any(hint in normalized_name for hint in ("bold", "black", "heavy", "semibold"))
    )
    italic = (
        abs(italic_angle) > 0.01
        or bool(flags & (1 << 6))
        or any(hint in normalized_name for hint in ("italic", "oblique"))
    )
    return font_name, font_weight, bold, italic


def _pdf_name(value: Any) -> str | None:
    if value is None:
        return None
    name = str(value).strip()
    return name.lstrip("/") or None


def _detect_columns(fragments: list[_Fragment], *, page_width: float) -> list[ColumnBand]:
    usable = [
        fragment
        for fragment in fragments
        if len(fragment.text.split()) >= 2 and fragment.width < page_width * 0.7
    ]
    if len(usable) < 4:
        return [ColumnBand(id="full", x_min=0.0, x_max=1.0)]
    bin_count = 200
    occupied = [False] * bin_count
    for fragment in usable:
        start = max(0, int(fragment.x / page_width * bin_count))
        end = min(bin_count, int((fragment.x + fragment.width) / page_width * bin_count) + 1)
        for index in range(start, end):
            occupied[index] = True
    first = next(index for index, value in enumerate(occupied) if value)
    last = bin_count - 1 - next(index for index, value in enumerate(reversed(occupied)) if value)
    boundaries: list[float] = []
    index = first
    while index <= last:
        if occupied[index]:
            index += 1
            continue
        gap_start = index
        while index <= last and not occupied[index]:
            index += 1
        gap_end = index
        if gap_end - gap_start < 8:
            continue
        left_x = gap_start / bin_count
        right_x = gap_end / bin_count
        left = [
            fragment
            for fragment in usable
            if fragment.x + fragment.width <= gap_start / bin_count * page_width
        ]
        right = [fragment for fragment in usable if fragment.x >= gap_end / bin_count * page_width]
        if (
            len(left) >= 2
            and len(right) >= 2
            and len({round(fragment.y, 1) for fragment in left}) >= 2
            and len({round(fragment.y, 1) for fragment in right}) >= 2
        ):
            boundaries.append((left_x + right_x) / 2)
    if not boundaries:
        return [ColumnBand(id="full", x_min=0.0, x_max=1.0)]
    if len(boundaries) == 1:
        names = ["auto-left", "auto-right"]
    elif len(boundaries) == 2:
        names = ["auto-left", "auto-middle", "auto-right"]
    else:
        names = [f"auto-{index + 1}" for index in range(len(boundaries) + 1)]
    edges = [0.0, *boundaries, 1.0]
    return [
        ColumnBand(id=name, x_min=edges[index], x_max=edges[index + 1])
        for index, name in enumerate(names)
    ]


def _column_for_fragment(
    fragment: _Fragment,
    columns: Sequence[ColumnBand],
    *,
    page_width: float,
) -> ColumnBand:
    center_x = fragment.x + fragment.width / 2
    normalized_x = center_x / page_width
    return next(
        (column for column in columns if column.x_min <= normalized_x <= column.x_max),
        min(columns, key=lambda column: abs((column.x_min + column.x_max) / 2 - normalized_x)),
    )


def _fragment_language(
    fragment: _Fragment,
    profile: DocumentProfile,
    *,
    page_width: float,
    page_height: float,
) -> str:
    center_x = (fragment.x + fragment.width / 2) / page_width
    center_y = (fragment.y + fragment.height / 2) / page_height
    region = next(
        (
            region
            for region in profile.language.regions
            if region.box.x_min <= center_x <= region.box.x_max
            and region.box.y_min <= center_y <= region.box.y_max
        ),
        None,
    )
    if region is not None:
        return region.language
    return _detect_language_hint(fragment.text) or profile.language.primary_language


def _detect_language_hint(text: str) -> str | None:
    if re.search(r"[\u0400-\u04ff]", text):
        return "ru"
    if re.search(r"[\u0600-\u06ff]", text):
        return "ar"
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    words = set(re.findall(r"[a-zäöüß]+", text.casefold()))
    if any(char in text.casefold() for char in ("ä", "ö", "ü", "ß")):
        return "de"
    hints = {
        "de": {"der", "die", "das", "und", "sie", "den", "mit", "nicht", "fest"},
        "en": {"the", "and", "with", "remove", "install", "loosen", "tighten", "concludes"},
        "es": {"el", "los", "las", "con", "para", "quitar", "instalar", "apretar", "aflojar"},
        "fr": {
            "le",
            "la",
            "les",
            "des",
            "une",
            "et",
            "avec",
            "pour",
            "retirez",
            "installez",
            "serrez",
        },
        "it": {"gli", "con", "per", "rimuovere", "installare", "serrare", "allentare"},
        "nl": {"het", "een", "met", "voor", "verwijderen", "installeren", "vastdraaien"},
        "pt": {"os", "com", "para", "remover", "instalar", "apertar", "soltar"},
    }
    scores = {language: len(words & candidates) for language, candidates in hints.items()}
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if ranked[0][1] >= 2 and ranked[0][1] > ranked[1][1]:
        return ranked[0][0]
    return None


def _normalized_box(
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    page_width: float,
    page_height: float,
) -> NormalizedBox:
    safe_x_min = min(0.999, max(0.0, x_min / page_width))
    safe_x_max = min(1.0, max(safe_x_min + 0.001, x_max / page_width))
    safe_y_min = min(0.999, max(0.0, y_min / page_height))
    safe_y_max = min(1.0, max(safe_y_min + 0.001, y_max / page_height))
    return NormalizedBox(
        x_min=safe_x_min,
        y_min=safe_y_min,
        x_max=safe_x_max,
        y_max=safe_y_max,
    )


def _printed_page_and_title(text: str, physical_page: int) -> tuple[int, str]:
    match = re.match(r"^(\d{1,3})(?:\s+|(?=[A-Z]))(.+)$", text)
    if match is None:
        return physical_page, text
    return int(match.group(1)), match.group(2).strip()


def _matches_procedure_end(text: str, markers: Sequence[str]) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(marker)}(?!\w)", text, flags=re.IGNORECASE)
        for marker in markers
    )


def _step_starts(
    lines: list[_Line],
    *,
    classifications: Sequence[BlockClassification],
    allowed: set[int] | None = None,
    section_contexts: Sequence[str],
    section_ids: Sequence[int],
    profile: DocumentProfile,
) -> tuple[list[_StepStart], list[RejectedStepCandidate], dict[int, str]]:
    starts: list[_StepStart] = []
    rejected: list[RejectedStepCandidate] = []
    linked_content: set[int] = set()
    for index, line in enumerate(lines):
        if classifications[index].kind == "heading":
            continue
        inline = INLINE_STEP.match(line.text)
        if inline is not None:
            text = inline.group(2).strip()
            reason = _step_rejection_reason(
                text,
                classification=classifications[index],
                allowed=allowed is not None and index in allowed,
                section_context=section_contexts[index],
                profile=profile,
                mixed_column=_has_mixed_columns(line),
            )
            if reason is not None:
                rejected.append(
                    RejectedStepCandidate(
                        line_id=line.spans[0].span_id,
                        text=text,
                        reason=reason,
                    )
                )
                continue
            starts.append(
                _StepStart(
                    int(inline.group(1)),
                    index,
                    index,
                    text,
                )
            )
            continue
        if not STEP_NUMBER.fullmatch(line.text):
            continue
        candidates = [
            candidate_index
            for candidate_index, candidate in enumerate(lines)
            if candidate_index != index
            and 60 < candidate.x < 75
            and candidate_index not in linked_content
            and 0 <= candidate.y - line.y <= 10
        ]
        if candidates:
            content_index = min(candidates, key=lambda candidate: abs(lines[candidate].y - line.y))
            linked_content.add(content_index)
            text = lines[content_index].text
            reason = _step_rejection_reason(
                text,
                classification=classifications[content_index],
                allowed=allowed is not None and content_index in allowed,
                section_context=section_contexts[content_index],
                profile=profile,
                mixed_column=_has_mixed_columns(lines[content_index]),
            )
            if reason is not None:
                rejected.append(
                    RejectedStepCandidate(
                        line_id=line.spans[0].span_id,
                        text=text,
                        reason=reason,
                    )
                )
                continue
            starts.append(
                _StepStart(
                    int(line.text),
                    index,
                    content_index,
                    text,
                )
            )
        else:
            rejected.append(
                RejectedStepCandidate(
                    line_id=line.spans[0].span_id,
                    text=line.text,
                    reason="missing-action-text",
                )
            )
    starts_by_section: dict[int, list[_StepStart]] = {}
    for start in starts:
        starts_by_section.setdefault(section_ids[start.line_index], []).append(start)
    accepted: list[_StepStart] = []
    numbering_issues: dict[int, str] = {}
    for section_id, section_starts in starts_by_section.items():
        numbers = [start.number for start in section_starts]
        if any(right == left for left, right in pairwise(numbers)):
            accepted.extend(section_starts)
            continue
        first_break = next(
            (index for index, (left, right) in enumerate(pairwise(numbers)) if right != left + 1),
            None,
        )
        if first_break is None:
            accepted.extend(section_starts)
        else:
            accepted.extend(section_starts[: first_break + 1])
            numbering_issues[section_id] = (
                f"numbered step {numbers[first_break + 1]} is discontinuous "
                f"after step {numbers[first_break]}"
            )
            rejected.extend(
                RejectedStepCandidate(
                    line_id=lines[start.line_index].spans[0].span_id,
                    text=start.text,
                    reason="numbering-discontinuous",
                )
                for start in section_starts[first_break + 1 :]
            )
    line_positions = {line.spans[0].span_id: index for index, line in enumerate(lines)}
    return (
        sorted(accepted, key=lambda start: start.line_index),
        sorted(rejected, key=lambda candidate: line_positions[candidate.line_id]),
        numbering_issues,
    )


MEASUREMENT_VALUE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:N\s*[·.]?\s*m|Nm|mm|cm|in(?:-lb)?|lbf|lb-ft)\b",
    re.IGNORECASE,
)
SOURCE_REFERENCE = re.compile(
    r"(?:\.{3,}\s*\d{1,3}\s*$|"
    r"\b(?:see|refer to)\s+(?:section|page)\b|"
    r"\b(?:section|page)\s+\d{1,3}\s*$)",
    re.IGNORECASE,
)
FIGURE_CALLOUT = re.compile(r"^(?:figure|fig\.|illustration|diagram)\b", re.IGNORECASE)


def _step_rejection_reason(
    text: str,
    *,
    classification: BlockClassification,
    allowed: bool,
    section_context: str,
    profile: DocumentProfile,
    mixed_column: bool,
) -> StepRejectionReason | None:
    if SOURCE_REFERENCE.search(text):
        return "source-reference"
    if classification.kind == "table" or MEASUREMENT_VALUE.search(text):
        return "table-value"
    if classification.kind == "figure" or FIGURE_CALLOUT.search(text):
        return "figure-callout"
    if mixed_column:
        return "mixed-column"
    if not text or not any(character.isalpha() for character in text):
        return "missing-action-text"
    if not _contains_procedure_action(text, profile) and len(re.findall(r"[^\W_]+", text)) < 2:
        return "missing-action-text"
    if not _is_procedure_section_heading(section_context, profile):
        return "missing-procedure-heading"
    if not allowed or classification.kind != "procedure-step":
        return "non-procedure-block"
    return None


def _has_mixed_columns(line: _Line) -> bool:
    spans = sorted(line.spans, key=lambda span: span.page_box.x_min)
    return any(
        right.page_box.x_min - left.page_box.x_max >= 0.18 for left, right in pairwise(spans)
    )


def _is_procedure_section_heading(text: str, profile: DocumentProfile) -> bool:
    normalized = re.sub(r"^\s*(?:\d+(?:\.\d+)*[.)]?\s+)", "", text).casefold()
    return _contains_procedure_action(normalized, profile)


def _contains_procedure_action(text: str, profile: DocumentProfile) -> bool:
    normalized = text.casefold()
    aliases = {
        variant.casefold()
        for action, variants in profile.action_aliases.items()
        for variant in (action, *variants)
        if variant.strip()
    }
    if any(alias in normalized for alias in aliases):
        return True
    words = re.findall(r"[^\W_]+", normalized)
    return any(
        word
        in {
            action,
            f"{action}s",
            f"{action}ed",
            f"{action}ing",
            *PROCEDURE_HEADING_ACTION_FORMS.get(action, set()),
        }
        or (action.endswith("e") and word in {f"{action}d", f"{action[:-1]}ing"})
        for word in words
        for action in PROCEDURE_HEADING_ACTIONS
    )


def _collect_warning(
    lines: list[_Line],
    heading_index: int,
    *,
    column_id: str,
    markers: Sequence[str],
) -> tuple[str, int, list[LayoutSpan]]:
    heading = lines[heading_index].text
    severity = _warning_severity(heading)
    assert severity is not None
    body: list[str] = []
    evidence_spans = list(lines[heading_index].spans)
    last_y = lines[heading_index].y
    index = heading_index + 1
    while index < len(lines):
        line = lines[index]
        if line.column_id != column_id:
            break
        text = line.text
        if not text or STEP_NUMBER.fullmatch(text) or INLINE_STEP.match(text):
            break
        if (
            NAVIGATION_CUE.match(text)
            or TRUNCATION_CUE.search(text)
            or _matches_procedure_end(text, markers)
        ):
            break
        if last_y - line.y > 25:
            break
        body.append(text)
        evidence_spans.extend(line.spans)
        last_y = line.y
        index += 1
    return normalize_pdf_text("\n".join(body)), index, evidence_spans


def _warning_severity(text: str) -> Literal["warning", "notice"] | None:
    normalized = text.strip().upper().lstrip("⚠ ")
    return WARNING_HEADINGS.get(normalized)


def _has_table_spacing(line: _Line, spaced_cells: list[str]) -> bool:
    if len(spaced_cells) >= 3 and _looks_like_table_cells(spaced_cells):
        return True
    xs = sorted(span.page_box.x_min for span in line.spans)
    return (
        len(xs) >= 3
        and all(right - left >= 20 for left, right in pairwise(xs))
        and _looks_like_table_cells([span.text for span in line.spans])
    )


def _looks_like_table_cells(cells: list[str]) -> bool:
    numeric_cells = sum(any(character.isdigit() for character in cell) for cell in cells)
    return numeric_cells >= 2 or all(len(cell.split()) <= 6 for cell in cells)


def _heading_follows_position(
    heading_lines_by_page: dict[int, list[int]],
    position: tuple[int, int],
) -> bool:
    physical_page, line_index = position
    return any(
        heading_line > line_index for heading_line in heading_lines_by_page.get(physical_page, [])
    )


def _heading_between_positions(
    heading_lines_by_page: dict[int, list[int]],
    after: tuple[int, int],
    before: tuple[int, int],
) -> bool:
    return any(
        after < (physical_page, line_index) < before
        for physical_page, line_indexes in heading_lines_by_page.items()
        for line_index in line_indexes
    )


def _section_start_position(
    parsed_pages: Sequence[_PageParse],
    *,
    after: tuple[int, int],
    heading_path: list[str],
    fallback: tuple[int, int],
) -> tuple[int, int]:
    candidates = [
        (event.physical_page, event.line_index)
        for parsed in parsed_pages
        for event in parsed.heading_events
        if (event.physical_page, event.line_index) > after
        and event.heading_path == heading_path[: len(event.heading_path)]
    ]
    return min(candidates, default=fallback)


def _group_procedures(
    parsed_pages: list[_PageParse],
    end_profile: EndBoundaryProfile,
) -> list[StoredProcedure]:
    grouped: dict[_ProcedureGroupingKey, list[StoredProcedureStep]] = {}
    paths: dict[_ProcedureGroupingKey, list[str]] = {}
    page_numbers: dict[_ProcedureGroupingKey, list[int]] = {}
    step_issues: dict[_ProcedureGroupingKey, list[str]] = {}
    end_evidence: dict[_ProcedureGroupingKey, list[ProcedureEndEvidence]] = {}
    completeness_notes: dict[_ProcedureGroupingKey, list[str]] = {}
    section_levels: dict[_ProcedureGroupingKey, int] = {}
    final_positions: dict[_ProcedureGroupingKey, tuple[int, int]] = {}
    grouping_decisions: dict[_ProcedureGroupingKey, list[ProcedureGroupingDecision]] = {}
    previous_key_by_title: dict[tuple[str, str], _ProcedureGroupingKey] = {}
    order: list[_ProcedureGroupingKey] = []
    active_key: _ProcedureGroupingKey | None = None
    previous_page: int | None = None
    section_run = 0
    heading_lines_by_page: dict[int, list[int]] = {}
    for parsed in parsed_pages:
        for event in parsed.heading_events:
            heading_lines_by_page.setdefault(event.physical_page, []).append(event.line_index)

    for parsed in parsed_pages:
        page_sections: list[int] = []
        for parsed_step in parsed.steps:
            if not page_sections or page_sections[-1] != parsed_step.section_sequence:
                page_sections.append(parsed_step.section_sequence)

        for position, sequence in enumerate(page_sections):
            section_steps = [
                parsed_step
                for parsed_step in parsed.steps
                if parsed_step.section_sequence == sequence
            ]
            title = section_steps[0].section_title
            heading_path = section_steps[0].heading_path
            first_step_number = section_steps[0].step.number
            current_section_position = (parsed.page.physical_page, section_steps[0].line_index)
            for event in parsed.heading_events:
                if event.line_index < section_steps[0].line_index:
                    current_section_position = (event.physical_page, event.line_index)
            active_last_step = (
                grouped[active_key][-1].number
                if active_key is not None and grouped[active_key]
                else None
            )
            active_ended = (
                active_key is not None
                and active_last_step is not None
                and any(
                    evidence.after_step == active_last_step for evidence in end_evidence[active_key]
                )
            )
            active_interrupted = active_key is not None and _heading_follows_position(
                heading_lines_by_page,
                final_positions[active_key],
            )
            continues = (
                position == 0
                and active_key is not None
                and active_key[0] == parsed.document_id
                and active_key[1] == title
                and paths[active_key] == heading_path
                and previous_page is not None
                and parsed.page.physical_page == previous_page + 1
                and not active_ended
                and not active_interrupted
                and active_last_step is not None
                and first_step_number > 1
            )
            if continues:
                key = active_key
                assert key is not None
                assert active_last_step is not None
                continuation_reason = (
                    "continued step numbering on the adjacent page"
                    if first_step_number == active_last_step + 1
                    else "resumed non-initial step numbering on the adjacent page"
                )
                grouping_decisions[key].append(
                    ProcedureGroupingDecision(
                        decision="merged",
                        reason=continuation_reason,
                        pages=[page_numbers[key][-1], parsed.page.physical_page],
                    )
                )
            else:
                key = (parsed.document_id, title, tuple(heading_path), section_run)
                section_run += 1
                grouped[key] = []
                paths[key] = heading_path
                page_numbers[key] = []
                step_issues[key] = []
                end_evidence[key] = []
                completeness_notes[key] = []
                grouping_decisions[key] = []
                section_levels[key] = section_steps[0].section_level
                order.append(key)
                previous_key = previous_key_by_title.get((parsed.document_id, title))
                if previous_key is not None:
                    prior_page = page_numbers[previous_key][-1]
                    prior_last_step = grouped[previous_key][-1].number
                    prior_ended = any(
                        evidence.after_step == prior_last_step
                        for evidence in end_evidence[previous_key]
                    )
                    prior_interrupted = _heading_between_positions(
                        heading_lines_by_page,
                        final_positions[previous_key],
                        _section_start_position(
                            parsed_pages,
                            after=final_positions[previous_key],
                            heading_path=heading_path,
                            fallback=current_section_position,
                        ),
                    )
                    if prior_interrupted:
                        reason = "an intervening heading ended the prior section"
                    elif paths[previous_key] != heading_path:
                        reason = "heading path differs from the repeated title"
                    elif first_step_number == 1:
                        reason = "repeated title started again at step 1"
                    elif prior_ended:
                        reason = "previous procedure ended before the repeated title"
                    elif position != 0 or parsed.page.physical_page != prior_page + 1:
                        reason = "repeated title is not the first section on an adjacent page"
                    else:
                        reason = "repeated title did not continue the prior step numbering"
                    grouping_decisions[key].append(
                        ProcedureGroupingDecision(
                            decision="kept-separate",
                            reason=reason,
                            pages=sorted({prior_page, parsed.page.physical_page}),
                        )
                    )
                previous_key_by_title[(parsed.document_id, title)] = key

            grouped[key].extend(parsed_step.step for parsed_step in section_steps)
            if parsed.page.physical_page not in page_numbers[key]:
                page_numbers[key].append(parsed.page.physical_page)
            step_issues[key].extend(parsed.step_issues.get(sequence, []))
            end_evidence[key].extend(parsed.end_evidence.get(sequence, []))
            completeness_notes[key].extend(parsed.completeness_notes.get(sequence, []))
            final_positions[key] = (
                parsed.page.physical_page,
                section_steps[-1].line_index,
            )
            active_key = key
            previous_page = parsed.page.physical_page

    procedures: list[StoredProcedure] = []
    for key in order:
        document_id, title, _, _ = key
        steps = grouped[key]
        deduplicated: dict[int, StoredProcedureStep] = {}
        issues: list[str] = []
        for step in steps:
            if step.number in deduplicated:
                issues.append(f"step {step.number} appears more than once")
                reason = f"step {step.number} appears more than once in one candidate"
                if not any(
                    decision.decision == "rejected" and decision.reason == reason
                    for decision in grouping_decisions[key]
                ):
                    grouping_decisions[key].append(
                        ProcedureGroupingDecision(
                            decision="rejected",
                            reason=reason,
                            pages=sorted(
                                {
                                    deduplicated[step.number].citation.physical_page,
                                    step.citation.physical_page,
                                }
                            ),
                        )
                    )
            else:
                deduplicated[step.number] = step
        issues.extend(step_issues[key])
        ordered_steps = list(deduplicated.values())
        final_step = ordered_steps[-1].number
        note_events = _events_before_next_heading(
            parsed_pages,
            events=(event for parsed in parsed_pages for event in parsed.completeness_note_events),
            after_position=final_positions[key],
        )
        completeness_notes[key].extend(event.text for event in note_events)
        if not any(evidence.after_step == final_step for evidence in end_evidence[key]):
            end_marker_events = _events_before_next_heading(
                parsed_pages,
                events=(event for parsed in parsed_pages for event in parsed.end_marker_events),
                after_position=final_positions[key],
            )
            if end_marker_events:
                end_evidence[key].append(
                    ProcedureEndEvidence(
                        text=end_marker_events[0].text,
                        after_step=final_step,
                        strategy="explicit-marker",
                    )
                )
        if end_profile.strategy == "section-boundary" and not any(
            evidence.after_step == final_step for evidence in end_evidence[key]
        ):
            boundary = _next_section_boundary(
                parsed_pages,
                after_position=final_positions[key],
                procedure_level=section_levels[key],
            )
            if boundary is not None:
                end_evidence[key].append(
                    ProcedureEndEvidence(
                        text=boundary,
                        after_step=final_step,
                        strategy="section-boundary",
                    )
                )
        end = next(
            (evidence for evidence in end_evidence[key] if evidence.after_step == final_step),
            None,
        )
        first_page = min(page_numbers[key])
        procedure_id = f"{document_id}#{_slug(title)}-p{first_page}"
        notes = list(dict.fromkeys(completeness_notes[key]))
        procedures.append(
            StoredProcedure(
                procedure_id=procedure_id,
                document_id=document_id,
                title=title,
                heading_path=paths[key],
                start_boundary=" > ".join(paths[key]),
                end_boundary=end.text if end is not None else None,
                end_strategy=end.strategy if end is not None else end_profile.strategy,
                page_numbers=sorted(page_numbers[key]),
                steps=ordered_steps,
                end_evidence=end_evidence[key],
                completeness_notes=notes,
                validation_issues=issues,
                grouping_decisions=grouping_decisions[key],
            )
        )
    return procedures


def _next_section_boundary(
    parsed_pages: Sequence[_PageParse],
    *,
    after_position: tuple[int, int],
    procedure_level: int,
) -> str | None:
    events = sorted(
        (event for parsed in parsed_pages for event in parsed.heading_events),
        key=lambda event: (event.physical_page, event.line_index),
    )
    for event in events:
        if (event.physical_page, event.line_index) <= after_position:
            continue
        if event.level <= procedure_level:
            return " > ".join(event.heading_path)
        return None
    return None


def _events_before_next_heading(
    parsed_pages: Sequence[_PageParse],
    *,
    events: Iterable[_TextEvent],
    after_position: tuple[int, int],
) -> list[_TextEvent]:
    heading = next(
        (
            event
            for event in sorted(
                (event for parsed in parsed_pages for event in parsed.heading_events),
                key=lambda event: (event.physical_page, event.line_index),
            )
            if (event.physical_page, event.line_index) > after_position
        ),
        None,
    )
    heading_position = (heading.physical_page, heading.line_index) if heading is not None else None
    return [
        event
        for event in sorted(
            events,
            key=lambda event: (event.physical_page, event.line_index),
        )
        if (event.physical_page, event.line_index) > after_position
        and (heading_position is None or (event.physical_page, event.line_index) < heading_position)
    ]


def procedure_completeness_issues(procedure: StoredProcedure) -> list[str]:
    issues = list(procedure.validation_issues)
    numbers = [step.number for step in procedure.steps]
    if not numbers:
        return [*issues, "no numbered procedure steps were found"]
    if numbers != list(range(1, max(numbers) + 1)):
        missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
        if missing:
            issues.append(f"required step {missing[0]} may be missing")
        else:
            issues.append("procedure steps are not in source order")
    if any(not step.text.strip() for step in procedure.steps):
        issues.append("a procedure step has no supporting text")
    if any(not warning.text.strip() for step in procedure.steps for warning in step.warnings):
        issues.append("a procedure warning has no supporting text")
    for step in procedure.steps:
        if TRUNCATION_CUE.search(step.text):
            issues.append("the source marks the procedure as partial or truncated")
            break
    if (
        any(TRUNCATION_CUE.search(note) for note in procedure.completeness_notes)
        and "the source marks the procedure as partial or truncated" not in issues
    ):
        issues.append("the source marks the procedure as partial or truncated")
    if procedure.end_boundary is None:
        issues.append("the source-defined procedure end was not found")
    return issues


def _matches_question(title: str, question: str) -> bool:
    title_tokens = [token for token in tokens(title) if token not in PROCEDURE_STOPWORDS]
    if not title_tokens:
        return False
    return identity_matches(
        question,
        identifiers=[" ".join(title_tokens)],
        supporting=[title, PROCEDURE_QUERY_VOCAB],
    )


def _unique_citations(citations: Iterable[StoredCitation]) -> list[StoredCitation]:
    unique: list[StoredCitation] = []
    seen: set[tuple[str, int, str]] = set()
    for citation in citations:
        key = (citation.document_id, citation.physical_page, citation.section)
        if key not in seen:
            seen.add(key)
            unique.append(citation)
    return unique


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")


def _not_found(message: str, source_pack_id: str) -> CanonicalResponse:
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type="procedure",
        language="en",
        status="not_found",
        failure=Failure(code="not_found", message=message),
        source_pack_id=source_pack_id,
    )


def _clarification_required(*, source_pack_id: str) -> CanonicalResponse:
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type="procedure",
        language="en",
        status="clarification_required",
        clarification=Clarification(
            message="Please identify the exact task.",
            missing_information=["task"],
        ),
        source_pack_id=source_pack_id,
    )
