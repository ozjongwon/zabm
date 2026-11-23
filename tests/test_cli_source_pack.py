from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from test_cli_specification import FIXTURE_PDF, run_cli

REPO_ROOT = Path(__file__).resolve().parents[1]


def prepare_multi_source_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path, Path]:
    source_specs = [
        ("test-source-1", "Test Manufacturer A", "Rev A"),
        ("test-source-2", "Test Manufacturer A", "Rev B"),
        ("test-source-3", "Test Manufacturer B", "2026"),
        ("test-source-4", "Test Manufacturer B", "Rev C"),
    ]
    source_records: list[dict[str, str]] = []
    for index, (source_id, manufacturer, revision) in enumerate(source_specs, start=1):
        source_path = tmp_path / f"source-{index}.pdf"
        source_path.write_bytes(FIXTURE_PDF)
        source_records.append(
            {
                "id": source_id,
                "title": f"Test Manual {index}",
                "manufacturer": manufacturer,
                "url": source_path.as_uri(),
                "sha256": hashlib.sha256(FIXTURE_PDF).hexdigest(),
                "retrieval_date": "2026-11-23",
                "revision": revision,
            }
        )

    manifest_path = tmp_path / "source-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "test-multi-1",
                "sources": source_records,
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
    return (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        tmp_path / "pdf-doc",
        tmp_path / "data",
    )


def download_sources(
    manifest_path: Path,
    pdf_dir: Path,
) -> dict[str, Any]:
    result = run_cli(
        "download",
        "--manifest",
        str(manifest_path),
        "--pdf-dir",
        str(pdf_dir),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    report: dict[str, Any] = json.loads(result.stdout)
    return report


def ingest_sources(
    manifest_path: Path,
    specification_evidence_path: Path,
    compatibility_evidence_path: Path,
    pdf_dir: Path,
    data_dir: Path,
) -> dict[str, Any]:
    result = run_cli(
        "ingest",
        "--manifest",
        str(manifest_path),
        "--evidence",
        str(specification_evidence_path),
        "--compatibility-evidence",
        str(compatibility_evidence_path),
        "--pdf-dir",
        str(pdf_dir),
        "--data-dir",
        str(data_dir),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    report: dict[str, Any] = json.loads(result.stdout)
    return report


def test_cli_builds_a_clean_multi_manufacturer_candidate_pack(
    tmp_path: Path,
) -> None:
    (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        pdf_dir,
        data_dir,
    ) = prepare_multi_source_fixture(tmp_path)
    assert not pdf_dir.exists()
    assert not data_dir.exists()

    download_report = download_sources(manifest_path, pdf_dir)
    ingest_report = ingest_sources(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        pdf_dir,
        data_dir,
    )

    assert download_report["source_pack_id"] == "test-multi-1"
    assert download_report["source_count"] == 4
    assert download_report["manufacturer_count"] == 2
    assert [source["manufacturer"] for source in download_report["sources"]] == [
        "Test Manufacturer A",
        "Test Manufacturer A",
        "Test Manufacturer B",
        "Test Manufacturer B",
    ]
    assert all(Path(source["path"]).is_file() for source in download_report["sources"])
    assert all(source["url"].startswith("file:") for source in download_report["sources"])

    assert ingest_report["source_pack_id"] == "test-multi-1"
    assert ingest_report["source_count"] == 4
    assert ingest_report["manufacturer_count"] == 2
    assert ingest_report["page_alignment"] == {
        "document_count": 4,
        "physical_page_count": 4,
        "parsed_page_count": 4,
        "text_page_count": 4,
        "missing_text_pages": [],
    }
    assert set(ingest_report["artifact_checksums"]) == {
        "compatibility.json",
        "retrieval.json",
        "specifications.json",
    }
    assert all(
        re.fullmatch(r"[0-9a-f]{64}", checksum)
        for checksum in ingest_report["artifact_checksums"].values()
    )


def test_cli_rejects_a_changed_source_before_writing_evidence(tmp_path: Path) -> None:
    (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        pdf_dir,
        data_dir,
    ) = prepare_multi_source_fixture(tmp_path)
    download_sources(manifest_path, pdf_dir)
    changed_source = pdf_dir / "test-source-2.pdf"
    changed_source.write_bytes(changed_source.read_bytes() + b"\nchanged\n")

    result = run_cli(
        "ingest",
        "--manifest",
        str(manifest_path),
        "--evidence",
        str(specification_evidence_path),
        "--compatibility-evidence",
        str(compatibility_evidence_path),
        "--pdf-dir",
        str(pdf_dir),
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode != 0
    assert "test-source-2 does not match the manifest hash" in result.stderr
    assert not (data_dir / "generated").exists()


def test_cli_download_rejects_a_manifest_hash_mismatch(tmp_path: Path) -> None:
    (
        manifest_path,
        _,
        _,
        pdf_dir,
        data_dir,
    ) = prepare_multi_source_fixture(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["sources"][1]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_cli(
        "download",
        "--manifest",
        str(manifest_path),
        "--pdf-dir",
        str(pdf_dir),
        "--json",
    )

    assert result.returncode != 0
    assert "test-source-2 hash mismatch" in result.stderr
    assert not (pdf_dir / "test-source-2.pdf").exists()
    assert not (data_dir / "generated").exists()


def test_cli_rebuilds_the_same_canonical_artifacts_from_clean_state(
    tmp_path: Path,
) -> None:
    (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        _,
        _,
    ) = prepare_multi_source_fixture(tmp_path)
    first_pdf_dir = tmp_path / "first-pdf-doc"
    first_data_dir = tmp_path / "first-data"
    second_pdf_dir = tmp_path / "second-pdf-doc"
    second_data_dir = tmp_path / "second-data"

    first_download = download_sources(manifest_path, first_pdf_dir)
    first_ingest = ingest_sources(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        first_pdf_dir,
        first_data_dir,
    )
    second_download = download_sources(manifest_path, second_pdf_dir)
    second_ingest = ingest_sources(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        second_pdf_dir,
        second_data_dir,
    )

    assert [(source["id"], source["sha256"]) for source in first_download["sources"]] == [
        (source["id"], source["sha256"]) for source in second_download["sources"]
    ]
    assert first_ingest["artifact_checksums"] == second_ingest["artifact_checksums"]
    for artifact_name in first_ingest["artifact_checksums"]:
        assert (first_data_dir / "generated" / artifact_name).read_bytes() == (
            second_data_dir / "generated" / artifact_name
        ).read_bytes()


def test_documented_build_wrappers_are_executable_and_forward_cli_arguments() -> None:
    for script, command in (
        ("download-sources.sh", "download"),
        ("ingest-sources.sh", "ingest"),
    ):
        result = subprocess.run(
            [str(REPO_ROOT / "scripts" / script), "--help"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert f"zabm {command}" in result.stdout
