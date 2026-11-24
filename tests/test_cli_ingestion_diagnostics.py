from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from cross_layout_corpus import (
    CorpusWorkspace,
    ingest_corpus,
    materialize_corpus,
    read_catalog,
)
from test_cli_procedure import run_cli


@pytest.fixture(scope="module")
def ingested_corpus(tmp_path_factory: pytest.TempPathFactory) -> CorpusWorkspace:
    workspace = materialize_corpus(tmp_path_factory.mktemp("ingestion-diagnostics"))
    ingest_corpus(workspace)
    return workspace


def _sources(workspace: CorpusWorkspace) -> list[dict[str, Any]]:
    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    return manifest["sources"]


def _ingest_args(workspace: CorpusWorkspace, *extra: str) -> list[str]:
    return [
        "ingest",
        "--manifest",
        str(workspace.manifest_path),
        "--evidence",
        str(workspace.specification_evidence_path),
        "--compatibility-evidence",
        str(workspace.compatibility_evidence_path),
        "--ingestion-profiles",
        str(workspace.profile_path),
        "--pdf-dir",
        str(workspace.pdf_dir),
        "--data-dir",
        str(workspace.data_dir),
        *extra,
    ]


def test_ingest_report_exposes_bounded_diagnostics_and_complete_provenance(
    ingested_corpus: CorpusWorkspace,
) -> None:
    report, catalog = ingest_corpus(ingested_corpus)
    diagnostics = report["ingestion_diagnostics"]
    pages = diagnostics["pages"]

    assert diagnostics["source_pack_id"] == report["source_pack_id"]
    assert all("text" not in page for page in pages)
    single_column = next(
        page
        for page in pages
        if page["document_id"] == "single-column" and page["physical_page"] == 1
    )
    assert single_column["page_kind"] == "procedure-step"
    assert single_column["columns"]
    assert single_column["languages"]
    assert single_column["headings"]
    assert any(step["decision"] == "accepted" for step in single_column["candidate_steps"])

    rejected_pages = [
        page
        for page in pages
        if any(step["decision"] == "rejected" for step in page["candidate_steps"])
    ]
    assert rejected_pages
    assert all(
        step["reason"]
        for page in rejected_pages
        for step in page["candidate_steps"]
        if step["decision"] == "rejected"
    )

    expected_rejections = Counter(
        candidate["reason"]
        for source in catalog["sources"]
        for page in source["pages"]
        for candidate in page["rejected_step_candidates"]
    )
    assert report["procedure_candidate_counts"]["rejected_by_reason"] == dict(expected_rejections)

    provenance = report["ingestion_provenance"]
    assert provenance["parser_version"] == "pdf-ingestion-v11"
    assert (
        provenance["source_manifest_sha256"]
        == hashlib.sha256(ingested_corpus.manifest_path.read_bytes()).hexdigest()
    )
    assert provenance["fonttools_version"] == "4.68.0"
    assert provenance["pypdf_version"] == "6.21.4"
    assert [
        (source["profile_id"], source["profile_version"], source["profile_sha256"])
        for source in provenance["profiles"]
    ] == [
        (
            source["ingestion_profile"]["profile_id"],
            source["ingestion_profile"]["profile_version"],
            source["ingestion_profile"]["profile_sha256"],
        )
        for source in catalog["sources"]
    ]
    assert {source["document_id"]: source["source_sha256"] for source in catalog["sources"]} == {
        source["id"]: source["sha256"] for source in _sources(ingested_corpus)
    }
    assert set(report["artifact_checksums"]) == {
        "compatibility.json",
        "retrieval.json",
        "specifications.json",
    }
    persisted_report = json.loads(
        (ingested_corpus.data_dir / "generated" / "ingestion-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted_report["ingestion_diagnostics"] == diagnostics
    assert persisted_report["artifact_checksums"] == report["artifact_checksums"]


def test_normal_ingest_reports_candidate_decisions_and_diagnostics_flag(
    ingested_corpus: CorpusWorkspace,
) -> None:
    catalog = read_catalog(ingested_corpus)
    rejection_reason = next(
        candidate["reason"]
        for source in catalog["sources"]
        for page in source["pages"]
        for candidate in page["rejected_step_candidates"]
    )

    result = run_cli(*_ingest_args(ingested_corpus))
    assert result.returncode == 0, result.stderr
    assert "Procedure candidates:" in result.stdout
    assert f"{rejection_reason}=" in result.stdout
    assert "Page classification:" not in result.stdout

    diagnostics = run_cli(*_ingest_args(ingested_corpus, "--diagnostics"))
    assert diagnostics.returncode == 0, diagnostics.stderr
    assert "single-column page 1: procedure-step" in diagnostics.stdout
    assert "columns:" in diagnostics.stdout
    assert "languages: en" in diagnostics.stdout
    assert f"rejected {rejection_reason}:" in diagnostics.stdout


def test_profile_change_requires_review_and_changes_the_retrieval_checksum(
    tmp_path: Path,
) -> None:
    workspace = materialize_corpus(tmp_path)
    initial_report, _ = ingest_corpus(workspace)
    retrieval_path = workspace.data_dir / "generated" / "retrieval.json"
    original_retrieval = retrieval_path.read_bytes()
    original_checksum = initial_report["artifact_checksums"]["retrieval.json"]

    profiles = json.loads(workspace.profile_path.read_text(encoding="utf-8"))
    profiles["profile_manifest_version"] = "cross-layout-profiles-v2"
    workspace.profile_path.write_text(
        json.dumps(profiles, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    blocked = run_cli(*_ingest_args(workspace))
    assert blocked.returncode == 1
    assert "--rebuild-review" in blocked.stderr
    assert "source-pack freeze" in blocked.stderr
    assert "retrieval smoke" in blocked.stderr
    assert "complete evaluation" in blocked.stderr
    assert retrieval_path.read_bytes() == original_retrieval

    reviewed = run_cli(
        *_ingest_args(workspace, "--rebuild-review", "review-2026-11-24-pdf-12"),
        "--json",
    )
    assert reviewed.returncode == 0, reviewed.stderr
    report = json.loads(reviewed.stdout)
    decision = report["rebuild_decision"]
    assert decision["status"] == "reviewed"
    assert decision["review"] == "review-2026-11-24-pdf-12"
    assert "profile_manifest_version" in decision["changed_components"]
    assert decision["previous_retrieval_sha256"] == original_checksum
    assert report["artifact_checksums"]["retrieval.json"] != original_checksum

    unchanged = run_cli(*_ingest_args(workspace, "--json"))
    assert unchanged.returncode == 0, unchanged.stderr
    unchanged_report = json.loads(unchanged.stdout)
    assert unchanged_report["rebuild_decision"]["status"] == "unchanged"
    assert (
        unchanged_report["artifact_checksums"]["retrieval.json"]
        == report["artifact_checksums"]["retrieval.json"]
    )
