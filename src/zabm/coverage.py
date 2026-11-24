from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from zabm.agent import answer_question
from zabm.compatibility import CompatibilityCatalog
from zabm.procedures import (
    RetrievalCatalog,
    procedure_completeness_issues,
    resolve_procedure_evidence,
)
from zabm.response import CanonicalResponse
from zabm.specifications import SourceRecord, SpecificationCatalog, load_source_manifest

EvidenceType = Literal["specification", "compatibility", "procedure"]
ResponseType = Literal["specification", "compatibility", "procedure"]
CoverageStatus = Literal["supported", "not_found"]
CompatibilityOutcome = Literal["compatible", "not_compatible", "unknown"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CoverageCitationExpectation(_StrictModel):
    document_id: str
    physical_page: int = Field(ge=1)


class CoverageExpectation(_StrictModel):
    response_type: ResponseType
    status: CoverageStatus
    claim_ids: list[str] = Field(default_factory=list[str])
    citations: list[CoverageCitationExpectation] = Field(
        default_factory=list[CoverageCitationExpectation]
    )
    compatibility_outcome: CompatibilityOutcome | None = None
    failure_contains: str | None = None


class CoverageCase(_StrictModel):
    id: str
    source_id: str
    evidence_type: EvidenceType
    question: str
    expected: CoverageExpectation


class UnanswerableContent(_StrictModel):
    id: str
    source_id: str
    evidence_type: EvidenceType
    physical_page: int = Field(ge=1)
    question: str
    reason: str
    expected_failure_contains: str


class CoverageSet(_StrictModel):
    coverage_set_id: str
    cases: list[CoverageCase] = Field(min_length=1)
    unanswerable_content: list[UnanswerableContent] = Field(
        default_factory=list[UnanswerableContent]
    )


class ObservedClaim(_StrictModel):
    claim_id: str
    text: str


class ObservedCitation(_StrictModel):
    document_id: str
    physical_page: int
    printed_page: int
    section: str


class CoverageCaseResult(_StrictModel):
    id: str
    source_id: str
    evidence_type: EvidenceType
    question: str
    expected_status: CoverageStatus
    observed_response_type: str
    observed_status: str
    passed: bool
    claims: list[ObservedClaim] = Field(default_factory=list[ObservedClaim])
    citations: list[ObservedCitation] = Field(default_factory=list[ObservedCitation])
    compatibility_outcome: CompatibilityOutcome | None = None
    failure_message: str | None = None
    issues: list[str] = Field(default_factory=list[str])


class UnanswerableContentResult(_StrictModel):
    id: str
    source_id: str
    evidence_type: EvidenceType
    physical_page: int
    question: str
    reason: str
    observed_status: str
    failure_message: str | None = None
    passed: bool
    issues: list[str] = Field(default_factory=list[str])


class SourceCoverage(_StrictModel):
    source_id: str
    title: str
    accepted_case_count: int
    rejected_case_count: int
    unanswerable_count: int
    specification_count: int
    eligible_specification_count: int
    compatibility_rule_count: int
    eligible_compatibility_rule_count: int
    procedure_count: int
    complete_procedure_count: int
    validation_issues: list[str] = Field(default_factory=list[str])


class CoverageReport(_StrictModel):
    coverage_set_id: str
    source_pack_id: str
    passed: bool
    case_results: list[CoverageCaseResult]
    unanswerable_content: list[UnanswerableContentResult]
    sources: list[SourceCoverage]
    issues: list[str] = Field(default_factory=list[str])


def run_coverage(
    manifest_path: Path,
    coverage_set_path: Path,
    data_dir: Path,
) -> CoverageReport:
    manifest = load_source_manifest(manifest_path)
    coverage_set = CoverageSet.model_validate_json(coverage_set_path.read_text(encoding="utf-8"))
    source_records = {source.id: source for source in manifest.sources}
    issues = _validate_coverage_set(coverage_set, source_records)

    case_results: list[CoverageCaseResult] = []
    for case in coverage_set.cases:
        response = answer_question(case.question, data_dir)
        response_issues = _case_issues(case, response)
        observed_compatibility = None
        if response.compatibility is not None:
            outcome = response.compatibility.outcome
            if outcome != "not_found":
                observed_compatibility = outcome
        case_results.append(
            CoverageCaseResult(
                id=case.id,
                source_id=case.source_id,
                evidence_type=case.evidence_type,
                question=case.question,
                expected_status=case.expected.status,
                observed_response_type=response.response_type,
                observed_status=response.status,
                passed=not response_issues,
                claims=[
                    ObservedClaim(claim_id=claim.claim_id, text=claim.text)
                    for claim in response.claims
                ],
                citations=[
                    ObservedCitation(
                        document_id=citation.document_id,
                        physical_page=citation.physical_page,
                        printed_page=citation.printed_page,
                        section=citation.section,
                    )
                    for citation in response.citations
                ],
                compatibility_outcome=observed_compatibility,
                failure_message=response.failure.message if response.failure else None,
                issues=response_issues,
            )
        )

    unanswerable_results: list[UnanswerableContentResult] = []
    for item in coverage_set.unanswerable_content:
        response = answer_question(item.question, data_dir)
        item_issues = _unanswerable_issues(item, response)
        unanswerable_results.append(
            UnanswerableContentResult(
                id=item.id,
                source_id=item.source_id,
                evidence_type=item.evidence_type,
                physical_page=item.physical_page,
                question=item.question,
                reason=item.reason,
                observed_status=response.status,
                failure_message=response.failure.message if response.failure else None,
                passed=not item_issues,
                issues=item_issues,
            )
        )

    catalogs = _load_catalogs(data_dir, manifest.manifest_version, issues)
    sources = _source_coverage(
        manifest.sources,
        case_results,
        unanswerable_results,
        catalogs,
    )
    for source in sources:
        if source.accepted_case_count == 0:
            issues.append(f"source {source.source_id} has no accepted CLI coverage case")
        if source.unanswerable_count == 0:
            issues.append(f"source {source.source_id} has no rejected or unanswerable content")

    return CoverageReport(
        coverage_set_id=coverage_set.coverage_set_id,
        source_pack_id=manifest.manifest_version,
        passed=not issues
        and all(result.passed for result in case_results)
        and all(result.passed for result in unanswerable_results),
        case_results=case_results,
        unanswerable_content=unanswerable_results,
        sources=sources,
        issues=issues,
    )


def _validate_coverage_set(
    coverage_set: CoverageSet,
    source_records: Mapping[str, SourceRecord],
) -> list[str]:
    issues: list[str] = []
    case_ids = [case.id for case in coverage_set.cases]
    unanswerable_ids = [item.id for item in coverage_set.unanswerable_content]
    all_ids = [*case_ids, *unanswerable_ids]
    duplicates = sorted({item_id for item_id in all_ids if all_ids.count(item_id) > 1})
    if duplicates:
        issues.append(f"coverage item IDs must be unique: {', '.join(duplicates)}")

    for case in coverage_set.cases:
        if case.source_id not in source_records:
            issues.append(f"coverage case {case.id} references unknown source {case.source_id}")
        if case.evidence_type != case.expected.response_type:
            issues.append(
                f"coverage case {case.id} evidence type does not match its expected response type"
            )
        if case.expected.status == "supported" and not case.expected.claim_ids:
            issues.append(f"supported coverage case {case.id} has no expected claim IDs")
        if case.expected.status == "not_found" and case.expected.claim_ids:
            issues.append(f"not-found coverage case {case.id} must not expect claims")
    for item in coverage_set.unanswerable_content:
        if item.source_id not in source_records:
            issues.append(
                f"unanswerable content {item.id} references unknown source {item.source_id}"
            )
    return issues


def _case_issues(case: CoverageCase, response: CanonicalResponse) -> list[str]:
    issues: list[str] = []
    if response.response_type != case.expected.response_type:
        issues.append(
            f"expected response type {case.expected.response_type}, "
            f"observed {response.response_type}"
        )
    if response.status != case.expected.status:
        issues.append(f"expected status {case.expected.status}, observed {response.status}")
    observed_claim_ids = [claim.claim_id for claim in response.claims]
    if len(observed_claim_ids) != len(set(observed_claim_ids)) or set(observed_claim_ids) != set(
        case.expected.claim_ids
    ):
        issues.append(
            "claim IDs differ: expected "
            f"{sorted(case.expected.claim_ids)}, observed {sorted(observed_claim_ids)}"
        )

    observed_citations = {
        (citation.document_id, citation.physical_page) for citation in response.citations
    }
    for expected in case.expected.citations:
        locator = (expected.document_id, expected.physical_page)
        if locator not in observed_citations:
            issues.append(
                f"missing citation {expected.document_id} physical page {expected.physical_page}"
            )
    if case.expected.status == "supported":
        if not response.citations:
            issues.append("supported coverage case returned no citations")
        if case.source_id not in {citation.document_id for citation in response.citations}:
            issues.append(f"supported coverage case did not cite source {case.source_id}")
    else:
        if response.claims or response.citations:
            issues.append("not-found coverage case returned substantive evidence")
        if _has_substantive_payload(response):
            issues.append("not-found coverage case returned a substantive payload")
        failure_message = response.failure.message if response.failure else ""
        if not response.failure or response.failure.code != "not_found":
            issues.append("not-found coverage case has no not_found failure")
        expected_text = case.expected.failure_contains
        if expected_text and expected_text not in failure_message:
            issues.append(
                f"failure message does not contain {expected_text!r}: {failure_message!r}"
            )

    if case.expected.compatibility_outcome is not None:
        observed = response.compatibility.outcome if response.compatibility is not None else None
        if observed != case.expected.compatibility_outcome:
            issues.append(
                f"expected compatibility outcome "
                f"{case.expected.compatibility_outcome}, observed {observed}"
            )
    return issues


def _unanswerable_issues(
    item: UnanswerableContent,
    response: CanonicalResponse,
) -> list[str]:
    issues: list[str] = []
    if response.status != "not_found":
        issues.append(f"expected not_found, observed {response.status}")
    if response.claims or response.citations:
        issues.append("unanswerable content returned claims or citations")
    if _has_substantive_payload(response):
        issues.append("unanswerable content returned a substantive payload")
    failure_message = response.failure.message if response.failure else ""
    if not response.failure or response.failure.code != "not_found":
        issues.append("unanswerable content has no not_found failure")
    if item.expected_failure_contains not in failure_message:
        issues.append(
            f"failure message does not contain "
            f"{item.expected_failure_contains!r}: {failure_message!r}"
        )
    return issues


def _has_substantive_payload(response: CanonicalResponse) -> bool:
    compatibility = response.compatibility
    substantive_compatibility = compatibility is not None and (
        compatibility.outcome != "not_found"
        or compatibility.component_a is not None
        or compatibility.component_b is not None
    )
    return (
        response.specification is not None
        or substantive_compatibility
        or response.procedure is not None
    )


def _load_catalogs(
    data_dir: Path,
    manifest_version: str,
    issues: list[str],
) -> tuple[
    SpecificationCatalog | None,
    CompatibilityCatalog | None,
    RetrievalCatalog | None,
]:
    generated_dir = data_dir / "generated"
    specifications_path = generated_dir / "specifications.json"
    compatibility_path = generated_dir / "compatibility.json"
    retrieval_path = generated_dir / "retrieval.json"
    specifications = None
    compatibility = None
    retrieval = None
    try:
        if specifications_path.is_file():
            specifications = SpecificationCatalog.model_validate_json(
                specifications_path.read_text(encoding="utf-8")
            )
            if specifications.source_pack_id != manifest_version:
                issues.append("specification evidence source-pack ID does not match the manifest")
        else:
            issues.append("specification evidence has not been ingested")
        if compatibility_path.is_file():
            compatibility = CompatibilityCatalog.model_validate_json(
                compatibility_path.read_text(encoding="utf-8")
            )
            if compatibility.source_pack_id != manifest_version:
                issues.append("compatibility evidence source-pack ID does not match the manifest")
        else:
            issues.append("compatibility evidence has not been ingested")
        if retrieval_path.is_file():
            retrieval = RetrievalCatalog.model_validate_json(
                retrieval_path.read_text(encoding="utf-8")
            )
            if retrieval.source_pack_id != manifest_version:
                issues.append("retrieval evidence source-pack ID does not match the manifest")
        else:
            issues.append("retrieval evidence has not been ingested")
    except (OSError, ValueError) as exc:
        issues.append(f"could not inspect generated evidence: {exc}")
    return specifications, compatibility, retrieval


def _source_coverage(
    manifest_sources: list[SourceRecord],
    case_results: list[CoverageCaseResult],
    unanswerable_results: list[UnanswerableContentResult],
    catalogs: tuple[
        SpecificationCatalog | None,
        CompatibilityCatalog | None,
        RetrievalCatalog | None,
    ],
) -> list[SourceCoverage]:
    specifications, compatibility, retrieval = catalogs
    reports: list[SourceCoverage] = []
    for manifest_source in manifest_sources:
        source_id = manifest_source.id
        accepted = [
            result
            for result in case_results
            if result.source_id == source_id
            and result.passed
            and result.observed_status == "supported"
        ]
        rejected = [
            result
            for result in case_results
            if result.source_id == source_id and result.expected_status == "not_found"
        ]
        unanswerable = [result for result in unanswerable_results if result.source_id == source_id]
        stored_specifications = (
            [
                item
                for item in specifications.specifications
                if item.specification.source_id == source_id
            ]
            if specifications is not None
            else []
        )
        stored_compatibility = (
            [item for item in compatibility.compatibility_rules if item.rule.source_id == source_id]
            if compatibility is not None
            else []
        )
        stored_procedures = (
            [
                resolve_procedure_evidence(procedure, retrieval.sources)
                for procedure in retrieval.procedures
                if procedure.document_id == source_id
            ]
            if retrieval is not None
            else []
        )
        validation_issues = [
            *(
                f"{item.specification.id}: {issue}"
                for item in stored_specifications
                for issue in item.validation_issues
            ),
            *(
                f"{item.rule.id}: {issue}"
                for item in stored_compatibility
                for issue in item.validation_issues
            ),
            *(
                f"{procedure.procedure_id}: {issue}"
                for procedure in stored_procedures
                for issue in procedure_completeness_issues(procedure)
            ),
        ]
        reports.append(
            SourceCoverage(
                source_id=source_id,
                title=manifest_source.title,
                accepted_case_count=len(accepted),
                rejected_case_count=len(rejected),
                unanswerable_count=len(rejected) + len(unanswerable),
                specification_count=len(stored_specifications),
                eligible_specification_count=sum(
                    not item.validation_issues for item in stored_specifications
                ),
                compatibility_rule_count=len(stored_compatibility),
                eligible_compatibility_rule_count=sum(
                    not item.validation_issues for item in stored_compatibility
                ),
                procedure_count=len(stored_procedures),
                complete_procedure_count=sum(
                    not procedure_completeness_issues(procedure) for procedure in stored_procedures
                ),
                validation_issues=sorted(set(validation_issues)),
            )
        )
    return reports
