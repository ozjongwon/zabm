from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from zabm.matching import tokens
from zabm.procedures import RetrievalCatalog
from zabm.specifications import (
    SourceManifest,
    file_sha256,
    load_source_manifest,
    write_json,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EvidenceType = Literal["specification", "compatibility", "procedure"]
RetrievalPathKind = Literal["bm25", "token-overlap"]


class FrozenSourcePackError(RuntimeError):
    pass


class ExpectedEvidence(BaseModel):
    source_id: str
    physical_pages: list[int] = Field(min_length=1)
    section: str | None = None


class RetrievalSmokeItem(BaseModel):
    id: str
    evidence_type: EvidenceType
    query: str
    expected_evidence: list[ExpectedEvidence] = Field(min_length=1)


class RetrievalSmokeSet(BaseModel):
    smoke_set_id: str
    items: list[RetrievalSmokeItem] = Field(min_length=1)


class RetrievalPath(BaseModel):
    id: str
    kind: RetrievalPathKind
    k1: float = 1.2
    b: float = 0.75
    title_boost: float = 2.0
    section_boost: float = 2.0


class RetrievalConfiguration(BaseModel):
    configuration_id: str
    top_k: int = 5
    required_recall_at_5: float = 0.85
    minimum_passing_paths: int = 1
    paths: list[RetrievalPath] = Field(min_length=1)


class RetrievedEvidence(BaseModel):
    source_id: str
    physical_page: int
    section: str
    score: float


class SmokeItemResult(BaseModel):
    path_id: str
    item_id: str
    evidence_type: EvidenceType
    query: str
    expected_evidence: list[ExpectedEvidence]
    retrieved_evidence: list[RetrievedEvidence]
    hit: bool


class PathResult(BaseModel):
    path_id: str
    hit_count: int
    item_count: int
    recall_at_5: float
    passed: bool
    items: list[SmokeItemResult]


class ThresholdDecision(BaseModel):
    required_recall_at_5: float
    minimum_passing_paths: int
    passing_paths: list[str]
    passed: bool


class RetrievalSmokeReport(BaseModel):
    evaluation_mode: Literal["retrieval-only"] = "retrieval-only"
    source_pack_id: str
    source_pack_manifest_sha256: str
    smoke_set_id: str
    smoke_set_sha256: str
    retrieval_configuration_id: str
    retrieval_config_sha256: str
    top_k: int
    item_results: list[SmokeItemResult]
    path_results: list[PathResult]
    threshold_decision: ThresholdDecision


class SourceUpdatePolicy(BaseModel):
    requires_explicit_manifest_change: bool = True
    requires_maintainer_review: bool = True
    requires_complete_evaluation_rerun: bool = True


class SourceFreeze(BaseModel):
    freeze_version: str
    frozen_at: date
    manifest_version: str
    manifest_path: str
    source_pack_manifest_sha256: str
    source_hashes: dict[str, str]
    smoke_set_path: str
    smoke_set_sha256: str
    retrieval_config_path: str
    retrieval_config_sha256: str
    retrieval_smoke_report_path: str
    retrieval_smoke_report_sha256: str
    threshold_decision: ThresholdDecision
    maintainer_review: str
    update_policy: SourceUpdatePolicy
    candidate_audit_path: str | None = None
    candidate_audit_sha256: str | None = None


class _CandidateAuditDecision(BaseModel):
    included: bool


class _CandidateAuditRecord(BaseModel):
    source_id: str
    decision: _CandidateAuditDecision


class _SourceCandidateAudit(BaseModel):
    candidates: list[_CandidateAuditRecord]


@dataclass(frozen=True)
class _RetrievalUnit:
    source_id: str
    title: str
    section: str
    physical_page: int
    text: str


def run_retrieval_smoke(
    manifest_path: Path,
    smoke_set_path: Path,
    retrieval_config_path: Path,
    data_dir: Path,
) -> RetrievalSmokeReport:
    manifest = load_source_manifest(manifest_path)
    smoke_set = RetrievalSmokeSet.model_validate_json(smoke_set_path.read_text(encoding="utf-8"))
    configuration = RetrievalConfiguration.model_validate_json(
        retrieval_config_path.read_text(encoding="utf-8")
    )
    if configuration.top_k != 5:
        raise ValueError("the frozen retrieval smoke configuration must use top_k 5")
    if configuration.required_recall_at_5 < 0.85:
        raise ValueError("the frozen Recall@5 threshold cannot be below 0.85")
    if configuration.minimum_passing_paths < 1:
        raise ValueError("the frozen retrieval configuration must require a passing path")
    evidence_types = {item.evidence_type for item in smoke_set.items}
    if evidence_types != {"specification", "compatibility", "procedure"}:
        raise ValueError(
            "the fixed retrieval smoke set must cover specification, compatibility, "
            "and procedure evidence"
        )
    item_ids = [item.id for item in smoke_set.items]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("retrieval smoke item IDs must be unique")
    path_ids = [path.id for path in configuration.paths]
    if len(path_ids) != len(set(path_ids)):
        raise ValueError("retrieval path IDs must be unique")

    catalog_path = data_dir / "generated" / "retrieval.json"
    if not catalog_path.is_file():
        raise ValueError("retrieval evidence has not been ingested")
    catalog = RetrievalCatalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
    if catalog.source_pack_id != manifest.manifest_version:
        raise ValueError(
            "retrieval evidence source-pack ID does not match the source manifest; "
            "run `zabm ingest` again"
        )
    catalog_source_ids = {source.document_id for source in catalog.sources}
    for item in smoke_set.items:
        missing_sources = {
            expected.source_id
            for expected in item.expected_evidence
            if expected.source_id not in catalog_source_ids
        }
        if missing_sources:
            names = ", ".join(sorted(missing_sources))
            raise ValueError(f"retrieval smoke item {item.id} references unknown sources: {names}")

    units = _retrieval_units(catalog)
    path_results: list[PathResult] = []
    all_item_results: list[SmokeItemResult] = []
    for path in configuration.paths:
        item_results: list[SmokeItemResult] = []
        for item in smoke_set.items:
            retrieved = _retrieve(item.query, units, path, configuration.top_k)
            hit = any(
                expected.source_id == evidence.source_id
                and evidence.physical_page in expected.physical_pages
                for expected in item.expected_evidence
                for evidence in retrieved
            )
            item_results.append(
                SmokeItemResult(
                    path_id=path.id,
                    item_id=item.id,
                    evidence_type=item.evidence_type,
                    query=item.query,
                    expected_evidence=item.expected_evidence,
                    retrieved_evidence=retrieved,
                    hit=hit,
                )
            )
        hit_count = sum(result.hit for result in item_results)
        recall_at_5 = hit_count / len(item_results)
        path_results.append(
            PathResult(
                path_id=path.id,
                hit_count=hit_count,
                item_count=len(item_results),
                recall_at_5=recall_at_5,
                passed=recall_at_5 >= configuration.required_recall_at_5,
                items=item_results,
            )
        )
        all_item_results.extend(item_results)

    passing_paths = [result.path_id for result in path_results if result.passed]
    threshold_decision = ThresholdDecision(
        required_recall_at_5=configuration.required_recall_at_5,
        minimum_passing_paths=configuration.minimum_passing_paths,
        passing_paths=passing_paths,
        passed=len(passing_paths) >= configuration.minimum_passing_paths,
    )
    return RetrievalSmokeReport(
        source_pack_id=manifest.manifest_version,
        source_pack_manifest_sha256=file_sha256(manifest_path),
        smoke_set_id=smoke_set.smoke_set_id,
        smoke_set_sha256=file_sha256(smoke_set_path),
        retrieval_configuration_id=configuration.configuration_id,
        retrieval_config_sha256=file_sha256(retrieval_config_path),
        top_k=configuration.top_k,
        item_results=all_item_results,
        path_results=path_results,
        threshold_decision=threshold_decision,
    )


def write_retrieval_smoke_report(report: RetrievalSmokeReport, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(report_path, report.model_dump(mode="json"))


def load_source_freeze(path: Path) -> SourceFreeze:
    return SourceFreeze.model_validate_json(path.read_text(encoding="utf-8"))


def verify_source_freeze(
    freeze_path: Path,
    manifest_path: Path,
    smoke_set_path: Path,
    retrieval_config_path: Path,
    report_path: Path,
) -> SourceFreeze:
    freeze = load_source_freeze(freeze_path)
    manifest = load_source_manifest(manifest_path)
    current_hashes = {
        "manifest": file_sha256(manifest_path),
        "smoke set": file_sha256(smoke_set_path),
        "retrieval configuration": file_sha256(retrieval_config_path),
        "retrieval smoke report": file_sha256(report_path),
    }
    frozen_hashes = {
        "manifest": freeze.source_pack_manifest_sha256,
        "smoke set": freeze.smoke_set_sha256,
        "retrieval configuration": freeze.retrieval_config_sha256,
        "retrieval smoke report": freeze.retrieval_smoke_report_sha256,
    }
    for label, current_hash in current_hashes.items():
        if current_hash != frozen_hashes[label]:
            raise FrozenSourcePackError(
                f"{label} differs from the frozen source pack; source updates require an "
                "explicit manifest change, maintainer review, and complete evaluation rerun"
            )

    if freeze.candidate_audit_path is not None:
        if freeze.candidate_audit_sha256 is None:
            raise FrozenSourcePackError("frozen source pack has no candidate-audit checksum")
        candidate_audit_path = _resolve_stored_path(freeze.candidate_audit_path)
        if file_sha256(candidate_audit_path) != freeze.candidate_audit_sha256:
            raise FrozenSourcePackError(
                "candidate audit differs from the frozen source pack; source updates require "
                "an explicit manifest change, maintainer review, and complete evaluation rerun"
            )

    if not freeze.threshold_decision.passed or not freeze.threshold_decision.passing_paths:
        raise FrozenSourcePackError("the frozen source pack does not contain a passing path")
    current_sources = {source.id: source.sha256 for source in manifest.sources}
    if current_sources != freeze.source_hashes:
        raise FrozenSourcePackError(
            "source content differs from the frozen source pack; source updates require an "
            "explicit manifest change, maintainer review, and complete evaluation rerun"
        )
    return freeze


def verify_frozen_source_pack(freeze_path: Path, manifest_path: Path) -> SourceFreeze:
    freeze = load_source_freeze(freeze_path)
    return verify_source_freeze(
        freeze_path,
        manifest_path,
        _resolve_stored_path(freeze.smoke_set_path),
        _resolve_stored_path(freeze.retrieval_config_path),
        _resolve_stored_path(freeze.retrieval_smoke_report_path),
    )


def freeze_source_pack(
    manifest_path: Path,
    smoke_set_path: Path,
    retrieval_config_path: Path,
    report_path: Path,
    freeze_path: Path,
    *,
    maintainer_review: str,
    candidate_audit_path: Path | None = None,
) -> SourceFreeze:
    manifest = load_source_manifest(manifest_path)
    smoke_set = RetrievalSmokeSet.model_validate_json(smoke_set_path.read_text(encoding="utf-8"))
    configuration = RetrievalConfiguration.model_validate_json(
        retrieval_config_path.read_text(encoding="utf-8")
    )
    report = RetrievalSmokeReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    expected_hashes = {
        "manifest": file_sha256(manifest_path),
        "smoke_set": file_sha256(smoke_set_path),
        "retrieval_config": file_sha256(retrieval_config_path),
    }
    reported_hashes = {
        "manifest": report.source_pack_manifest_sha256,
        "smoke_set": report.smoke_set_sha256,
        "retrieval_config": report.retrieval_config_sha256,
    }
    if expected_hashes != reported_hashes:
        raise ValueError("retrieval smoke report does not match the frozen inputs")
    if report.source_pack_id != manifest.manifest_version:
        raise ValueError("retrieval smoke report source-pack ID does not match the manifest")
    if report.smoke_set_id != smoke_set.smoke_set_id:
        raise ValueError("retrieval smoke report smoke-set ID does not match the smoke set")
    if report.retrieval_configuration_id != configuration.configuration_id:
        raise ValueError(
            "retrieval smoke report configuration ID does not match the retrieval configuration"
        )
    if (
        report.threshold_decision.required_recall_at_5 != configuration.required_recall_at_5
        or report.threshold_decision.minimum_passing_paths != configuration.minimum_passing_paths
    ):
        raise ValueError("retrieval smoke report threshold does not match the configuration")
    if not report.threshold_decision.passed:
        raise ValueError(
            "retrieval smoke threshold was not met; refusing to freeze the source pack"
        )
    if not maintainer_review.strip():
        raise ValueError("a maintainer review reference is required to freeze the source pack")
    candidate_audit_sha256: str | None = None
    if candidate_audit_path is not None:
        _validate_candidate_audit(candidate_audit_path, manifest)
        candidate_audit_sha256 = file_sha256(candidate_audit_path)

    freeze = SourceFreeze(
        freeze_version=f"frozen-{manifest.manifest_version}",
        frozen_at=date.today(),
        manifest_version=manifest.manifest_version,
        manifest_path=_stored_path(manifest_path),
        source_pack_manifest_sha256=expected_hashes["manifest"],
        source_hashes={source.id: source.sha256 for source in manifest.sources},
        smoke_set_path=_stored_path(smoke_set_path),
        smoke_set_sha256=expected_hashes["smoke_set"],
        retrieval_config_path=_stored_path(retrieval_config_path),
        retrieval_config_sha256=expected_hashes["retrieval_config"],
        retrieval_smoke_report_path=_stored_path(report_path),
        retrieval_smoke_report_sha256=file_sha256(report_path),
        threshold_decision=report.threshold_decision,
        maintainer_review=maintainer_review,
        update_policy=SourceUpdatePolicy(),
        candidate_audit_path=(
            _stored_path(candidate_audit_path) if candidate_audit_path is not None else None
        ),
        candidate_audit_sha256=candidate_audit_sha256,
    )
    freeze_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(freeze_path, freeze.model_dump(mode="json"))
    return freeze


def _retrieval_units(catalog: RetrievalCatalog) -> list[_RetrievalUnit]:
    return [
        _RetrievalUnit(
            source_id=source.document_id,
            title=source.title,
            section=page.section,
            physical_page=page.physical_page,
            text=page.text,
        )
        for source in catalog.sources
        for page in source.pages
    ]


def _retrieve(
    query: str,
    units: list[_RetrievalUnit],
    path: RetrievalPath,
    top_k: int,
) -> list[RetrievedEvidence]:
    if path.kind == "bm25":
        scores = _bm25_scores(query, units, path)
    else:
        scores = _token_overlap_scores(query, units, path)
    ranked = sorted(
        zip(units, scores, strict=True),
        key=lambda item: (-item[1], item[0].source_id, item[0].physical_page),
    )[:top_k]
    return [
        RetrievedEvidence(
            source_id=unit.source_id,
            physical_page=unit.physical_page,
            section=unit.section,
            score=round(score, 6),
        )
        for unit, score in ranked
    ]


def _weighted_tokens(
    unit: _RetrievalUnit,
    *,
    title_boost: float,
    section_boost: float,
) -> list[str]:
    return [
        *tokens(unit.text),
        *(tokens(unit.section) * max(1, round(section_boost))),
        *(tokens(unit.title) * max(1, round(title_boost))),
    ]


def _bm25_scores(
    query: str,
    units: list[_RetrievalUnit],
    path: RetrievalPath,
) -> list[float]:
    tokenized = [
        _weighted_tokens(
            unit,
            title_boost=path.title_boost,
            section_boost=path.section_boost,
        )
        for unit in units
    ]
    frequencies = [Counter(document) for document in tokenized]
    average_length = sum(len(document) for document in tokenized) / len(tokenized)
    query_terms = sorted(set(tokens(query)))
    document_count = len(units)
    matching_document_counts = {
        term: sum(term in candidate for candidate in frequencies) for term in query_terms
    }
    scores: list[float] = []
    for document, frequency in zip(tokenized, frequencies, strict=True):
        score = 0.0
        for term in query_terms:
            matching_documents = matching_document_counts[term]
            if matching_documents == 0:
                continue
            inverse_document_frequency = math.log(
                1 + (document_count - matching_documents + 0.5) / (matching_documents + 0.5)
            )
            term_frequency = frequency[term]
            length_normalization = path.k1 * (1 - path.b + path.b * len(document) / average_length)
            score += inverse_document_frequency * (
                term_frequency * (path.k1 + 1) / (term_frequency + length_normalization)
            )
        scores.append(score)
    return scores


def _token_overlap_scores(
    query: str,
    units: list[_RetrievalUnit],
    path: RetrievalPath,
) -> list[float]:
    query_terms = set(tokens(query))
    scores: list[float] = []
    for unit in units:
        document = set(
            _weighted_tokens(
                unit,
                title_boost=path.title_boost,
                section_boost=path.section_boost,
            )
        )
        scores.append(len(query_terms & document) / math.sqrt(max(1, len(document))))
    return scores


def _stored_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _resolve_stored_path(path: str) -> Path:
    stored = Path(path)
    return stored if stored.is_absolute() else PROJECT_ROOT / stored


def _validate_candidate_audit(path: Path, manifest: SourceManifest) -> None:
    audit = _SourceCandidateAudit.model_validate_json(path.read_text(encoding="utf-8"))
    included_source_ids = {
        candidate.source_id for candidate in audit.candidates if candidate.decision.included
    }
    manifest_source_ids = {source.id for source in manifest.sources}
    if included_source_ids != manifest_source_ids:
        raise ValueError(
            "candidate audit included decisions must exactly match the source manifest"
        )
