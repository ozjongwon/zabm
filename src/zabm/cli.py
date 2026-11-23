from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pypdf._configuration import overwrite_configuration

from zabm import __version__
from zabm.agent import answer_question
from zabm.compatibility import ingest_compatibility
from zabm.coverage import run_coverage
from zabm.evaluation_set import (
    build_evaluation_report,
    create_evaluation_freeze,
    load_evaluation_set,
    validate_evaluation_set,
    verify_evaluation_freeze,
)
from zabm.procedures import (
    ProcedureEvidenceInspection,
    ingest_retrieval,
    inspect_procedure_evidence,
)
from zabm.providers import ProviderError, configured_provider
from zabm.response import CanonicalResponse
from zabm.source_pack import (
    FrozenSourcePackError,
    freeze_source_pack,
    run_retrieval_smoke,
    verify_frozen_source_pack,
    verify_source_freeze,
    write_retrieval_smoke_report,
)
from zabm.specifications import (
    IngestionError,
    SourceIntegrityError,
    download_sources,
    file_sha256,
    ingest_sources,
    load_source_manifest,
    verify_source_files,
)

PINNED_PYTHON = "3.13.5"
PINNED_DEPENDENCIES = {"pydantic": "2.14.3", "pypdf": "6.21.4"}
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "data" / "manifests" / "source-pack-v1.json"
DEFAULT_EVIDENCE = REPO_ROOT / "data" / "evidence" / "verified-specifications.json"
DEFAULT_COMPATIBILITY_EVIDENCE = REPO_ROOT / "data" / "evidence" / "verified-compatibility.json"
DEFAULT_SMOKE_SET = REPO_ROOT / "data" / "retrieval-smoke" / "smoke-set-v1.json"
DEFAULT_RETRIEVAL_CONFIG = REPO_ROOT / "data" / "retrieval-smoke" / "retrieval-config-v1.json"
DEFAULT_SMOKE_REPORT = REPO_ROOT / "data" / "retrieval-smoke" / "report-v1.json"
DEFAULT_SOURCE_FREEZE = REPO_ROOT / "data" / "manifests" / "source-pack-freeze-v1.json"
DEFAULT_COVERAGE_SET = REPO_ROOT / "data" / "coverage" / "coverage-v1.json"
DEFAULT_EVALUATION_SET = REPO_ROOT / "data" / "evaluation" / "evaluation-set-v1.json"
DEFAULT_EVALUATION_FREEZE = REPO_ROOT / "data" / "evaluation" / "evaluation-freeze-v1.json"
DEFAULT_DATA_DIR = REPO_ROOT / ".zabm"
DEFAULT_PDF_DIR = REPO_ROOT / "pdf-doc"


class HealthReport(BaseModel):
    status: Literal["ok"]
    application_version: str
    python_version: str
    executable: str
    dependencies: dict[str, str]


def _installed_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "not-installed"


def _build_health_report() -> HealthReport:
    python_version = platform.python_version()
    dependencies = {package: _installed_version(package) for package in PINNED_DEPENDENCIES}

    if python_version != PINNED_PYTHON:
        raise RuntimeError(
            f"expected Python {PINNED_PYTHON}, found {python_version}; run ./scripts/install-dev.sh"
        )

    mismatches = [
        f"{package} {installed} (expected {expected})"
        for package, expected in PINNED_DEPENDENCIES.items()
        if (installed := dependencies[package]) != expected
    ]
    if mismatches:
        details = ", ".join(mismatches)
        raise RuntimeError(
            f"pinned runtime dependencies are not ready: {details}; run ./scripts/install-dev.sh"
        )

    return HealthReport(
        status="ok",
        application_version=__version__,
        python_version=python_version,
        executable=sys.executable,
        dependencies=dependencies,
    )


def _health_command(as_json: bool) -> int:
    try:
        report = _build_health_report()
    except RuntimeError as exc:
        print(f"zabm health: {exc}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(report.model_dump(), indent=2, sort_keys=True))
    else:
        print(f"zabm {report.application_version} is ready (Python {report.python_version})")
    return 0


def _download_command(manifest: Path, pdf_dir: Path, as_json: bool) -> int:
    try:
        report = download_sources(manifest, pdf_dir)
    except (OSError, SourceIntegrityError, ValueError) as exc:
        print(f"zabm download: {exc}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        print(f"Downloaded and verified {report.source_count} source(s).")
        for source in report.sources:
            print(f"- {source['id']}: {source['title']} ({source['manufacturer']})")
            print(f"  {source['url']}")
            print(
                f"  sha256: {source['sha256']} "
                f"(retrieved {source['retrieval_date']}, {source['revision']})"
            )
    return 0


def _ingest_command(
    manifest: Path,
    evidence: Path,
    compatibility_evidence: Path,
    pdf_dir: Path,
    data_dir: Path,
    freeze_path: Path | None,
    as_json: bool,
) -> int:
    try:
        source_freeze = freeze_path
        if (
            source_freeze is None
            and manifest.resolve() == DEFAULT_MANIFEST.resolve()
            and DEFAULT_SOURCE_FREEZE.is_file()
        ):
            source_freeze = DEFAULT_SOURCE_FREEZE
        if source_freeze is not None:
            if not source_freeze.is_file():
                raise FrozenSourcePackError(f"source freeze {source_freeze} does not exist")
            verify_frozen_source_pack(source_freeze, manifest)
        verify_source_files(manifest, pdf_dir)
        report = ingest_sources(manifest, evidence, pdf_dir, data_dir)
        compatibility_report = ingest_compatibility(
            manifest,
            compatibility_evidence,
            pdf_dir,
            data_dir,
        )
        retrieval_report = ingest_retrieval(manifest, pdf_dir, data_dir)
    except (OSError, FrozenSourcePackError, IngestionError, ValueError) as exc:
        print(f"zabm ingest: {exc}", file=sys.stderr)
        return 1

    artifact_paths = {
        "specifications.json": data_dir / "generated" / "specifications.json",
        "compatibility.json": data_dir / "generated" / "compatibility.json",
        "retrieval.json": data_dir / "generated" / "retrieval.json",
    }
    artifact_checksums = {name: file_sha256(path) for name, path in artifact_paths.items()}
    if as_json:
        combined_report = {
            **report.model_dump(mode="json"),
            "compatibility_rule_count": compatibility_report.compatibility_rule_count,
            "eligible_compatibility_rule_count": (
                compatibility_report.eligible_compatibility_rule_count
            ),
            "retrieval_page_count": retrieval_report.page_count,
            "page_alignment": retrieval_report.page_alignment.model_dump(mode="json"),
            "table_row_count": retrieval_report.table_row_count,
            "warning_count": retrieval_report.warning_count,
            "procedure_count": retrieval_report.procedure_count,
            "eligible_procedure_count": retrieval_report.eligible_procedure_count,
            "artifact_checksums": artifact_checksums,
            "validation_issues": [
                *report.validation_issues,
                *compatibility_report.validation_issues,
                *retrieval_report.validation_issues,
            ],
        }
        print(json.dumps(combined_report, indent=2, sort_keys=True))
    else:
        print(
            f"Ingested {report.specification_count} specification(s) from "
            f"{report.source_count} source(s) from {report.manufacturer_count} "
            f"manufacturer(s); "
            f"{report.eligible_specification_count} eligible."
        )
        print(
            f"Ingested {compatibility_report.compatibility_rule_count} compatibility "
            f"rule(s); {compatibility_report.eligible_compatibility_rule_count} eligible."
        )
        print(
            f"Ingested {retrieval_report.procedure_count} service procedure(s) from "
            f"{retrieval_report.page_count} retrieval page(s); "
            f"{retrieval_report.eligible_procedure_count} complete."
        )
        alignment = retrieval_report.page_alignment
        print(
            f"Page alignment: {alignment.parsed_page_count}/"
            f"{alignment.physical_page_count} parsed, "
            f"{alignment.text_page_count} with text."
        )
        for name, checksum in artifact_checksums.items():
            print(f"- {name}: sha256 {checksum}")
        for issue in [
            *report.validation_issues,
            *compatibility_report.validation_issues,
            *retrieval_report.validation_issues,
        ]:
            print(f"- rejected: {issue}", file=sys.stderr)
    return 0


def _render_response(response: CanonicalResponse) -> str:
    if response.status in {"not_found", "out_of_scope", "conflicting_evidence"}:
        assert response.failure is not None
        if response.status == "conflicting_evidence":
            return "\n".join(
                [
                    f"conflicting_evidence: {response.failure.message}",
                    _render_conflict_record(response),
                ]
            )
        return f"{response.status}: {response.failure.message}"

    if response.status == "clarification_required":
        assert response.clarification is not None
        return f"clarification_required: {response.clarification.message}"

    if response.response_type == "compatibility":
        assert response.compatibility is not None
        compatibility = response.compatibility
        assert compatibility.component_a is not None
        assert compatibility.component_b is not None
        citation = response.citations[0]
        conditions = "; ".join(compatibility.conditions)
        rendered = (
            f"{compatibility.component_a.name} with {compatibility.component_b.name}: "
            f"{compatibility.outcome}\n"
            f"Conditions: {conditions}\n"
            f"Source: {citation.title}, printed page {citation.printed_page}, "
            f"physical page {citation.physical_page}, {citation.section}, "
            f"retrieved {citation.retrieval_date.isoformat()}"
        )
        return _append_conflict_record(rendered, response)

    if response.response_type == "procedure":
        assert response.procedure is not None
        procedure = response.procedure
        lines = [procedure.title]
        for step in procedure.steps:
            lines.append(f"{step.number}. {step.text}")
            lines.extend(
                f"   {warning.severity.upper()}: {warning.text}" for warning in step.warnings
            )
            citation = step.citation
            lines.append(
                f"   Source: {citation.title}, printed page {citation.printed_page}, "
                f"physical page {citation.physical_page}, {citation.section}, "
                f"retrieved {citation.retrieval_date.isoformat()}"
            )
        return _append_conflict_record("\n".join(lines), response)

    assert response.specification is not None
    specification = response.specification
    citation = response.citations[0]
    conditions = "; ".join(specification.conditions)
    rendered = (
        f"{specification.manufacturer} {specification.model} "
        f"{specification.component} {specification.attribute}: "
        f"{specification.value.display}\n"
        f"Conditions: {conditions}\n"
        f"Source: {citation.title}, printed page {citation.printed_page}, "
        f"physical page {citation.physical_page}, {citation.section}, "
        f"retrieved {citation.retrieval_date.isoformat()}"
    )
    return _append_conflict_record(rendered, response)


def _append_conflict_record(rendered: str, response: CanonicalResponse) -> str:
    if response.conflicts is None:
        return rendered
    return f"{rendered}\n\n{_render_conflict_record(response)}"


def _render_conflict_record(response: CanonicalResponse) -> str:
    assert response.conflicts is not None
    conflicts = response.conflicts
    if conflicts.precedence_established:
        lines = ["Conflict resolved by cited precedence:"]
    else:
        lines = ["Applicable evidence:"]
    for candidate in conflicts.candidates:
        state = "selected" if candidate.selected else "rejected"
        lines.append(f"- {state}: {candidate.claim}")
        lines.append(f"  Excerpt: {' '.join(candidate.excerpts)}")
        for citation in candidate.citations:
            lines.append(
                f"  Source: {citation.title}, printed page {citation.printed_page}, "
                f"physical page {citation.physical_page}, {citation.section}, "
                f"retrieved {citation.retrieval_date.isoformat()}"
            )
    if conflicts.precedence is not None:
        precedence = conflicts.precedence
        lines.append(f"Precedence ({precedence.kind}): {precedence.reason}")
        lines.append(f"  Excerpt: {precedence.excerpt}")
        citation = precedence.citation
        lines.append(
            f"  Source: {citation.title}, printed page {citation.printed_page}, "
            f"physical page {citation.physical_page}, {citation.section}, "
            f"retrieved {citation.retrieval_date.isoformat()}"
        )
    return "\n".join(lines)


def _ask_command(
    question: str,
    data_dir: Path,
    as_json: bool,
    *,
    provider: str | None,
    provider_url: str | None,
    model: str | None,
    embedding_model: str | None,
    provider_configuration: str | None,
) -> int:
    try:
        model_provider = configured_provider(
            provider=provider,
            base_url=provider_url,
            model=model,
            embedding_model=embedding_model,
            configuration=provider_configuration,
        )
        response = answer_question(question, data_dir, model_provider)
    except ProviderError as exc:
        print(f"zabm ask: {exc}", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps(response.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        print(_render_response(response))
    return 0


def _evidence_command(question: str, data_dir: Path, as_json: bool) -> int:
    inspection = inspect_procedure_evidence(question, data_dir)
    if as_json:
        print(json.dumps(inspection.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        _render_evidence(inspection)
    return 0


def _retrieval_smoke_command(
    manifest: Path,
    smoke_set: Path,
    retrieval_config: Path,
    pdf_dir: Path | None,
    data_dir: Path,
    report_path: Path,
    freeze_path: Path | None,
    maintainer_review: str | None,
    candidate_audit: Path | None,
    as_json: bool,
) -> int:
    try:
        source_freeze = freeze_path
        if (
            source_freeze is None
            and manifest.resolve() == DEFAULT_MANIFEST.resolve()
            and report_path.resolve() == DEFAULT_SMOKE_REPORT.resolve()
            and DEFAULT_SOURCE_FREEZE.is_file()
        ):
            source_freeze = DEFAULT_SOURCE_FREEZE
        if source_freeze is not None and source_freeze.is_file():
            verify_source_freeze(
                source_freeze,
                manifest,
                smoke_set,
                retrieval_config,
                report_path,
            )
        verify_source_files(manifest, pdf_dir or data_dir.parent / "pdf-doc")
        report = run_retrieval_smoke(
            manifest,
            smoke_set,
            retrieval_config,
            data_dir,
        )
        write_retrieval_smoke_report(report, report_path)
    except (OSError, FrozenSourcePackError, SourceIntegrityError, ValueError) as exc:
        print(f"zabm retrieval-smoke: {exc}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        for result in report.path_results:
            state = "passed" if result.passed else "failed"
            print(
                f"{result.path_id}: Recall@5 {result.recall_at_5:.1%} "
                f"({result.hit_count}/{result.item_count}); {state}"
            )
        print(f"Threshold decision: {'passed' if report.threshold_decision.passed else 'failed'}")

    if not report.threshold_decision.passed:
        print(
            "zabm retrieval-smoke: no retrieval path met the required Recall@5 threshold",
            file=sys.stderr,
        )
        return 1

    if freeze_path is not None:
        if maintainer_review is None or not maintainer_review.strip():
            print(
                "zabm retrieval-smoke: --maintainer-review is required with --freeze",
                file=sys.stderr,
            )
            return 1
        try:
            freeze_source_pack(
                manifest,
                smoke_set,
                retrieval_config,
                report_path,
                freeze_path,
                maintainer_review=maintainer_review,
                candidate_audit_path=candidate_audit,
            )
        except (OSError, ValueError) as exc:
            print(f"zabm retrieval-smoke: {exc}", file=sys.stderr)
            return 1
        if not as_json:
            print(f"Frozen source pack: {freeze_path}")
    return 0


def _render_evidence(inspection: ProcedureEvidenceInspection) -> None:
    if not inspection.matches:
        print("No retrieval-evidence section matches this procedure question.")
        return
    for match in inspection.matches:
        state = "complete" if match.complete else "partial"
        pages = ", ".join(str(page.printed_page) for page in match.pages)
        print(f"{match.title} ({state}; printed pages {pages})")
        for issue in match.validation_issues:
            print(f"- {issue}")
        for step in match.steps:
            print(f"{step.number}. {step.text}")
            for warning in step.warnings:
                print(f"   {warning.severity.upper()}: {warning.text}")


def _coverage_command(
    manifest: Path,
    coverage_set: Path,
    data_dir: Path,
    as_json: bool,
) -> int:
    try:
        report = run_coverage(manifest, coverage_set, data_dir)
    except (OSError, ValueError) as exc:
        print(f"zabm coverage: {exc}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        accepted = sum(result.observed_status == "supported" for result in report.case_results)
        rejected = sum(result.observed_status == "not_found" for result in report.case_results)
        print(
            f"Coverage {'passed' if report.passed else 'failed'} across "
            f"{len(report.sources)} source(s): {accepted} accepted, {rejected} rejected, "
            f"{len(report.unanswerable_content)} explicitly unanswerable."
        )
        for source in report.sources:
            print(
                f"- {source.source_id}: {source.accepted_case_count} accepted, "
                f"{source.unanswerable_count} unavailable; "
                f"{source.eligible_specification_count}/"
                f"{source.specification_count} specifications, "
                f"{source.eligible_compatibility_rule_count}/"
                f"{source.compatibility_rule_count} compatibility rules, "
                f"{source.complete_procedure_count}/{source.procedure_count} "
                "procedures complete"
            )
        for issue in report.issues:
            print(f"- coverage issue: {issue}", file=sys.stderr)
        for result in report.case_results:
            for issue in result.issues:
                print(f"- {result.id}: {issue}", file=sys.stderr)
        for result in report.unanswerable_content:
            for issue in result.issues:
                print(f"- {result.id}: {issue}", file=sys.stderr)
    return 0 if report.passed else 1


def _evaluation_set_command(
    evaluation_set_path: Path,
    manifest_path: Path,
    pdf_dir: Path,
    source_pack_freeze_path: Path,
    freeze_path: Path | None,
    verify_freeze_path: Path | None,
    maintainer_review: str | None,
    as_json: bool,
) -> int:
    try:
        evaluation_set = load_evaluation_set(evaluation_set_path)
        manifest = load_source_manifest(manifest_path)
        issues = validate_evaluation_set(evaluation_set, manifest, pdf_dir)
    except (OSError, ValueError) as exc:
        print(f"zabm evaluation-set: {exc}", file=sys.stderr)
        return 1

    if issues:
        for issue in issues:
            print(f"zabm evaluation-set: {issue}", file=sys.stderr)
        return 1

    effective_verify_path = verify_freeze_path
    if (
        effective_verify_path is None
        and freeze_path is None
        and evaluation_set_path.resolve() == DEFAULT_EVALUATION_SET.resolve()
        and DEFAULT_EVALUATION_FREEZE.is_file()
    ):
        effective_verify_path = DEFAULT_EVALUATION_FREEZE
    freeze_verified = effective_verify_path is not None
    if effective_verify_path is not None:
        try:
            verify_evaluation_freeze(
                effective_verify_path,
                evaluation_set_path,
                manifest_path,
                source_pack_freeze_path,
            )
        except (OSError, ValueError) as exc:
            print(f"zabm evaluation-set: {exc}", file=sys.stderr)
            return 1

    if freeze_path is not None:
        if maintainer_review is None or not maintainer_review.strip():
            print(
                "zabm evaluation-set: --maintainer-review is required with --freeze",
                file=sys.stderr,
            )
            return 1
        try:
            create_evaluation_freeze(
                evaluation_set_path,
                evaluation_set,
                manifest,
                manifest_path,
                source_pack_freeze_path,
                freeze_path,
                maintainer_review=maintainer_review,
            )
        except (OSError, ValueError) as exc:
            print(f"zabm evaluation-set: {exc}", file=sys.stderr)
            return 1

    report = build_evaluation_report(
        evaluation_set,
        freeze_verified=freeze_verified,
    )
    if as_json:
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        counts = ", ".join(
            f"{category} {count}" for category, count in report.category_counts.items()
        )
        print(f"Evaluation set {report.evaluation_set_id} is valid: {counts}.")
        if freeze_verified:
            print("Frozen expected outcomes verified.")
        if freeze_path is not None:
            print(f"Frozen evaluation set: {freeze_path}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zabm",
        description="Bicycle maintenance assistant with evidence gates.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)

    health = commands.add_parser(
        "health",
        help="Check that the pinned development environment is ready.",
    )
    health.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable health report.",
    )

    download = commands.add_parser(
        "download",
        help="Download and verify the pinned source pack.",
    )
    download.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the source manifest.",
    )
    download.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDF_DIR,
        help="Directory for original downloaded PDFs.",
    )
    download.add_argument("--json", action="store_true", help="Emit a JSON report.")

    ingest = commands.add_parser(
        "ingest",
        help="Validate sources and build the structured and retrieval evidence stores.",
    )
    ingest.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the source manifest.",
    )
    ingest.add_argument(
        "--evidence",
        type=Path,
        default=DEFAULT_EVIDENCE,
        help="Path to the human-verified structured evidence.",
    )
    ingest.add_argument(
        "--compatibility-evidence",
        type=Path,
        default=DEFAULT_COMPATIBILITY_EVIDENCE,
        help="Path to the human-verified compatibility evidence.",
    )
    ingest.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDF_DIR,
        help="Directory containing the downloaded source PDFs.",
    )
    ingest.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory for generated evidence.",
    )
    ingest.add_argument(
        "--freeze",
        type=Path,
        help="Verify this source-pack freeze before writing derived evidence.",
    )
    ingest.add_argument("--json", action="store_true", help="Emit a JSON report.")

    ask = commands.add_parser(
        "ask",
        help="Ask a bicycle maintenance question.",
    )
    ask.add_argument("question", help="Natural-language maintenance question.")
    ask.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory for generated evidence.",
    )
    ask.add_argument(
        "--provider",
        choices=("deterministic", "openai-compatible"),
        default=os.getenv("ZABM_PROVIDER"),
        help="Model provider used for validated claim phrasing.",
    )
    ask.add_argument(
        "--provider-url",
        default=os.getenv("ZABM_PROVIDER_URL"),
        help="Base URL of an OpenAI-compatible provider, including /v1 when required.",
    )
    ask.add_argument(
        "--model",
        default=os.getenv("ZABM_MODEL"),
        help="Model identifier for an OpenAI-compatible provider.",
    )
    ask.add_argument(
        "--embedding-model",
        default=os.getenv("ZABM_EMBEDDING_MODEL"),
        help="Embedding model identifier for an OpenAI-compatible provider.",
    )
    ask.add_argument(
        "--provider-configuration",
        default=os.getenv("ZABM_PROVIDER_CONFIGURATION"),
        help="Stable configuration identifier recorded in the canonical response.",
    )
    ask.add_argument("--json", action="store_true", help="Emit the canonical response.")

    evidence = commands.add_parser(
        "evidence",
        help="Inspect the retrieval evidence selected for a procedure question.",
    )
    evidence.add_argument("question", help="Procedure question to inspect.")
    evidence.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory for generated evidence.",
    )
    evidence.add_argument("--json", action="store_true", help="Emit the evidence report.")

    coverage = commands.add_parser(
        "coverage",
        help="Audit representative CLI coverage across every frozen source document.",
    )
    coverage.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the source manifest.",
    )
    coverage.add_argument(
        "--coverage-set",
        type=Path,
        default=DEFAULT_COVERAGE_SET,
        help="Path to representative accepted and unanswerable coverage cases.",
    )
    coverage.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing generated evidence.",
    )
    coverage.add_argument("--json", action="store_true", help="Emit the coverage report.")

    evaluation_set = commands.add_parser(
        "evaluation-set",
        help="Validate the frozen evaluation set and its expected outcomes.",
    )
    evaluation_set.add_argument(
        "--evaluation-set",
        type=Path,
        default=DEFAULT_EVALUATION_SET,
        help="Path to the frozen evaluation set.",
    )
    evaluation_set.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the frozen source manifest.",
    )
    evaluation_set.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDF_DIR,
        help="Directory containing the frozen source PDFs.",
    )
    evaluation_set.add_argument(
        "--source-freeze",
        type=Path,
        default=DEFAULT_SOURCE_FREEZE,
        help="Path to the frozen source-pack descriptor.",
    )
    evaluation_set.add_argument(
        "--freeze",
        type=Path,
        help="Write an evaluation-set freeze after validation succeeds.",
    )
    evaluation_set.add_argument(
        "--verify-freeze",
        type=Path,
        help="Verify a previously written evaluation-set freeze.",
    )
    evaluation_set.add_argument(
        "--maintainer-review",
        help="Stable review reference recorded when freezing the evaluation set.",
    )
    evaluation_set.add_argument(
        "--json",
        action="store_true",
        help="Emit the evaluation-set validation report.",
    )

    retrieval_smoke = commands.add_parser(
        "retrieval-smoke",
        help="Run the retrieval-only source-pack smoke set and optionally freeze the pack.",
    )
    retrieval_smoke.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the source manifest.",
    )
    retrieval_smoke.add_argument(
        "--smoke-set",
        type=Path,
        default=DEFAULT_SMOKE_SET,
        help="Path to the fixed retrieval-only smoke set.",
    )
    retrieval_smoke.add_argument(
        "--retrieval-config",
        type=Path,
        default=DEFAULT_RETRIEVAL_CONFIG,
        help="Path to the frozen retrieval configuration.",
    )
    retrieval_smoke.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing the generated retrieval evidence.",
    )
    retrieval_smoke.add_argument(
        "--pdf-dir",
        type=Path,
        help="Directory containing the downloaded source PDFs.",
    )
    retrieval_smoke.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_SMOKE_REPORT,
        help="Path for the retrieval-smoke report.",
    )
    retrieval_smoke.add_argument(
        "--freeze",
        type=Path,
        help="Write a source-pack freeze record after the threshold passes.",
    )
    retrieval_smoke.add_argument(
        "--maintainer-review",
        help="Stable review reference recorded when freezing the source pack.",
    )
    retrieval_smoke.add_argument(
        "--candidate-audit",
        type=Path,
        help="Candidate audit whose decisions and checks are bound to the freeze.",
    )
    retrieval_smoke.add_argument(
        "--json",
        action="store_true",
        help="Emit the retrieval-smoke report.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    overwrite_configuration(stream_parsing_work_maximum_count=20_000_000)
    args = _parser().parse_args(argv)
    if args.command == "health":
        return _health_command(args.json)
    if args.command == "download":
        return _download_command(args.manifest, args.pdf_dir, args.json)
    if args.command == "ingest":
        return _ingest_command(
            args.manifest,
            args.evidence,
            args.compatibility_evidence,
            args.pdf_dir,
            args.data_dir,
            args.freeze,
            args.json,
        )
    if args.command == "ask":
        return _ask_command(
            args.question,
            args.data_dir,
            args.json,
            provider=args.provider,
            provider_url=args.provider_url,
            model=args.model,
            embedding_model=args.embedding_model,
            provider_configuration=args.provider_configuration,
        )
    if args.command == "evidence":
        return _evidence_command(args.question, args.data_dir, args.json)
    if args.command == "coverage":
        return _coverage_command(
            args.manifest,
            args.coverage_set,
            args.data_dir,
            args.json,
        )
    if args.command == "evaluation-set":
        return _evaluation_set_command(
            args.evaluation_set,
            args.manifest,
            args.pdf_dir,
            args.source_freeze,
            args.freeze,
            args.verify_freeze,
            args.maintainer_review,
            args.json,
        )
    if args.command == "retrieval-smoke":
        return _retrieval_smoke_command(
            args.manifest,
            args.smoke_set,
            args.retrieval_config,
            args.pdf_dir,
            args.data_dir,
            args.report,
            args.freeze,
            args.maintainer_review,
            args.candidate_audit,
            args.json,
        )
    raise AssertionError(f"unhandled command: {args.command}")
