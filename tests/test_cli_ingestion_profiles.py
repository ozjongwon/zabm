from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from test_cli_specification import FIXTURE_PDF, run_cli


def prepare_profile_fixture(
    tmp_path: Path,
    *,
    source_metadata: dict[str, str] | None = None,
    profile_reference: dict[str, str] | None = None,
) -> tuple[Path, Path, Path, Path, Path]:
    source_path = tmp_path / "manual.pdf"
    source_path.write_bytes(FIXTURE_PDF)
    source: dict[str, Any] = {
        "id": "test-manual",
        "title": "Test Bicycle Manual",
        "manufacturer": "Test Manufacturer",
        "url": source_path.as_uri(),
        "sha256": hashlib.sha256(FIXTURE_PDF).hexdigest(),
        "retrieval_date": "2026-11-24",
        "revision": "Rev C",
    }
    if source_metadata is not None:
        source["ingestion_metadata"] = source_metadata
    if profile_reference is not None:
        source["ingestion_profile"] = profile_reference

    manifest_path = tmp_path / "source-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "test-profiles-1",
                "sources": [source],
            }
        ),
        encoding="utf-8",
    )
    specification_evidence_path = tmp_path / "verified-specifications.json"
    specification_evidence_path.write_text(
        json.dumps({"specifications": []}),
        encoding="utf-8",
    )
    compatibility_evidence_path = tmp_path / "verified-compatibility.json"
    compatibility_evidence_path.write_text(
        json.dumps({"compatibility_rules": []}),
        encoding="utf-8",
    )
    profile_path = tmp_path / "ingestion-profiles.json"
    profile_path.write_text(json.dumps(profile_manifest()), encoding="utf-8")
    return (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        tmp_path / "data",
    )


def profile_manifest() -> dict[str, Any]:
    return {
        "profile_schema_version": "1",
        "profile_manifest_version": "profiles-v1",
        "profiles": [
            {
                "id": "standard-en",
                "version": "1",
                "selector": {
                    "metadata": {},
                    "fallback": True,
                },
                "page_classification": {"exceptions": []},
                "layout": {
                    "columns": [],
                    "reading_order": "left-to-right",
                },
                "language": {
                    "primary_language": "en",
                    "regions": [],
                },
                "headings": {
                    "rules": [],
                    "infer_hierarchy": True,
                },
                "tables": {"excluded_regions": []},
                "figures": {
                    "excluded_regions": [],
                    "requires_human_transcription": True,
                },
                "end_boundaries": {
                    "strategy": "explicit-marker",
                    "markers": ["This concludes"],
                },
                "action_aliases": {},
            },
            {
                "id": "two-column-en",
                "version": "1",
                "selector": {
                    "metadata": {"layout_family": "two-column"},
                    "fallback": False,
                },
                "page_classification": {"exceptions": []},
                "layout": {
                    "columns": [
                        {"id": "left", "x_min": 0.0, "x_max": 0.5},
                        {"id": "right", "x_min": 0.5, "x_max": 1.0},
                    ],
                    "reading_order": "left-to-right",
                },
                "language": {
                    "primary_language": "en",
                    "regions": [],
                },
                "headings": {
                    "rules": [],
                    "infer_hierarchy": True,
                },
                "tables": {"excluded_regions": []},
                "figures": {
                    "excluded_regions": [],
                    "requires_human_transcription": True,
                },
                "end_boundaries": {
                    "strategy": "explicit-marker",
                    "markers": ["Procedure complete"],
                },
                "action_aliases": {},
            },
        ],
    }


def ingest_with_profiles(
    manifest_path: Path,
    specification_evidence_path: Path,
    compatibility_evidence_path: Path,
    profile_path: Path,
    data_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pdf_dir = data_dir.parent / "pdf-doc"
    download = run_cli(
        "download",
        "--manifest",
        str(manifest_path),
        "--pdf-dir",
        str(pdf_dir),
        "--json",
    )
    assert download.returncode == 0, download.stderr

    ingest = run_cli(
        "ingest",
        "--manifest",
        str(manifest_path),
        "--evidence",
        str(specification_evidence_path),
        "--compatibility-evidence",
        str(compatibility_evidence_path),
        "--ingestion-profiles",
        str(profile_path),
        "--pdf-dir",
        str(pdf_dir),
        "--data-dir",
        str(data_dir),
        "--json",
    )
    assert ingest.returncode == 0, ingest.stderr
    report: dict[str, Any] = json.loads(ingest.stdout)
    catalog: dict[str, Any] = json.loads(
        (data_dir / "generated" / "retrieval.json").read_text(encoding="utf-8")
    )
    return report, catalog


def run_ingest(
    manifest_path: Path,
    specification_evidence_path: Path,
    compatibility_evidence_path: Path,
    profile_path: Path,
    data_dir: Path,
) -> subprocess.CompletedProcess[str]:
    pdf_dir = data_dir.parent / "pdf-doc"
    download = run_cli(
        "download",
        "--manifest",
        str(manifest_path),
        "--pdf-dir",
        str(pdf_dir),
        "--json",
    )
    assert download.returncode == 0, download.stderr
    return run_cli(
        "ingest",
        "--manifest",
        str(manifest_path),
        "--evidence",
        str(specification_evidence_path),
        "--compatibility-evidence",
        str(compatibility_evidence_path),
        "--ingestion-profiles",
        str(profile_path),
        "--pdf-dir",
        str(pdf_dir),
        "--data-dir",
        str(data_dir),
        "--json",
    )


def test_cli_selects_a_document_profile_and_records_retrieval_provenance(
    tmp_path: Path,
) -> None:
    (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    ) = prepare_profile_fixture(
        tmp_path,
        source_metadata={"layout_family": "two-column"},
    )

    report, catalog = ingest_with_profiles(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    )

    profile_manifest_sha256 = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    assert report["ingestion_provenance"]["parser_version"] == "pdf-ingestion-v10"
    assert report["ingestion_provenance"]["profile_manifest_version"] == "profiles-v1"
    assert report["ingestion_provenance"]["profile_manifest_sha256"] == profile_manifest_sha256
    assert catalog["ingestion_provenance"] == report["ingestion_provenance"]
    assignment = catalog["ingestion_provenance"]["profiles"][0]
    assert assignment["document_id"] == "test-manual"
    assert assignment["profile_id"] == "two-column-en"
    assert assignment["profile_version"] == "1"
    assert re.fullmatch(r"[0-9a-f]{64}", assignment["profile_sha256"])
    assert catalog["sources"][0]["ingestion_profile"] == {
        "profile_id": "two-column-en",
        "profile_version": "1",
        "profile_sha256": assignment["profile_sha256"],
    }


def test_cli_explicit_profile_reference_overrides_source_metadata(
    tmp_path: Path,
) -> None:
    (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    ) = prepare_profile_fixture(
        tmp_path,
        source_metadata={"layout_family": "two-column"},
        profile_reference={"id": "standard-en", "version": "1"},
    )

    _, catalog = ingest_with_profiles(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    )

    assert catalog["sources"][0]["ingestion_profile"]["profile_id"] == "standard-en"


def test_cli_rejects_an_unknown_explicit_profile_version_before_writing_evidence(
    tmp_path: Path,
) -> None:
    (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    ) = prepare_profile_fixture(
        tmp_path,
        profile_reference={"id": "standard-en", "version": "2"},
    )

    result = run_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    )

    assert result.returncode == 1
    assert "source test-manual references unsupported ingestion profile version '2'" in (
        result.stderr
    )
    assert "supported versions: 1" in result.stderr
    assert not (data_dir / "generated").exists()


def test_cli_rejects_invalid_profile_overrides_with_an_actionable_error(
    tmp_path: Path,
) -> None:
    (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    ) = prepare_profile_fixture(tmp_path)
    payload = profile_manifest()
    payload["profiles"][1]["layout"]["columns"][1]["x_max"] = 1.2
    profile_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    )

    assert result.returncode == 1
    assert "invalid ingestion profile manifest" in result.stderr
    assert "layout.columns.1.x_max" in result.stderr
    assert "less than or equal to 1" in result.stderr
    assert not (data_dir / "generated").exists()


def test_cli_rejects_unreviewed_section_boundary_completeness(
    tmp_path: Path,
) -> None:
    (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    ) = prepare_profile_fixture(tmp_path)
    payload = profile_manifest()
    payload["profiles"][0]["end_boundaries"]["strategy"] = "section-boundary"
    profile_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    )

    assert result.returncode == 1
    assert "section-boundary strategy requires a maintainer review reference" in result.stderr
    assert not (data_dir / "generated").exists()


def test_cli_rejects_an_action_alias_term_assigned_to_multiple_actions(
    tmp_path: Path,
) -> None:
    (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    ) = prepare_profile_fixture(tmp_path)
    payload = profile_manifest()
    payload["profiles"][0]["action_aliases"] = {
        "install": ["fit"],
        "mount": ["fit"],
    }
    profile_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    )

    assert result.returncode == 1
    assert "action alias term 'fit' is assigned to multiple actions" in result.stderr
    assert not (data_dir / "generated").exists()


def test_cli_records_normalized_action_vocabulary_with_the_selected_profile(
    tmp_path: Path,
) -> None:
    (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    ) = prepare_profile_fixture(tmp_path)
    payload = profile_manifest()
    payload["profiles"][0]["action_aliases"] = {
        "Install": ["FITTING", "mounting"],
    }
    profile_path.write_text(json.dumps(payload), encoding="utf-8")

    _, catalog = ingest_with_profiles(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        profile_path,
        data_dir,
    )

    assert catalog["sources"][0]["procedure_language"] == "en"
    assert catalog["sources"][0]["action_aliases"] == {
        "install": ["fitting", "mounting"],
    }
