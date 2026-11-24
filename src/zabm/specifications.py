from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from collections.abc import Iterable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field
from pypdf import PdfReader

from zabm.conflicts import EvidenceCandidate, adjudicate, conflicting_evidence_response
from zabm.ingestion import IngestionProfileReference
from zabm.matching import identity_matches, tokens, unknown_tokens
from zabm.response import (
    CanonicalResponse,
    Claim,
    Clarification,
    Failure,
    PrecedenceDecision,
    SpecificationAnswer,
    SpecificationValue,
    StoredCitation,
)

DOWNLOAD_CHUNK_SIZE = 1024 * 1024
NUMBER_PATTERN = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")


class SourceRecord(BaseModel):
    id: str
    title: str
    manufacturer: str
    url: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieval_date: date
    revision: str | None = None
    ingestion_metadata: dict[str, str] = Field(default_factory=dict[str, str])
    ingestion_profile: IngestionProfileReference | None = None


class SourceManifest(BaseModel):
    manifest_version: str
    sources: list[SourceRecord]


class CitationTarget(BaseModel):
    printed_page: int
    physical_page: int
    section: str


class HumanVerification(BaseModel):
    status: str
    verified_by: str = ""
    verified_at: date | None = None


class PrecedenceRule(BaseModel):
    kind: Literal["model_scope", "supersession", "revision_date", "manufacturer_scope"]
    supersedes: list[str]
    reason: str
    source_id: str
    citation: CitationTarget
    evidence_excerpts: list[str]


class VerifiedSpecification(BaseModel):
    id: str
    manufacturer: str
    model: str
    component: str
    attribute: str
    aliases: list[str] = Field(default_factory=list)
    value: SpecificationValue
    conditions: list[str]
    source_id: str
    citation: CitationTarget
    evidence_excerpts: list[str]
    verification: HumanVerification
    precedence: PrecedenceRule | None = None


class VerifiedSpecificationFile(BaseModel):
    specifications: list[VerifiedSpecification]


class StoredSpecification(BaseModel):
    specification: VerifiedSpecification
    citation: StoredCitation
    precedence: PrecedenceDecision | None = None
    precedence_validation_issues: list[str] = Field(default_factory=list[str])
    validation_issues: list[str] = Field(default_factory=list)


class SpecificationCatalog(BaseModel):
    source_pack_id: str
    specifications: list[StoredSpecification]


class DownloadReport(BaseModel):
    source_pack_id: str
    source_count: int
    manufacturer_count: int
    sources: list[dict[str, str]]


class IngestReport(BaseModel):
    source_pack_id: str
    source_count: int
    manufacturer_count: int
    specification_count: int
    eligible_specification_count: int
    validation_issues: list[str]


class SourceIntegrityError(RuntimeError):
    pass


class IngestionError(RuntimeError):
    pass


def load_source_manifest(path: Path) -> SourceManifest:
    return SourceManifest.model_validate_json(path.read_text(encoding="utf-8"))


def verify_source_files(manifest_path: Path, pdf_dir: Path) -> None:
    verify_source_files_from_manifest(load_source_manifest(manifest_path), pdf_dir)


def verify_source_files_from_manifest(manifest: SourceManifest, pdf_dir: Path) -> None:
    for source in manifest.sources:
        source_path = pdf_dir / f"{source.id}.pdf"
        if not source_path.is_file():
            raise IngestionError(f"source {source.id} has not been downloaded")
        if file_sha256(source_path) != source.sha256:
            raise IngestionError(f"source {source.id} does not match the manifest hash")


def load_verified_specifications(path: Path) -> VerifiedSpecificationFile:
    return VerifiedSpecificationFile.model_validate_json(path.read_text(encoding="utf-8"))


def load_source_pages(manifest: SourceManifest, pdf_dir: Path) -> dict[str, list[str]]:
    verify_source_files_from_manifest(manifest, pdf_dir)
    page_texts: dict[str, list[str]] = {}
    for source in manifest.sources:
        source_path = pdf_dir / f"{source.id}.pdf"
        reader = PdfReader(source_path)
        page_texts[source.id] = [
            unicodedata.normalize("NFKC", page.extract_text() or "") for page in reader.pages
        ]
    return page_texts


def citation_issues(
    citation: CitationTarget,
    evidence_excerpts: Iterable[str],
    pages: list[str],
) -> list[str]:
    issues: list[str] = []
    physical_page = citation.physical_page
    if physical_page < 1 or physical_page > len(pages):
        issues.append(f"physical page {physical_page} is outside the document")
        return issues

    page_text = normalize_text(pages[physical_page - 1])
    if normalize_text(str(citation.printed_page)) not in page_text:
        issues.append("printed page number is not present on the cited physical page")
    if normalize_text(citation.section) not in page_text:
        issues.append("cited section is not present on the physical page")
    for excerpt in evidence_excerpts:
        if normalize_text(excerpt) not in page_text:
            issues.append("evidence excerpt is not present on the cited physical page")
    return issues


def download_sources(manifest_path: Path, pdf_dir: Path) -> DownloadReport:
    manifest = load_source_manifest(manifest_path)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, str]] = []

    for source in manifest.sources:
        destination = pdf_dir / f"{source.id}.pdf"
        temporary = destination.with_suffix(".pdf.part")
        request = Request(source.url, headers={"User-Agent": "zabm-source-downloader/0.1"})

        try:
            digest = hashlib.sha256()
            with urlopen(request, timeout=60) as response, temporary.open("wb") as output:
                while chunk := response.read(DOWNLOAD_CHUNK_SIZE):
                    output.write(chunk)
                    digest.update(chunk)

            actual_hash = digest.hexdigest()
            if actual_hash != source.sha256:
                raise SourceIntegrityError(
                    f"source {source.id} hash mismatch: expected {source.sha256}, got {actual_hash}"
                )
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

        reports.append(
            {
                "id": source.id,
                "title": source.title,
                "manufacturer": source.manufacturer,
                "url": source.url,
                "path": str(destination),
                "sha256": source.sha256,
                "retrieval_date": source.retrieval_date.isoformat(),
                "revision": source.revision or "not available",
            }
        )

    return DownloadReport(
        source_pack_id=manifest.manifest_version,
        source_count=len(manifest.sources),
        manufacturer_count=len({source.manufacturer for source in manifest.sources}),
        sources=reports,
    )


def ingest_sources(
    manifest_path: Path,
    evidence_path: Path,
    pdf_dir: Path,
    data_dir: Path,
) -> IngestReport:
    manifest = load_source_manifest(manifest_path)
    evidence = load_verified_specifications(evidence_path)
    sources = {source.id: source for source in manifest.sources}
    page_texts = load_source_pages(manifest, pdf_dir)

    stored: list[StoredSpecification] = []
    all_issues: list[str] = []
    for specification in evidence.specifications:
        source = sources.get(specification.source_id)
        issues: list[str] = []
        if source is None:
            issues.append(f"source {specification.source_id} is not in the manifest")
            pages: list[str] = []
        else:
            pages = page_texts[specification.source_id]
            issues.extend(
                citation_issues(
                    specification.citation,
                    specification.evidence_excerpts,
                    pages,
                )
            )

        issues.extend(_eligibility_issues(specification))
        stored_precedence, precedence_issues = store_precedence(
            specification.precedence,
            sources,
            page_texts,
            manifest.manifest_version,
        )
        citation = StoredCitation(
            document_id=specification.source_id,
            title=source.title if source else "unknown",
            manufacturer=source.manufacturer if source else specification.manufacturer,
            printed_page=specification.citation.printed_page,
            physical_page=specification.citation.physical_page,
            section=specification.citation.section,
            retrieval_date=source.retrieval_date if source else date.min,
            source_manifest_version=manifest.manifest_version,
        )
        stored.append(
            StoredSpecification(
                specification=specification,
                citation=citation,
                precedence=stored_precedence,
                precedence_validation_issues=precedence_issues,
                validation_issues=issues,
            )
        )
        all_issues.extend(f"{specification.id}: {issue}" for issue in issues)
        all_issues.extend(f"{specification.id} precedence: {issue}" for issue in precedence_issues)

    catalog = SpecificationCatalog(
        source_pack_id=manifest.manifest_version,
        specifications=stored,
    )
    generated_dir = data_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    write_json(generated_dir / "specifications.json", catalog.model_dump(mode="json"))

    return IngestReport(
        source_pack_id=manifest.manifest_version,
        source_count=len(manifest.sources),
        manufacturer_count=len({source.manufacturer for source in manifest.sources}),
        specification_count=len(stored),
        eligible_specification_count=sum(not item.validation_issues for item in stored),
        validation_issues=all_issues,
    )


def answer_specification(question: str, data_dir: Path) -> CanonicalResponse:
    catalog_path = data_dir / "generated" / "specifications.json"
    if not catalog_path.is_file():
        return _not_found(
            "Source data has not been ingested. Run `zabm download` and `zabm ingest` first.",
            source_pack_id="unknown",
        )

    catalog = SpecificationCatalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
    matches = [
        item for item in catalog.specifications if _matches_question(item.specification, question)
    ]
    if not matches:
        missing = [
            fields
            for item in catalog.specifications
            if (fields := _missing_identity_fields(item.specification, question))
        ]
        if missing:
            return _clarification_response(
                min(missing, key=len),
                source_pack_id=catalog.source_pack_id,
            )
        return _not_found(
            "No human-verified structured evidence matches this specification.",
            source_pack_id=catalog.source_pack_id,
        )
    if len(matches) > 1:
        groups: dict[
            tuple[str, str, str, str],
            list[StoredSpecification],
        ] = {}
        for item in matches:
            specification = item.specification
            key = (
                specification.manufacturer.casefold(),
                specification.model.casefold(),
                specification.component.casefold(),
                specification.attribute.casefold(),
            )
            groups.setdefault(key, []).append(item)
        if len(groups) > 1:
            return _clarification_required(
                [item.specification for item in matches],
                source_pack_id=catalog.source_pack_id,
            )
        matches = next(iter(groups.values()))

    for stored in matches:
        issues = stored.validation_issues + _eligibility_issues(stored.specification)
        if issues:
            return _not_found(
                f"Verified evidence was rejected: {issues[0]}",
                source_pack_id=catalog.source_pack_id,
            )

    candidates = [_evidence_candidate(item) for item in matches]
    adjudication = adjudicate(candidates)
    if adjudication.selected is None:
        assert adjudication.report is not None
        return conflicting_evidence_response(
            response_type="specification",
            report=adjudication.report,
            source_pack_id=catalog.source_pack_id,
        )

    selected_claim_id = adjudication.selected.claim_id
    stored = matches[0]
    for match in matches:
        if match.specification.id == selected_claim_id:
            stored = match
            break

    specification = stored.specification
    claim_text = _claim_text(specification)
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type="specification",
        language="en",
        status="supported",
        claims=[
            Claim(
                claim_id=specification.id,
                text=claim_text,
                evidence_ids=[specification.id],
            )
        ],
        specification=SpecificationAnswer(
            manufacturer=specification.manufacturer,
            model=specification.model,
            component=specification.component,
            attribute=specification.attribute,
            value=specification.value,
            conditions=specification.conditions,
        ),
        conflicts=adjudication.report,
        citations=[stored.citation],
        source_pack_id=catalog.source_pack_id,
    )


def _evidence_candidate(stored: StoredSpecification) -> EvidenceCandidate:
    specification = stored.specification
    return EvidenceCandidate(
        claim_id=specification.id,
        claim=_claim_text(specification),
        evidence_ids=(specification.id,),
        excerpts=tuple(specification.evidence_excerpts),
        citations=(stored.citation,),
        answer_key=(
            specification.value.minimum,
            specification.value.maximum,
            specification.value.unit,
            specification.value.display,
            *specification.conditions,
        ),
        precedence=stored.precedence,
    )


def _claim_text(specification: VerifiedSpecification) -> str:
    return (
        f"{specification.manufacturer} {specification.model} "
        f"{specification.component} {specification.attribute}: "
        f"{specification.value.display}."
    )


def store_precedence(
    precedence: PrecedenceRule | None,
    sources: dict[str, SourceRecord],
    page_texts: dict[str, list[str]],
    manifest_version: str,
) -> tuple[PrecedenceDecision | None, list[str]]:
    if precedence is None:
        return None, []

    issues: list[str] = []
    if not precedence.supersedes:
        issues.append("precedence does not identify superseded evidence")
    if not precedence.reason.strip():
        issues.append("precedence reason is missing")
    if not precedence.evidence_excerpts:
        issues.append("precedence evidence excerpt is missing")

    source = sources.get(precedence.source_id)
    if source is None:
        issues.append(f"precedence source {precedence.source_id} is not in the manifest")
    else:
        issues.extend(
            citation_issues(
                precedence.citation,
                precedence.evidence_excerpts,
                page_texts[precedence.source_id],
            )
        )
        cue_issue = _precedence_cue_issue(precedence, source)
        if cue_issue is not None:
            issues.append(cue_issue)
    if issues:
        return None, issues
    citation = StoredCitation(
        document_id=precedence.source_id,
        title=source.title if source else "unknown",
        manufacturer=source.manufacturer if source else "unknown",
        printed_page=precedence.citation.printed_page,
        physical_page=precedence.citation.physical_page,
        section=precedence.citation.section,
        retrieval_date=source.retrieval_date if source else date.min,
        source_manifest_version=manifest_version,
    )
    return (
        PrecedenceDecision(
            kind=precedence.kind,
            reason=precedence.reason,
            supersedes=precedence.supersedes,
            excerpt=" ".join(precedence.evidence_excerpts),
            citation=citation,
        ),
        [],
    )


def _precedence_cue_issue(
    precedence: PrecedenceRule,
    source: SourceRecord,
) -> str | None:
    evidence = normalize_text(" ".join(precedence.evidence_excerpts))
    if precedence.kind == "supersession":
        if not any(cue in evidence for cue in ("supersed", "replace", "obsolete")):
            return "precedence excerpt does not establish supersession"
    elif precedence.kind == "revision_date":
        if not any(cue in evidence for cue in ("revision", "revised", "effective")):
            return "precedence excerpt does not establish a revision date"
    elif precedence.kind == "model_scope":
        if not any(
            cue in evidence
            for cue in ("applies to", "applies only", "only for", "specific to", "model scope")
        ):
            return "precedence excerpt does not establish model scope"
    elif normalize_text(source.manufacturer) not in evidence:
        return "precedence excerpt does not establish manufacturer scope"
    return None


def _not_found(message: str, source_pack_id: str) -> CanonicalResponse:
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type="specification",
        language="en",
        status="not_found",
        failure=Failure(code="not_found", message=message),
        source_pack_id=source_pack_id,
    )


def _clarification_required(
    specifications: list[VerifiedSpecification],
    *,
    source_pack_id: str,
) -> CanonicalResponse:
    missing: list[str] = []
    if len({item.model for item in specifications}) > 1:
        missing.append("model")
    if len({item.component for item in specifications}) > 1:
        missing.append("component")
    if len({item.attribute for item in specifications}) > 1:
        missing.append("attribute")
    sides = {
        next(
            (
                condition.split(":", maxsplit=1)[1].strip().casefold()
                for condition in item.conditions
                if condition.casefold().startswith("side:")
            ),
            "",
        )
        for item in specifications
    }
    if len(sides) > 1:
        missing.append("side")
    if not missing:
        missing.append("component")
    return _clarification_response(missing, source_pack_id=source_pack_id)


def _missing_identity_fields(
    specification: VerifiedSpecification,
    question: str,
) -> list[str]:
    supporting = [
        specification.manufacturer,
        specification.value.unit,
        specification.value.display,
        *specification.conditions,
    ]
    unknown = unknown_tokens(
        question,
        identifiers=[
            specification.model,
            specification.component,
            specification.attribute,
        ],
        aliases=specification.aliases,
        supporting=supporting,
    )
    if unknown:
        return []

    question_tokens = set(tokens(question))
    alias_tokens = [set(tokens(alias)) for alias in specification.aliases if alias.strip()]
    alias_matched = any(tokens_for_alias <= question_tokens for tokens_for_alias in alias_tokens)
    missing: list[str] = []
    if not alias_matched and not set(tokens(specification.model)) <= question_tokens:
        missing.append("model")
    if not alias_matched and not set(tokens(specification.component)) <= question_tokens:
        missing.append("component")
    if not alias_matched and not set(tokens(specification.attribute)) <= question_tokens:
        missing.append("attribute")
    return missing


def _clarification_response(
    missing: list[str],
    *,
    source_pack_id: str,
) -> CanonicalResponse:
    message = f"Please identify the exact {' and '.join(missing)}."
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type="specification",
        language="en",
        status="clarification_required",
        clarification=Clarification(
            message=message,
            missing_information=missing,
        ),
        source_pack_id=source_pack_id,
    )


def _eligibility_issues(specification: VerifiedSpecification) -> list[str]:
    issues: list[str] = []
    verification = specification.verification
    if verification.status != "human_verified":
        issues.append("human verification is missing")
    if not verification.verified_by.strip():
        issues.append("human verifier is missing")
    if verification.verified_at is None:
        issues.append("human verification date is missing")
    if not specification.conditions:
        issues.append("source-defined applicability conditions are missing")
    if not specification.value.unit.strip():
        issues.append("specification unit is missing")
    elif not _unit_matches(
        specification.value.unit,
        specification.evidence_excerpts,
    ):
        issues.append("specification unit does not match the claim evidence excerpt")
    if not specification.evidence_excerpts:
        issues.append("claim evidence excerpt is missing")
    if not _numbers_match(
        specification.value.display,
        specification.evidence_excerpts,
        [
            specification.value.minimum,
            *([specification.value.maximum] if specification.value.maximum is not None else []),
        ],
    ):
        issues.append("a numeric value does not match the claim evidence excerpt")
    if (
        specification.value.maximum is not None
        and specification.value.minimum > specification.value.maximum
    ):
        issues.append("specification range is reversed")
    return issues


def _numbers_match(
    claim_text: str,
    evidence_excerpts: Iterable[str],
    claim_values: Iterable[float],
) -> bool:
    claim_numbers = {
        float(number) for number in NUMBER_PATTERN.findall(_normalize_unit_spelling(claim_text))
    }
    claim_numbers.update(float(value) for value in claim_values)
    evidence_numbers = {
        float(number)
        for number in NUMBER_PATTERN.findall(_normalize_unit_spelling(" ".join(evidence_excerpts)))
    }
    return bool(claim_numbers) and all(number in evidence_numbers for number in claim_numbers)


def _unit_matches(unit: str, evidence_excerpts: Iterable[str]) -> bool:
    evidence_text = _normalize_unit_spelling(" ".join(evidence_excerpts)).casefold()
    return _normalize_unit_spelling(unit).strip().casefold() in evidence_text


def _normalize_unit_spelling(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.sub(r"\bN\s*[*·•⋅]\s*m\b", " N·m ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bN\s*m\b", " N·m ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bin\s*[-·•⋅/]\s*lb\b", " in-lb ", normalized, flags=re.IGNORECASE)
    return normalized


def normalize_text(text: str) -> str:
    normalized = _normalize_unit_spelling(text).casefold()
    return " ".join(normalized.split())


def _matches_question(specification: VerifiedSpecification, question: str) -> bool:
    return identity_matches(
        question,
        identifiers=[
            specification.model,
            specification.component,
            specification.attribute,
        ],
        aliases=specification.aliases,
        supporting=[
            specification.manufacturer,
            specification.value.unit,
            specification.value.display,
            *specification.conditions,
        ],
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(DOWNLOAD_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(f"{path.suffix}.part")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
