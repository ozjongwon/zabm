from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import socket
import sys
import time
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pypdf._configuration import overwrite_configuration

from zabm import __version__
from zabm.acceptance import (
    build_acceptance_report,
    load_cpu_smoke_evidence,
    load_evaluation_artifact,
    write_acceptance_report,
)
from zabm.agent import answer_question
from zabm.compatibility import ingest_compatibility
from zabm.coverage import run_coverage
from zabm.evaluation import (
    RuntimeIdentity,
    detect_hardware,
    run_evaluation,
    write_evaluation_artifact,
)
from zabm.evaluation_set import (
    build_evaluation_report,
    create_evaluation_freeze,
    load_evaluation_set,
    validate_evaluation_set,
    verify_evaluation_freeze,
)
from zabm.ingestion import (
    DEFAULT_INGESTION_PROFILES,
    IngestionProfileError,
    load_ingestion_profiles,
    resolve_document_profile,
)
from zabm.procedures import (
    ProcedureEvidenceInspection,
    RetrievalIngestReport,
    assess_ingestion_rebuild,
    ingest_retrieval,
    inspect_procedure_evidence,
)
from zabm.providers import PROVIDER_NAMES, ProviderError, configured_provider
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
    write_json,
)
from zabm.web import ZabmHTTPServer

PINNED_PYTHON = "3.13.5"
PINNED_DEPENDENCIES = {"pydantic": "2.14.3", "pypdf": "6.21.4"}
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "data" / "manifests" / "source-pack-v1.json"
DEFAULT_EVIDENCE = REPO_ROOT / "data" / "evidence" / "verified-specifications.json"
DEFAULT_COMPATIBILITY_EVIDENCE = REPO_ROOT / "data" / "evidence" / "verified-compatibility.json"
DEFAULT_TRANSCRIPTIONS = REPO_ROOT / "data" / "evidence" / "verified-transcriptions.json"
DEFAULT_SMOKE_SET = REPO_ROOT / "data" / "retrieval-smoke" / "smoke-set-v1.json"
DEFAULT_RETRIEVAL_CONFIG = REPO_ROOT / "data" / "retrieval-smoke" / "retrieval-config-v1.json"
DEFAULT_SMOKE_REPORT = REPO_ROOT / "data" / "retrieval-smoke" / "report-v1.json"
DEFAULT_SOURCE_FREEZE = REPO_ROOT / "data" / "manifests" / "source-pack-freeze-v1.json"
DEFAULT_COVERAGE_SET = REPO_ROOT / "data" / "coverage" / "coverage-v1.json"
DEFAULT_EVALUATION_SET = REPO_ROOT / "data" / "evaluation" / "evaluation-set-v1.json"
DEFAULT_EVALUATION_FREEZE = REPO_ROOT / "data" / "evaluation" / "evaluation-freeze-v1.json"
DEFAULT_BASELINE_CONFIG = REPO_ROOT / "data" / "evaluation" / "baseline-config-v1.json"
DEFAULT_EVALUATION_RESULTS = REPO_ROOT / "data" / "evaluation" / "baseline-results-v1.json"
DEFAULT_ACCEPTANCE_REPORT = REPO_ROOT / "data" / "evaluation" / "acceptance-report-v1.json"
DEFAULT_DATA_DIR = REPO_ROOT / ".zabm"
DEFAULT_PDF_DIR = REPO_ROOT / "pdf-doc"
DEBUG_LOG_FORMAT = "%(levelname)s %(name)s %(message)s"


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


def _debug_enabled_by_default() -> bool:
    return os.getenv("ZABM_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _configure_debug_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format=DEBUG_LOG_FORMAT,
        stream=sys.stderr,
        force=True,
    )
    logging.getLogger("zabm").setLevel(logging.DEBUG if debug else logging.WARNING)


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
    ingestion_profiles_path: Path,
    transcriptions_path: Path,
    language: str | None,
    diagnostics: bool,
    rebuild_review: str | None,
    as_json: bool,
) -> int:
    try:
        ingestion_profiles = load_ingestion_profiles(ingestion_profiles_path)
        source_manifest = load_source_manifest(manifest)
        for source in source_manifest.sources:
            resolve_document_profile(
                ingestion_profiles,
                source_id=source.id,
                metadata=source.ingestion_metadata,
                reference=source.ingestion_profile,
            )
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
        assess_ingestion_rebuild(
            manifest,
            ingestion_profiles_path,
            data_dir,
            ingestion_profiles=ingestion_profiles,
            transcriptions_path=transcriptions_path,
            review=rebuild_review,
        )
        report = ingest_sources(manifest, evidence, pdf_dir, data_dir)
        compatibility_report = ingest_compatibility(
            manifest,
            compatibility_evidence,
            pdf_dir,
            data_dir,
        )
        retrieval_report = ingest_retrieval(
            manifest,
            pdf_dir,
            data_dir,
            ingestion_profiles_path,
            ingestion_profiles=ingestion_profiles,
            transcriptions_path=transcriptions_path,
            requested_language=language,
            rebuild_review=rebuild_review,
        )
    except (
        OSError,
        FrozenSourcePackError,
        IngestionError,
        IngestionProfileError,
        ValueError,
    ) as exc:
        print(f"zabm ingest: {exc}", file=sys.stderr)
        return 1

    artifact_paths = {
        "specifications.json": data_dir / "generated" / "specifications.json",
        "compatibility.json": data_dir / "generated" / "compatibility.json",
        "retrieval.json": data_dir / "generated" / "retrieval.json",
    }
    artifact_checksums = {name: file_sha256(path) for name, path in artifact_paths.items()}
    combined_report = {
        **report.model_dump(mode="json"),
        "compatibility_rule_count": compatibility_report.compatibility_rule_count,
        "eligible_compatibility_rule_count": (
            compatibility_report.eligible_compatibility_rule_count
        ),
        "retrieval_page_count": retrieval_report.page_count,
        "ingestion_provenance": retrieval_report.ingestion_provenance.model_dump(mode="json"),
        "page_alignment": retrieval_report.page_alignment.model_dump(mode="json"),
        "table_row_count": retrieval_report.table_row_count,
        "warning_count": retrieval_report.warning_count,
        "procedure_count": retrieval_report.procedure_count,
        "eligible_procedure_count": retrieval_report.eligible_procedure_count,
        "verified_transcription_count": retrieval_report.verified_transcription_count,
        "transcription_required_pages": [
            page.model_dump(mode="json") for page in retrieval_report.transcription_required_pages
        ],
        "ingestion_diagnostics": retrieval_report.ingestion_diagnostics.model_dump(mode="json"),
        "procedure_candidate_counts": (
            retrieval_report.procedure_candidate_counts.model_dump(mode="json")
        ),
        "rebuild_decision": retrieval_report.rebuild_decision.model_dump(mode="json"),
        "artifact_checksums": artifact_checksums,
        "validation_issues": [
            *report.validation_issues,
            *compatibility_report.validation_issues,
            *retrieval_report.validation_issues,
        ],
    }
    write_json(data_dir / "generated" / "ingestion-report.json", combined_report)
    if as_json:
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
        candidate_counts = retrieval_report.procedure_candidate_counts
        print(
            f"Procedure candidates: {candidate_counts.accepted_steps} accepted, "
            f"{candidate_counts.rejected_steps} rejected."
        )
        if candidate_counts.rejected_by_reason:
            reasons = ", ".join(
                f"{reason}={count}" for reason, count in candidate_counts.rejected_by_reason.items()
            )
            print(f"Procedure candidate rejections: {reasons}")
        rebuild_decision = retrieval_report.rebuild_decision
        decision = rebuild_decision.status
        if rebuild_decision.review:
            decision = f"{decision} ({rebuild_decision.review})"
        print(f"Ingestion rebuild: {decision}.")
        for action in rebuild_decision.required_actions:
            print(f"- required after parser/profile rebuild: {action}")
        if diagnostics:
            _render_ingestion_diagnostics(retrieval_report)
        for name, checksum in artifact_checksums.items():
            print(f"- {name}: sha256 {checksum}")
        for issue in [
            *report.validation_issues,
            *compatibility_report.validation_issues,
            *retrieval_report.validation_issues,
        ]:
            print(f"- rejected: {issue}", file=sys.stderr)
    return 0


def _render_ingestion_diagnostics(report: RetrievalIngestReport) -> None:
    print("Page classification:")
    for page in report.ingestion_diagnostics.pages:
        certainty = "uncertain" if page.classification_uncertain else "classified"
        print(
            f"- {page.document_id} page {page.physical_page}: {page.page_kind} "
            f"({certainty}, {page.classification_confidence:.2f}, "
            f"{page.ingestion_outcome})"
        )
        columns = ", ".join(
            f"{column.id}[{column.x_min:.2f}-{column.x_max:.2f}]" for column in page.columns
        )
        print(f"  columns: {columns or 'none'}")
        print(f"  languages: {', '.join(page.languages) or 'none'}")
        if page.classification_uncertainty:
            print(f"  classification note: {page.classification_uncertainty}")
        if page.ingestion_outcome_reason:
            print(f"  outcome reason: {page.ingestion_outcome_reason}")
        for heading in page.headings:
            print(f"  heading: {' > '.join(heading.heading_path)}")
        for step in page.candidate_steps:
            if step.decision == "accepted":
                print(f"  accepted step: {step.text}")
            else:
                print(f"  rejected {step.reason}: {step.text}")


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


def _provider_smoke_command(
    as_json: bool,
    output_path: Path | None,
    cpu_quantized: bool,
    skip_embeddings: bool,
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
        if model_provider is None:
            raise ProviderError(
                "provider-smoke requires a model provider; "
                "select openai-compatible, openai, or deepseek"
            )
        started = time.perf_counter()
        response = model_provider.complete(
            [{"role": "user", "content": "Reply with OK."}],
            seed=0,
        )
        chat_latency_ms = (time.perf_counter() - started) * 1000
        vectors: list[list[float]] = []
        embedding_latency_ms = 0.0
        if not skip_embeddings:
            started = time.perf_counter()
            vectors = model_provider.embed(["bicycle clamp bolt torque"])
            embedding_latency_ms = (time.perf_counter() - started) * 1000
            if not vectors or not vectors[0]:
                raise ProviderError("provider returned no embedding vector")
    except ProviderError as exc:
        print(f"zabm provider-smoke: {exc}", file=sys.stderr)
        return 1

    chat_result = {
        "response_characters": len(response),
        "latency_ms": round(chat_latency_ms, 3),
    }
    embedding_result: dict[str, object]
    if skip_embeddings:
        embedding_result = {"status": "skipped"}
    else:
        embedding_result = {
            "input_count": 1,
            "vector_count": len(vectors),
            "dimensions": len(vectors[0]),
            "latency_ms": round(embedding_latency_ms, 3),
        }
    report: dict[str, object] = {
        "provider": model_provider.identity.model_dump(mode="json"),
        "chat": chat_result,
        "embeddings": embedding_result,
    }
    if cpu_quantized:
        report = {
            "artifact_version": "cpu-smoke-v1",
            "status": "passed",
            "provider": model_provider.identity.model_dump(mode="json"),
            "hardware": detect_hardware().model_dump(mode="json"),
            "runtime": RuntimeIdentity(
                application="zabm",
                application_version=__version__,
                python_version=platform.python_version(),
                python_implementation=platform.python_implementation(),
            ).model_dump(mode="json"),
            "latency_ms": round(chat_latency_ms + embedding_latency_ms, 3),
            "chat": chat_result,
            "embeddings": embedding_result,
        }
    if output_path is not None:
        write_json(output_path, report)
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        identity = model_provider.identity
        if skip_embeddings:
            print(
                f"Provider smoke passed: {identity.provider}/{identity.model}; embeddings skipped."
            )
        else:
            print(
                f"Provider smoke passed: {identity.provider}/{identity.model}, "
                f"embedding {identity.embedding_model} ({len(vectors[0])} dimensions)."
            )
    return 0


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


def _web_command(
    host: str,
    port: int,
    data_dir: Path,
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
        server = ZabmHTTPServer((host, port), data_dir, model_provider)
    except (OSError, ProviderError) as exc:
        print(f"zabm web: {exc}", file=sys.stderr)
        return 1

    address = server.server_address
    raw_host = address[0]
    server_host = raw_host.decode() if isinstance(raw_host, bytes | bytearray) else raw_host
    server_port = address[1]
    urls = _web_urls(server_host, server_port)
    print(
        f"zabm web: {urls[0]} (data: {data_dir}; press Ctrl+C to stop)",
        flush=True,
    )
    for url in urls[1:]:
        print(f"zabm web: {url} (local network)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nzabm web: stopped", file=sys.stderr)
    finally:
        server.server_close()
    return 0


def _web_urls(server_host: str, server_port: int) -> tuple[str, ...]:
    if server_host not in {"0.0.0.0", "::"}:
        display_host = f"[{server_host}]" if ":" in server_host else server_host
        return (f"http://{display_host}:{server_port}",)

    urls = [f"http://127.0.0.1:{server_port}"]
    urls.extend(f"http://{host}:{server_port}" for host in _local_ipv4_addresses())
    return tuple(urls)


def _local_ipv4_addresses() -> tuple[str, ...]:
    addresses: set[str] = set()
    try:
        for result in socket.getaddrinfo(
            socket.gethostname(),
            None,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        ):
            host = result[4][0]
            if not isinstance(host, str):
                continue
            if not host.startswith("127."):
                addresses.add(host)
    except OSError:
        pass
    if addresses:
        return tuple(sorted(addresses))

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            host = probe.getsockname()[0]
            if not host.startswith("127."):
                return (host,)
    except OSError:
        pass
    return ()


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
    replace_freeze: bool,
    maintainer_review: str | None,
    candidate_audit: Path | None,
    as_json: bool,
) -> int:
    try:
        if replace_freeze and freeze_path is None:
            raise ValueError("--replace-freeze requires --freeze")
        source_freeze = freeze_path
        if (
            source_freeze is None
            and manifest.resolve() == DEFAULT_MANIFEST.resolve()
            and report_path.resolve() == DEFAULT_SMOKE_REPORT.resolve()
            and DEFAULT_SOURCE_FREEZE.is_file()
        ):
            source_freeze = DEFAULT_SOURCE_FREEZE
        if not replace_freeze and source_freeze is not None and source_freeze.is_file():
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


def _evaluation_command(
    evaluation_set_path: Path,
    baseline_config_path: Path,
    retrieval_config_path: Path,
    manifest_path: Path,
    pdf_dir: Path,
    data_dir: Path,
    output_path: Path,
    evaluation_freeze_path: Path | None,
    source_freeze_path: Path | None,
    as_json: bool,
    *,
    provider: str | None,
    provider_url: str | None,
    model: str | None,
    embedding_model: str | None,
    provider_configuration: str | None,
) -> int:
    try:
        effective_evaluation_freeze = evaluation_freeze_path
        if (
            effective_evaluation_freeze is None
            and evaluation_set_path.resolve() == DEFAULT_EVALUATION_SET.resolve()
        ):
            effective_evaluation_freeze = DEFAULT_EVALUATION_FREEZE
        if effective_evaluation_freeze is not None and effective_evaluation_freeze.is_file():
            verify_evaluation_freeze(
                effective_evaluation_freeze,
                evaluation_set_path,
                manifest_path,
                source_freeze_path or DEFAULT_SOURCE_FREEZE,
            )
        effective_source_freeze = source_freeze_path
        if (
            effective_source_freeze is None
            and manifest_path.resolve() == DEFAULT_MANIFEST.resolve()
        ):
            effective_source_freeze = DEFAULT_SOURCE_FREEZE
        if effective_source_freeze is not None and effective_source_freeze.is_file():
            verify_frozen_source_pack(effective_source_freeze, manifest_path)
        model_provider = configured_provider(
            provider=provider,
            base_url=provider_url,
            model=model,
            embedding_model=embedding_model,
            configuration=provider_configuration,
        )
        report = run_evaluation(
            evaluation_set_path=evaluation_set_path,
            baseline_config_path=baseline_config_path,
            retrieval_config_path=retrieval_config_path,
            manifest_path=manifest_path,
            pdf_dir=pdf_dir,
            data_dir=data_dir,
            provider=model_provider,
        )
        write_evaluation_artifact(report, output_path)
    except (OSError, ProviderError, ValueError) as exc:
        print(f"zabm evaluation: {exc}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        print(
            f"Evaluation {report.evaluation_set_id} completed with "
            f"{len(report.configurations)} configuration(s)."
        )
        for result in report.configurations:
            spread = result.spread.accuracy
            print(
                f"- {result.id}: accuracy median {spread.median:.1%} "
                f"(range {spread.minimum:.1%}-{spread.maximum:.1%})"
            )
        print(f"Results: {output_path}")
    return 0


def _acceptance_command(
    results_path: Path,
    output_path: Path,
    execution_environment: Literal["local-gpu", "local-cpu-quantized"],
    cpu_smoke_report_path: Path | None,
    bootstrap_seed: int,
    bootstrap_resamples: int,
    as_json: bool,
) -> int:
    try:
        evaluation = load_evaluation_artifact(results_path)
        cpu_performance = (
            load_cpu_smoke_evidence(cpu_smoke_report_path)
            if cpu_smoke_report_path is not None
            else None
        )
        report = build_acceptance_report(
            evaluation_path=results_path,
            evaluation=evaluation,
            execution_environment=execution_environment,
            cpu_performance=cpu_performance,
            bootstrap_seed=bootstrap_seed,
            bootstrap_resamples=bootstrap_resamples,
        )
        write_acceptance_report(report, output_path)
    except (OSError, ValueError) as exc:
        print(f"zabm acceptance: {exc}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        print(f"Acceptance {report.status} for {report.evaluation.evaluation_set_id}.")
        for gate in report.gates:
            print(f"- {gate.id}: {gate.status} ({gate.diagnosis})")
        print(f"Report: {output_path}")
    return 0 if report.status == "passed" else 1


def _add_provider_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        choices=PROVIDER_NAMES,
        default=os.getenv("ZABM_PROVIDER"),
        help="Provider profile: deterministic, openai-compatible, openai, or deepseek.",
    )
    parser.add_argument(
        "--provider-url",
        default=os.getenv("ZABM_PROVIDER_URL"),
        help="Override the provider base URL, including /v1 when required.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("ZABM_MODEL"),
        help="Chat model identifier; defaults depend on the provider profile.",
    )
    parser.add_argument(
        "--embedding-model",
        default=os.getenv("ZABM_EMBEDDING_MODEL"),
        help="Embedding model identifier; defaults depend on the provider profile.",
    )
    parser.add_argument(
        "--provider-configuration",
        default=os.getenv("ZABM_PROVIDER_CONFIGURATION"),
        help="Stable provider configuration identifier recorded with results.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=_debug_enabled_by_default(),
        help="Log model, routing, and retrieval interactions to stderr.",
    )


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
    ingest.add_argument(
        "--ingestion-profiles",
        type=Path,
        default=DEFAULT_INGESTION_PROFILES,
        help="Path to the versioned PDF-ingestion profile manifest.",
    )
    ingest.add_argument(
        "--transcriptions",
        type=Path,
        default=DEFAULT_TRANSCRIPTIONS,
        help="Path to the human-verified procedure transcription artifact.",
    )
    ingest.add_argument(
        "--language",
        help="Preferred extracted language code; defaults to each profile's primary language.",
    )
    ingest.add_argument(
        "--rebuild-review",
        help=(
            "Stable review reference required when parser, profile, or dependency "
            "provenance changes."
        ),
    )
    ingest.add_argument(
        "--diagnostics",
        action="store_true",
        help="Print page classifications, layout, headings, and candidate-step decisions.",
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
    _add_provider_arguments(ask)
    ask.add_argument("--json", action="store_true", help="Emit the canonical response.")

    provider_smoke = commands.add_parser(
        "provider-smoke",
        help="Exercise the configured chat and embedding provider endpoints.",
    )
    _add_provider_arguments(provider_smoke)
    provider_smoke.add_argument(
        "--cpu-quantized",
        action="store_true",
        help="Write CPU-quantized acceptance evidence for the smoke result.",
    )
    provider_smoke.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Check chat without calling an embedding endpoint.",
    )
    provider_smoke.add_argument(
        "--output",
        type=Path,
        help="Optional path for the provider-smoke JSON report.",
    )
    provider_smoke.add_argument("--json", action="store_true", help="Emit a JSON report.")

    web = commands.add_parser(
        "web",
        help="Serve the local web chat for bicycle maintenance questions.",
    )
    web.add_argument(
        "--host",
        default="0.0.0.0",
        help="Interface to bind; defaults to all network interfaces.",
    )
    web.add_argument(
        "--port",
        type=int,
        default=8765,
        help="TCP port to bind; use 0 to select an available port.",
    )
    web.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory for generated evidence.",
    )
    _add_provider_arguments(web)

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

    evaluation = commands.add_parser(
        "evaluation",
        help="Run the four-configuration baseline ladder and write canonical local results.",
    )
    evaluation.add_argument(
        "--evaluation-set",
        type=Path,
        default=DEFAULT_EVALUATION_SET,
        help="Path to the frozen evaluation set or a deterministic fixture set.",
    )
    evaluation.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_BASELINE_CONFIG,
        help="Path to the frozen baseline-ladder configuration.",
    )
    evaluation.add_argument(
        "--retrieval-config",
        type=Path,
        default=DEFAULT_RETRIEVAL_CONFIG,
        help="Path to the frozen retrieval configuration.",
    )
    evaluation.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the frozen source manifest.",
    )
    evaluation.add_argument(
        "--pdf-dir",
        type=Path,
        default=DEFAULT_PDF_DIR,
        help="Directory containing the frozen source PDFs.",
    )
    evaluation.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing generated evidence.",
    )
    evaluation.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_EVALUATION_RESULTS,
        help="Canonical local JSON artifact for every baseline and run.",
    )
    evaluation.add_argument(
        "--evaluation-freeze",
        type=Path,
        help="Evaluation-set freeze to verify; defaults for the frozen scored set.",
    )
    evaluation.add_argument(
        "--source-freeze",
        type=Path,
        help="Source-pack freeze to verify; defaults for the default source manifest.",
    )
    _add_provider_arguments(evaluation)
    evaluation.add_argument(
        "--json",
        action="store_true",
        help="Emit the canonical evaluation artifact.",
    )

    acceptance = commands.add_parser(
        "acceptance",
        help="Score v1 acceptance gates from a canonical evaluation artifact.",
    )
    acceptance.add_argument(
        "--results",
        type=Path,
        default=DEFAULT_EVALUATION_RESULTS,
        help="Canonical evaluation artifact containing every baseline and run.",
    )
    acceptance.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_ACCEPTANCE_REPORT,
        help="Path for the scored acceptance report.",
    )
    acceptance.add_argument(
        "--execution-environment",
        choices=("local-gpu", "local-cpu-quantized"),
        required=True,
        help="Recorded execution target used for performance gates.",
    )
    acceptance.add_argument(
        "--cpu-smoke-report",
        type=Path,
        help="Successful CPU-quantized smoke report for the documented performance gate.",
    )
    acceptance.add_argument(
        "--bootstrap-seed",
        type=int,
        default=20_261_124,
        help="Fixed seed for item-paired bootstrap resampling.",
    )
    acceptance.add_argument(
        "--bootstrap-resamples",
        type=int,
        default=10_000,
        help="Number of item-paired bootstrap resamples.",
    )
    acceptance.add_argument(
        "--json",
        action="store_true",
        help="Emit the scored acceptance report.",
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
        "--replace-freeze",
        action="store_true",
        help="Replace an existing freeze after an explicitly reviewed smoke rerun.",
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
    overwrite_configuration(stream_parsing_work_maximum_count=20_000_000)
    args = _parser().parse_args(argv)
    _configure_debug_logging(getattr(args, "debug", False))
    logging.getLogger("pypdf").setLevel(logging.ERROR)
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
            args.ingestion_profiles,
            args.transcriptions,
            args.language,
            args.diagnostics,
            args.rebuild_review,
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
    if args.command == "provider-smoke":
        return _provider_smoke_command(
            args.json,
            args.output,
            args.cpu_quantized,
            args.skip_embeddings,
            provider=args.provider,
            provider_url=args.provider_url,
            model=args.model,
            embedding_model=args.embedding_model,
            provider_configuration=args.provider_configuration,
        )
    if args.command == "web":
        return _web_command(
            args.host,
            args.port,
            args.data_dir,
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
    if args.command == "evaluation":
        return _evaluation_command(
            args.evaluation_set,
            args.config,
            args.retrieval_config,
            args.manifest,
            args.pdf_dir,
            args.data_dir,
            args.output,
            args.evaluation_freeze,
            args.source_freeze,
            args.json,
            provider=args.provider,
            provider_url=args.provider_url,
            model=args.model,
            embedding_model=args.embedding_model,
            provider_configuration=args.provider_configuration,
        )
    if args.command == "acceptance":
        return _acceptance_command(
            args.results,
            args.output,
            args.execution_environment,
            args.cpu_smoke_report,
            args.bootstrap_seed,
            args.bootstrap_resamples,
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
            args.replace_freeze,
            args.maintainer_review,
            args.candidate_audit,
            args.json,
        )
    raise AssertionError(f"unhandled command: {args.command}")
