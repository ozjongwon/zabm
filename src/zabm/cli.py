from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from zabm import __version__
from zabm.specifications import (
    CanonicalResponse,
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
DEFAULT_DATA_DIR = REPO_ROOT / ".zabm"


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


def _download_command(manifest: Path, data_dir: Path, as_json: bool) -> int:
    try:
        report = download_sources(manifest, data_dir)
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
    data_dir: Path,
    as_json: bool,
) -> int:
    try:
        report = ingest_sources(manifest, evidence, data_dir)
    except (OSError, IngestionError, ValueError) as exc:
        print(f"zabm ingest: {exc}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        print(
            f"Ingested {report.specification_count} specification(s) from "
            f"{report.source_count} source(s); "
            f"{report.eligible_specification_count} eligible."
        )
        for issue in report.validation_issues:
            print(f"- rejected: {issue}", file=sys.stderr)
    return 0


def _render_response(response: CanonicalResponse) -> str:
    if response.status == "not_found":
        assert response.failure is not None
        return f"not_found: {response.failure.message}"

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
    response = answer_specification(question, data_dir)
    if as_json:
        print(json.dumps(response.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        print(_render_response(response))
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
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory for downloaded sources and generated evidence.",
    )
    download.add_argument("--json", action="store_true", help="Emit a JSON report.")

    ingest = commands.add_parser(
        "ingest",
        help="Validate sources and build the structured evidence store.",
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
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory for downloaded sources and generated evidence.",
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
        help="Directory for downloaded sources and generated evidence.",
    )
    ask.add_argument("--json", action="store_true", help="Emit the canonical response.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "health":
        return _health_command(args.json)
    if args.command == "download":
        return _download_command(args.manifest, args.data_dir, args.json)
    if args.command == "ingest":
        return _ingest_command(args.manifest, args.evidence, args.data_dir, args.json)
    if args.command == "ask":
        return _ask_command(args.question, args.data_dir, args.json)
    raise AssertionError(f"unhandled command: {args.command}")
