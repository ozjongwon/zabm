from __future__ import annotations

import argparse
import json
import platform
import re
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from zabm import __version__
from zabm.compatibility import answer_compatibility, ingest_compatibility
from zabm.procedures import (
    ProcedureEvidenceInspection,
    answer_procedure,
    ingest_retrieval,
    inspect_procedure_evidence,
)
from zabm.response import CanonicalResponse
from zabm.specifications import (
    IngestionError,
    SourceIntegrityError,
    answer_specification,
    download_sources,
    ingest_sources,
)

PINNED_PYTHON = "3.13.5"
PINNED_DEPENDENCIES = {"pydantic": "2.14.3", "pypdf": "6.21.4"}
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "data" / "manifests" / "source-pack-v1.json"
DEFAULT_EVIDENCE = REPO_ROOT / "data" / "evidence" / "verified-specifications.json"
DEFAULT_COMPATIBILITY_EVIDENCE = REPO_ROOT / "data" / "evidence" / "verified-compatibility.json"
DEFAULT_DATA_DIR = REPO_ROOT / ".zabm"
DEFAULT_PDF_DIR = REPO_ROOT / "pdf-doc"
COMPATIBILITY_CUES = (
    "compatible",
    "compatibility",
    "fit together",
    "use together",
    "used together",
    "work together",
)
PROCEDURE_CUES = (
    "how do i ",
    "how to ",
    "procedure",
    "service steps",
    "steps",
    "walk me through",
)
PROCEDURE_ACTIONS = {
    "adjust",
    "assemble",
    "bleed",
    "disassemble",
    "install",
    "prepare",
    "remove",
    "replace",
}


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
            print(
                f"- {source['id']}: {source['sha256']} "
                f"(retrieved {source['retrieval_date']}, {source['revision']})"
            )
    return 0


def _ingest_command(
    manifest: Path,
    evidence: Path,
    compatibility_evidence: Path,
    pdf_dir: Path,
    data_dir: Path,
    as_json: bool,
) -> int:
    try:
        report = ingest_sources(manifest, evidence, pdf_dir, data_dir)
        compatibility_report = ingest_compatibility(
            manifest,
            compatibility_evidence,
            pdf_dir,
            data_dir,
        )
        retrieval_report = ingest_retrieval(manifest, pdf_dir, data_dir)
    except (OSError, IngestionError, ValueError) as exc:
        print(f"zabm ingest: {exc}", file=sys.stderr)
        return 1

    if as_json:
        combined_report = {
            **report.model_dump(mode="json"),
            "compatibility_rule_count": compatibility_report.compatibility_rule_count,
            "eligible_compatibility_rule_count": (
                compatibility_report.eligible_compatibility_rule_count
            ),
            "retrieval_page_count": retrieval_report.page_count,
            "table_row_count": retrieval_report.table_row_count,
            "warning_count": retrieval_report.warning_count,
            "procedure_count": retrieval_report.procedure_count,
            "eligible_procedure_count": retrieval_report.eligible_procedure_count,
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
            f"{report.source_count} source(s); "
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
        for issue in [
            *report.validation_issues,
            *compatibility_report.validation_issues,
            *retrieval_report.validation_issues,
        ]:
            print(f"- rejected: {issue}", file=sys.stderr)
    return 0


def _render_response(response: CanonicalResponse) -> str:
    if response.status == "not_found":
        assert response.failure is not None
        return f"not_found: {response.failure.message}"

    if response.response_type == "compatibility":
        assert response.compatibility is not None
        compatibility = response.compatibility
        assert compatibility.component_a is not None
        assert compatibility.component_b is not None
        citation = response.citations[0]
        conditions = "; ".join(compatibility.conditions)
        return (
            f"{compatibility.component_a.name} with {compatibility.component_b.name}: "
            f"{compatibility.outcome}\n"
            f"Conditions: {conditions}\n"
            f"Source: {citation.title}, printed page {citation.printed_page}, "
            f"physical page {citation.physical_page}, {citation.section}, "
            f"retrieved {citation.retrieval_date.isoformat()}"
        )

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
        return "\n".join(lines)

    assert response.specification is not None
    specification = response.specification
    citation = response.citations[0]
    conditions = "; ".join(specification.conditions)
    return (
        f"{specification.manufacturer} {specification.model} "
        f"{specification.component} {specification.attribute}: "
        f"{specification.value.display}\n"
        f"Conditions: {conditions}\n"
        f"Source: {citation.title}, printed page {citation.printed_page}, "
        f"physical page {citation.physical_page}, {citation.section}, "
        f"retrieved {citation.retrieval_date.isoformat()}"
    )


def _ask_command(question: str, data_dir: Path, as_json: bool) -> int:
    if _is_compatibility_question(question):
        response = answer_compatibility(question, data_dir)
    elif _is_procedure_question(question):
        response = answer_procedure(question, data_dir)
    else:
        response = answer_specification(question, data_dir)
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


def _is_compatibility_question(question: str) -> bool:
    normalized_question = question.casefold()
    if any(cue in normalized_question for cue in COMPATIBILITY_CUES):
        return True
    return bool(
        re.search(
            r"\b(?:can|could|may|should)\b[^?]*\buse(?:d)?\b[^?]*\bwith\b",
            normalized_question,
        )
    )


def _is_procedure_question(question: str) -> bool:
    normalized_question = question.casefold()
    if any(cue in normalized_question for cue in PROCEDURE_CUES):
        return True
    first_word = normalized_question.strip().split(maxsplit=1)[0].rstrip(".,:;?!")
    return first_word in PROCEDURE_ACTIONS


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
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
            args.json,
        )
    if args.command == "ask":
        return _ask_command(args.question, args.data_dir, args.json)
    if args.command == "evidence":
        return _evidence_command(args.question, args.data_dir, args.json)
    raise AssertionError(f"unhandled command: {args.command}")
