from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader

from zabm.response import SpecificationValue
from zabm.source_pack import verify_frozen_source_pack
from zabm.specifications import (
    SourceManifest,
    file_sha256,
    write_json,
)

EvaluationCategory = Literal[
    "specification",
    "compatibility",
    "procedure",
    "not_found",
    "conflicting_evidence",
    "out_of_scope",
]
ResponseType = Literal["specification", "compatibility", "procedure", "out_of_scope"]
ExpectedStatus = Literal[
    "supported",
    "clarification_required",
    "not_found",
    "conflicting_evidence",
    "out_of_scope",
]
CompatibilityOutcome = Literal["compatible", "not_compatible", "unknown", "not_found"]
WarningSeverity = Literal["warning", "notice"]
EdgeCase = Literal[
    "adjacent_model",
    "wrong_generation",
    "cross_brand_pair",
    "unsupported_material",
    "missing_attribute",
    "truncated_procedure",
    "ambiguous_alias",
    "false_premise",
]

EXPECTED_CATEGORY_COUNTS: dict[EvaluationCategory, int] = {
    "specification": 36,
    "compatibility": 27,
    "procedure": 27,
    "not_found": 15,
    "conflicting_evidence": 8,
    "out_of_scope": 7,
}
REQUIRED_EDGE_CASES: frozenset[EdgeCase] = frozenset(
    {
        "adjacent_model",
        "wrong_generation",
        "cross_brand_pair",
        "unsupported_material",
        "missing_attribute",
        "truncated_procedure",
        "ambiguous_alias",
        "false_premise",
    }
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceLocator(_StrictModel):
    document_id: str
    physical_page: int = Field(ge=1)
    printed_page: int = Field(ge=1)
    section: str = Field(min_length=1)


class SpecificationExpectation(_StrictModel):
    value: SpecificationValue
    required_qualifiers: list[str] = Field(min_length=1)


class CompatibilityExpectation(_StrictModel):
    outcome: CompatibilityOutcome
    required_qualifiers: list[str] = Field(default_factory=list[str])


class ProcedureWarningExpectation(_StrictModel):
    severity: WarningSeverity
    text: str


class ProcedureStepExpectation(_StrictModel):
    number: int = Field(ge=1)
    text: str
    warnings: list[ProcedureWarningExpectation] = Field(
        default_factory=list[ProcedureWarningExpectation]
    )


class ProcedureExpectation(_StrictModel):
    title: str
    steps: list[ProcedureStepExpectation] = Field(min_length=1)


class ConflictCandidate(_StrictModel):
    claim: str
    evidence_indexes: list[int] = Field(min_length=1)


class ConflictExpectation(_StrictModel):
    candidates: list[ConflictCandidate] = Field(min_length=2)
    precedence_established: bool = False


class ExpectedOutcome(_StrictModel):
    response_type: ResponseType
    status: ExpectedStatus
    specification: SpecificationExpectation | None = None
    compatibility: CompatibilityExpectation | None = None
    procedure: ProcedureExpectation | None = None
    conflicts: ConflictExpectation | None = None
    clarification_missing_information: list[str] = Field(default_factory=list[str])
    failure_contains: str | None = None


class EvaluationItem(_StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]+$")
    category: EvaluationCategory
    question: str = Field(min_length=1)
    edge_cases: list[EdgeCase] = Field(default_factory=list[EdgeCase])
    evidence: list[SourceLocator] = Field(default_factory=list[SourceLocator])
    expected: ExpectedOutcome


class EvaluationSet(_StrictModel):
    evaluation_set_id: str
    source_pack_id: str
    frozen_at: date
    maintainer_review: str
    items: list[EvaluationItem] = Field(min_length=1)


class EvaluationSetReport(_StrictModel):
    status: Literal["valid"] = "valid"
    evaluation_set_id: str
    source_pack_id: str
    item_count: int
    category_counts: dict[EvaluationCategory, int]
    edge_case_counts: dict[EdgeCase, int]
    freeze_verified: bool


class EvaluationFreeze(_StrictModel):
    freeze_version: str
    frozen_at: date
    evaluation_set_id: str
    evaluation_set_path: str
    evaluation_set_sha256: str
    source_pack_id: str
    source_pack_freeze_path: str
    source_pack_freeze_sha256: str
    source_pack_manifest_sha256: str
    item_count: int
    category_counts: dict[EvaluationCategory, int]
    maintainer_review: str


def load_evaluation_set(path: Path) -> EvaluationSet:
    return EvaluationSet.model_validate_json(path.read_text(encoding="utf-8"))


def validate_evaluation_set(
    evaluation_set: EvaluationSet,
    manifest: SourceManifest,
    pdf_dir: Path,
) -> list[str]:
    issues: list[str] = []
    item_ids = [item.id for item in evaluation_set.items]
    duplicates = sorted(item_id for item_id, count in Counter(item_ids).items() if count > 1)
    if duplicates:
        issues.append(f"evaluation item IDs must be unique: {', '.join(duplicates)}")

    if evaluation_set.source_pack_id != manifest.manifest_version:
        issues.append(
            "evaluation set source-pack ID does not match the manifest: "
            f"expected {manifest.manifest_version}, found {evaluation_set.source_pack_id}"
        )

    category_counts = Counter(item.category for item in evaluation_set.items)
    for category, expected_count in EXPECTED_CATEGORY_COUNTS.items():
        found_count = category_counts[category]
        if found_count != expected_count:
            issues.append(f"{category}: expected {expected_count}, found {found_count}")

    observed_edge_cases = {
        edge_case for item in evaluation_set.items for edge_case in item.edge_cases
    }
    for edge_case in sorted(REQUIRED_EDGE_CASES - observed_edge_cases):
        issues.append(f"evaluation set is missing required edge case {edge_case}")

    sources = {source.id: source for source in manifest.sources}
    source_page_counts: dict[str, int] = {}
    for source in manifest.sources:
        source_path = pdf_dir / f"{source.id}.pdf"
        if not source_path.is_file():
            issues.append(f"source {source.id} has not been downloaded for locator validation")
            continue
        try:
            source_page_counts[source.id] = len(PdfReader(source_path).pages)
        except (OSError, ValueError) as exc:
            issues.append(f"could not read source {source.id}: {exc}")

    for item in evaluation_set.items:
        if item.category != "out_of_scope" and not item.evidence:
            issues.append(f"evaluation item {item.id} has no source locator")
        for index, locator in enumerate(item.evidence):
            if locator.document_id not in sources:
                issues.append(
                    f"evaluation item {item.id} references unknown source {locator.document_id}"
                )
                continue
            page_count = source_page_counts.get(locator.document_id)
            if page_count is not None:
                if locator.physical_page > page_count:
                    issues.append(
                        f"evaluation item {item.id} references physical page "
                        f"{locator.physical_page} outside source {locator.document_id} "
                        f"({page_count} pages)"
                    )
                if locator.printed_page > page_count:
                    issues.append(
                        f"evaluation item {item.id} references printed page "
                        f"{locator.printed_page} outside source {locator.document_id} "
                        f"({page_count} pages)"
                    )
            if not locator.section.strip():
                issues.append(f"evaluation item {item.id} evidence {index} has no section locator")

        issues.extend(_expected_outcome_issues(item))
    return issues


def _expected_outcome_issues(item: EvaluationItem) -> list[str]:
    expected = item.expected
    issues: list[str] = []
    if item.category == "specification":
        if expected.response_type != "specification":
            issues.append(f"evaluation item {item.id} has the wrong specification response type")
        if expected.status == "supported":
            if expected.specification is None:
                issues.append(f"evaluation item {item.id} has no expected specification")
            else:
                value = expected.specification.value
                if value.maximum is not None and value.minimum > value.maximum:
                    issues.append(f"evaluation item {item.id} has a reversed specification range")
                if not value.unit.strip() or not value.display.strip():
                    issues.append(f"evaluation item {item.id} has an incomplete normalized value")
    elif item.category == "compatibility":
        if expected.response_type != "compatibility":
            issues.append(f"evaluation item {item.id} has the wrong compatibility response type")
        if expected.status == "supported":
            if expected.compatibility is None:
                issues.append(f"evaluation item {item.id} has no expected compatibility outcome")
            elif not expected.compatibility.required_qualifiers:
                issues.append(f"evaluation item {item.id} has no required compatibility qualifiers")
            elif expected.compatibility.outcome == "not_found":
                issues.append(
                    f"evaluation item {item.id} has a not_found compatibility outcome "
                    "with supported status"
                )
    elif item.category == "procedure":
        if expected.response_type != "procedure":
            issues.append(f"evaluation item {item.id} has the wrong procedure response type")
        if expected.status == "supported":
            if expected.procedure is None:
                issues.append(f"evaluation item {item.id} has no expected procedure")
            else:
                issues.extend(_procedure_expectation_issues(item.id, expected.procedure))
    elif item.category == "not_found" and expected.status != "not_found":
        issues.append(f"evaluation item {item.id} must have not_found status")
    elif item.category == "conflicting_evidence":
        if expected.status != "conflicting_evidence":
            issues.append(f"evaluation item {item.id} must have conflicting_evidence status")
        if expected.conflicts is None:
            issues.append(f"evaluation item {item.id} has no expected conflict candidates")
        else:
            evidence_count = len(item.evidence)
            for candidate in expected.conflicts.candidates:
                for evidence_index in candidate.evidence_indexes:
                    if evidence_index < 0 or evidence_index >= evidence_count:
                        issues.append(
                            f"evaluation item {item.id} conflict candidate references "
                            f"missing evidence index {evidence_index}"
                        )
    elif item.category == "out_of_scope":
        if expected.response_type != "out_of_scope" or expected.status != "out_of_scope":
            issues.append(f"evaluation item {item.id} must have out_of_scope response and status")
        if item.evidence:
            issues.append(f"out-of-scope evaluation item {item.id} must not record evidence")
    if (
        expected.status == "clarification_required"
        and not expected.clarification_missing_information
    ):
        issues.append(f"evaluation item {item.id} has no clarification requirement")
    return issues


def _procedure_expectation_issues(
    item_id: str,
    procedure: ProcedureExpectation,
) -> list[str]:
    issues: list[str] = []
    numbers = [step.number for step in procedure.steps]
    if numbers != list(range(1, len(numbers) + 1)):
        issues.append(f"evaluation item {item_id} procedure steps are not contiguous from 1")
    if any(not step.text.strip() for step in procedure.steps):
        issues.append(f"evaluation item {item_id} procedure contains a blank step")
    if any(not warning.text.strip() for step in procedure.steps for warning in step.warnings):
        issues.append(f"evaluation item {item_id} procedure contains a blank warning")
    return issues


def create_evaluation_freeze(
    evaluation_set_path: Path,
    evaluation_set: EvaluationSet,
    manifest: SourceManifest,
    manifest_path: Path,
    source_pack_freeze_path: Path,
    freeze_path: Path,
    *,
    maintainer_review: str,
) -> EvaluationFreeze:
    if not maintainer_review.strip():
        raise ValueError("a maintainer review reference is required to freeze the evaluation set")
    verify_frozen_source_pack(source_pack_freeze_path, manifest_path)
    category_counts: dict[EvaluationCategory, int] = {
        category: sum(item.category == category for item in evaluation_set.items)
        for category in EXPECTED_CATEGORY_COUNTS
    }
    freeze = EvaluationFreeze(
        freeze_version=f"frozen-{evaluation_set.evaluation_set_id}",
        frozen_at=date.today(),
        evaluation_set_id=evaluation_set.evaluation_set_id,
        evaluation_set_path=_stored_path(evaluation_set_path),
        evaluation_set_sha256=file_sha256(evaluation_set_path),
        source_pack_id=manifest.manifest_version,
        source_pack_freeze_path=_stored_path(source_pack_freeze_path),
        source_pack_freeze_sha256=file_sha256(source_pack_freeze_path),
        source_pack_manifest_sha256=file_sha256(manifest_path),
        item_count=len(evaluation_set.items),
        category_counts=category_counts,
        maintainer_review=maintainer_review,
    )
    freeze_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(freeze_path, freeze.model_dump(mode="json"))
    return freeze


def verify_evaluation_freeze(
    freeze_path: Path,
    evaluation_set_path: Path,
    manifest_path: Path,
    source_pack_freeze_path: Path,
) -> EvaluationFreeze:
    freeze = EvaluationFreeze.model_validate_json(freeze_path.read_text(encoding="utf-8"))
    expected_hashes = {
        "evaluation set": (file_sha256(evaluation_set_path), freeze.evaluation_set_sha256),
        "source-pack freeze": (
            file_sha256(source_pack_freeze_path),
            freeze.source_pack_freeze_sha256,
        ),
        "source-pack manifest": (
            file_sha256(manifest_path),
            freeze.source_pack_manifest_sha256,
        ),
    }
    for label, (current_hash, frozen_hash) in expected_hashes.items():
        if current_hash != frozen_hash:
            if label == "evaluation set":
                raise ValueError(
                    "evaluation set differs from the frozen evaluation set; "
                    "expected outcomes may not change after a baseline"
                )
            raise ValueError(
                f"{label} differs from the frozen evaluation set; a reviewed rerun is required"
            )
    return freeze


def build_evaluation_report(
    evaluation_set: EvaluationSet,
    *,
    freeze_verified: bool,
) -> EvaluationSetReport:
    category_counts: dict[EvaluationCategory, int] = {
        category: sum(item.category == category for item in evaluation_set.items)
        for category in EXPECTED_CATEGORY_COUNTS
    }
    edge_case_counts: Counter[EdgeCase] = Counter(
        edge_case for item in evaluation_set.items for edge_case in item.edge_cases
    )
    ordered_edge_case_counts: dict[EdgeCase, int] = {
        edge_case: edge_case_counts[edge_case] for edge_case in sorted(REQUIRED_EDGE_CASES)
    }
    return EvaluationSetReport(
        evaluation_set_id=evaluation_set.evaluation_set_id,
        source_pack_id=evaluation_set.source_pack_id,
        item_count=len(evaluation_set.items),
        category_counts=category_counts,
        edge_case_counts=ordered_edge_case_counts,
        freeze_verified=freeze_verified,
    )


def _stored_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()
