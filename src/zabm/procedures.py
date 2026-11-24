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
    HeadingNode,
    IngestionProfileProvenance,
    IngestionProfilesFile,
    IngestionProvenance,
    LayoutSpan,
    LayoutStageResult,
    NormalizedBox,
    PageBox,
    PageKind,
    PdfPageObservation,
    SelectedProfileProvenance,
    load_ingestion_profiles,
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
    CitationTarget,
    citation_issues,
    file_sha256,
    load_source_manifest,
    write_json,
)

logger = logging.getLogger("zabm.rag")

WARNING_HEADINGS: dict[str, Literal["warning", "notice"]] = {
    "NOTICE": "notice",
    "WARNING": "warning",
}
STEP_NUMBER = re.compile(r"^\d{1,2}$")
INLINE_STEP = re.compile(r"^(\d{1,2})\s+(.+)$")
SERVICE_HEADING = re.compile(r"^(?:\d+/)?\d+ Hour Service\s+(.+)$", re.IGNORECASE)
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
    reading_order: list[str] = Field(default_factory=list[str])
    languages: list[str] = Field(default_factory=list[str])
    page_kind: PageKind = "unknown"
    classification_confidence: float = 0.0
    classification_uncertain: bool = True
    classification_uncertainty: str | None = None
    text: str
    blocks: list[EvidenceBlock]


class RetrievalSource(BaseModel):
    document_id: str
    title: str
    manufacturer: str
    ingestion_profile: IngestionProfileProvenance
    pages: list[RetrievalPage]


class ProcedureEndEvidence(BaseModel):
    text: str
    after_step: int


class StoredProcedure(BaseModel):
    procedure_id: str
    document_id: str
    title: str
    heading_path: list[str]
    page_numbers: list[int]
    steps: list[ProcedureStep]
    end_evidence: list[ProcedureEndEvidence] = Field(default_factory=list[ProcedureEndEvidence])
    validation_issues: list[str] = Field(default_factory=list[str])


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


class RetrievalIngestReport(BaseModel):
    source_pack_id: str
    ingestion_provenance: IngestionProvenance
    page_count: int
    page_alignment: PageAlignmentReport
    table_row_count: int
    warning_count: int
    procedure_count: int
    eligible_procedure_count: int
    validation_issues: list[str]


class ProcedureEvidenceMatch(BaseModel):
    procedure_id: str
    title: str
    heading_path: list[str]
    complete: bool
    validation_issues: list[str]
    pages: list[RetrievalPage]
    steps: list[ProcedureStep]


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


@dataclass
class _StepStart:
    number: int
    number_line_index: int
    line_index: int
    text: str


@dataclass
class _ParsedStep:
    step: ProcedureStep
    section_sequence: int
    section_title: str
    heading_path: list[str]


@dataclass
class _PageParse:
    page: RetrievalPage
    steps: list[_ParsedStep]
    step_issues: dict[int, list[str]]
    end_evidence: dict[int, list[ProcedureEndEvidence]]
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
    requested_language: str | None = None,
) -> RetrievalIngestReport:
    manifest = load_source_manifest(manifest_path)
    if ingestion_profiles is not None and ingestion_profiles_path is None:
        raise ValueError("preloaded ingestion profiles require their source manifest path")
    profile_path = ingestion_profiles_path or DEFAULT_INGESTION_PROFILES
    profiles = ingestion_profiles or load_ingestion_profiles(profile_path)
    sources: list[RetrievalSource] = []
    procedures: list[StoredProcedure] = []
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
        sources.append(
            RetrievalSource(
                document_id=source.id,
                title=source.title,
                manufacturer=source.manufacturer,
                ingestion_profile=profile_provenance,
                pages=[parsed.page for parsed in parsed_pages],
            )
        )
        for procedure in _group_procedures(parsed_pages):
            procedures.append(procedure)
            validation_issues.extend(
                f"{procedure.procedure_id}: {issue}" for issue in procedure.validation_issues
            )

    ingestion_provenance = IngestionProvenance(
        parser_version=PARSER_VERSION,
        fonttools_version=FONTTOOLS_VERSION,
        pypdf_version=PYPDF_VERSION,
        profile_schema_version=profiles.profile_schema_version,
        profile_manifest_version=profiles.profile_manifest_version,
        profile_manifest_sha256=file_sha256(profile_path),
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

    procedure = matches[0]
    issues = procedure.validation_issues + procedure_completeness_issues(procedure)
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
            steps=procedure.steps,
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
        issues = procedure.validation_issues + procedure_completeness_issues(procedure)
        matches.append(
            ProcedureEvidenceMatch(
                procedure_id=procedure.procedure_id,
                title=procedure.title,
                heading_path=procedure.heading_path,
                complete=not issues,
                validation_issues=issues,
                pages=[
                    pages_by_source[procedure.document_id][page_number]
                    for page_number in procedure.page_numbers
                ],
                steps=procedure.steps,
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
    current_title: str = section_title
    current_path: list[str] = heading_path
    section_sequence = 0
    section_paths = {section_sequence: list(current_path)}
    current_step: ProcedureStep | None = None
    pending_warnings: list[ProcedureWarning] = []

    allowed_step_lines: set[int] = (
        {
            index
            for index, block in enumerate(content_classifications)
            if block.kind == "procedure-step"
        }
        if extraction_allowed
        else set()
    )
    step_starts = _step_starts(content_lines, allowed=allowed_step_lines)
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
            heading_count += 1
            current_title = heading.title
            current_path = next_path
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
        if _matches_procedure_end(line_text, profile.end_boundaries.markers):
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
            warning_text, index = _collect_warning(
                content_lines,
                index,
                column_id=line.column_id,
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
            warning = ProcedureWarning(severity=warning_severity, text=warning_text)
            if current_step is None:
                pending_warnings.append(warning)
            else:
                current_step.warnings.append(warning)
            continue

        step = start_by_index.get(index)
        if step is not None:
            step_column_id = content_lines[step.line_index].column_id
            body_lines: list[str] = [step.text]
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
                ):
                    break
                candidate_text = candidate.text
                if _matches_procedure_end(candidate_text, profile.end_boundaries.markers):
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
            issues = citation_issues(
                CitationTarget(
                    printed_page=printed_page,
                    physical_page=physical_page,
                    section=current_title,
                ),
                [text, *(warning.text for warning in pending_warnings)],
                [""] * (physical_page - 1) + [normalize_pdf_text(raw_text)],
            )
            procedure_step = ProcedureStep(
                number=step.number,
                text=text,
                warnings=list(pending_warnings),
                citation=citation,
            )
            pending_warnings.clear()
            steps.append(
                _ParsedStep(
                    step=procedure_step,
                    section_sequence=section_sequence,
                    section_title=current_title,
                    heading_path=list(current_path),
                )
            )
            current_step = procedure_step
            step_issues.setdefault(section_sequence, []).extend(
                f"step {step.number}: {issue}" for issue in issues
            )
            blocks.append(
                _classified_evidence(
                    EvidenceBlock(kind="step", text=text, heading_path=list(current_path)),
                    content_classifications[step.number_line_index],
                )
            )
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
        classification_confidence=classification.confidence,
        classification_uncertain=classification.uncertain,
        classification_uncertainty=classification.rejection_reason,
        text=raw_text,
        blocks=blocks,
    )
    return _PageParse(
        page=page_model,
        steps=steps,
        step_issues=step_issues,
        end_evidence=end_evidence,
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


def _step_starts(lines: list[_Line], *, allowed: set[int] | None = None) -> list[_StepStart]:
    starts: list[_StepStart] = []
    linked_content: set[int] = set()
    for index, line in enumerate(lines):
        if allowed is not None and index not in allowed:
            continue
        inline = INLINE_STEP.match(line.text)
        if inline is not None:
            starts.append(
                _StepStart(
                    int(inline.group(1)),
                    index,
                    index,
                    inline.group(2).strip(),
                )
            )
            continue
        if not STEP_NUMBER.fullmatch(line.text) or line.x > 70:
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
            starts.append(
                _StepStart(
                    int(line.text),
                    index,
                    content_index,
                    lines[content_index].text,
                )
            )
    return sorted(starts, key=lambda start: start.line_index)


def _collect_warning(
    lines: list[_Line],
    heading_index: int,
    *,
    column_id: str,
) -> tuple[str, int]:
    heading = lines[heading_index].text
    severity = _warning_severity(heading)
    assert severity is not None
    body: list[str] = []
    last_y = lines[heading_index].y
    index = heading_index + 1
    while index < len(lines):
        line = lines[index]
        if line.column_id != column_id:
            break
        text = line.text
        if not text or STEP_NUMBER.fullmatch(text) or INLINE_STEP.match(text):
            break
        if "This concludes" in text or "Proceed to" in text:
            break
        if last_y - line.y > 25:
            break
        body.append(text)
        last_y = line.y
        index += 1
    return normalize_pdf_text("\n".join(body)), index


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


def _group_procedures(parsed_pages: list[_PageParse]) -> list[StoredProcedure]:
    grouped: dict[tuple[str, str, int], list[ProcedureStep]] = {}
    paths: dict[tuple[str, str, int], list[str]] = {}
    page_numbers: dict[tuple[str, str, int], list[int]] = {}
    step_issues: dict[tuple[str, str, int], list[str]] = {}
    end_evidence: dict[tuple[str, str, int], list[ProcedureEndEvidence]] = {}
    order: list[tuple[str, str, int]] = []
    active_key: tuple[str, str, int] | None = None
    active_title: str | None = None
    previous_page: int | None = None
    section_run = 0

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
            continues = (
                position == 0
                and active_title == title
                and previous_page is not None
                and parsed.page.physical_page == previous_page + 1
                and active_key is not None
            )
            if continues:
                key = active_key
                assert key is not None
            else:
                key = (parsed.document_id, title, section_run)
                section_run += 1
                grouped[key] = []
                paths[key] = section_steps[0].heading_path
                page_numbers[key] = []
                step_issues[key] = []
                end_evidence[key] = []
                order.append(key)

            grouped[key].extend(parsed_step.step for parsed_step in section_steps)
            if parsed.page.physical_page not in page_numbers[key]:
                page_numbers[key].append(parsed.page.physical_page)
            step_issues[key].extend(parsed.step_issues.get(sequence, []))
            end_evidence[key].extend(parsed.end_evidence.get(sequence, []))
            active_key = key
            active_title = title
            previous_page = parsed.page.physical_page

    procedures: list[StoredProcedure] = []
    for key in order:
        document_id, title, _ = key
        steps = grouped[key]
        deduplicated: dict[int, ProcedureStep] = {}
        issues: list[str] = []
        for step in steps:
            if step.number in deduplicated:
                issues.append(f"step {step.number} appears more than once")
            else:
                deduplicated[step.number] = step
        issues.extend(step_issues[key])
        ordered_steps = [deduplicated[number] for number in sorted(deduplicated)]
        first_page = min(page_numbers[key])
        procedure_id = f"{document_id}#{_slug(title)}-p{first_page}"
        procedures.append(
            StoredProcedure(
                procedure_id=procedure_id,
                document_id=document_id,
                title=title,
                heading_path=paths[key],
                page_numbers=sorted(page_numbers[key]),
                steps=ordered_steps,
                end_evidence=end_evidence[key],
                validation_issues=issues,
            )
        )
    return procedures


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
    final_step = max(numbers)
    if not any(end.after_step == final_step for end in procedure.end_evidence):
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
