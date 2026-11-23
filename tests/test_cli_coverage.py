from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from test_cli_procedure import download_and_ingest, write_fixture_pdf
from test_cli_specification import run_cli


def prepare_coverage_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    manifest_sources: list[dict[str, str]] = []
    specifications: list[dict[str, Any]] = []
    compatibility_rules: list[dict[str, Any]] = []
    for index in range(1, 7):
        source_id = f"test-source-{index}"
        source_path = tmp_path / f"{source_id}.pdf"
        write_fixture_pdf(
            source_path,
            [
                f"17 Trail Post {index} spring service",
                "Part    Tool    Torque",
                "Clamp bolt    T25    5 Nm",
                f"Hose barb {index} is compatible with Trail Post {index} A2.",
                f"50 Hour Service Trail Post {index} spring replacement",
                "NOTICE",
                "Hold the spring under compression.",
                "1 Remove the spring cap.",
                "2 Replace the spring.",
                "3 Install the spring cap.",
                f"This concludes the Trail Post {index} spring replacement procedure.",
            ],
        )
        manifest_sources.append(
            {
                "id": source_id,
                "title": f"Test Bicycle Manual {index}",
                "manufacturer": "Test Manufacturer",
                "url": source_path.as_uri(),
                "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                "retrieval_date": "2026-11-23",
                "revision": f"Rev {index}",
            }
        )
        specifications.append(
            {
                "id": f"verified-clamp-torque-{index}",
                "manufacturer": "Test Manufacturer",
                "model": f"Trail Post {index}",
                "component": "clamp bolt",
                "attribute": "torque",
                "aliases": [],
                "value": {
                    "minimum": 5,
                    "maximum": 5,
                    "unit": "N·m",
                    "display": "5 N·m",
                },
                "conditions": [
                    f"Model: Trail Post {index}",
                    "Fastener: clamp bolt",
                    "Tool: T25",
                ],
                "source_id": source_id,
                "citation": {
                    "printed_page": 17,
                    "physical_page": 1,
                    "section": f"Trail Post {index} spring service",
                },
                "evidence_excerpts": ["Clamp bolt T25 5 Nm"],
                "verification": {
                    "status": "human_verified",
                    "verified_by": "repository-maintainer",
                    "verified_at": "2026-11-23",
                },
            }
        )
        specifications.append(
            {
                "id": f"unverified-ghost-torque-{index}",
                "manufacturer": "Test Manufacturer",
                "model": f"Ghost Post {index}",
                "component": "ghost bolt",
                "attribute": "torque",
                "aliases": [],
                "value": {
                    "minimum": 5,
                    "maximum": 5,
                    "unit": "N·m",
                    "display": "5 N·m",
                },
                "conditions": [
                    f"Model: Ghost Post {index}",
                    "Fastener: ghost bolt",
                    "Tool: T25",
                ],
                "source_id": source_id,
                "citation": {
                    "printed_page": 17,
                    "physical_page": 1,
                    "section": f"Trail Post {index} spring service",
                },
                "evidence_excerpts": ["Clamp bolt T25 5 Nm"],
                "verification": {
                    "status": "proposed",
                    "verified_by": "",
                    "verified_at": None,
                },
            }
        )
        compatibility_rules.append(
            {
                "id": f"verified-barb-{index}",
                "component_a": {
                    "manufacturer": "Test Manufacturer",
                    "name": f"Hose barb {index}",
                    "aliases": [],
                },
                "component_b": {
                    "manufacturer": "Test Manufacturer",
                    "name": f"Trail Post {index} A2 seatpost",
                    "aliases": [],
                },
                "outcome": "compatible",
                "conditions": [
                    f"Seatpost: Trail Post {index} A2",
                    "Connection: hose barb",
                ],
                "source_id": source_id,
                "citation": {
                    "printed_page": 17,
                    "physical_page": 1,
                    "section": f"Trail Post {index} spring service",
                },
                "evidence_excerpts": [
                    f"Hose barb {index} is compatible with Trail Post {index} A2."
                ],
                "verification": {
                    "status": "human_verified",
                    "verified_by": "repository-maintainer",
                    "verified_at": "2026-11-23",
                },
            }
        )

    manifest_path = tmp_path / "source-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "test-coverage-1",
                "sources": manifest_sources,
            }
        ),
        encoding="utf-8",
    )
    specification_evidence_path = tmp_path / "verified-specifications.json"
    specification_evidence_path.write_text(
        json.dumps({"specifications": specifications}),
        encoding="utf-8",
    )
    compatibility_evidence_path = tmp_path / "verified-compatibility.json"
    compatibility_evidence_path.write_text(
        json.dumps({"compatibility_rules": compatibility_rules}),
        encoding="utf-8",
    )
    return (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        tmp_path / "data",
    )


def write_coverage_fixture(tmp_path: Path) -> Path:
    cases: list[dict[str, Any]] = []
    for index in range(1, 7):
        source_id = f"test-source-{index}"
        cases.append(
            {
                "id": f"accepted-specification-{index}",
                "source_id": source_id,
                "evidence_type": "specification",
                "question": f"What is the Trail Post {index} clamp bolt torque?",
                "expected": {
                    "response_type": "specification",
                    "status": "supported",
                    "claim_ids": [f"verified-clamp-torque-{index}"],
                    "citations": [{"document_id": source_id, "physical_page": 1}],
                },
            }
        )
        cases.append(
            {
                "id": f"rejected-unverified-specification-{index}",
                "source_id": source_id,
                "evidence_type": "specification",
                "question": f"What is the Ghost Post {index} ghost bolt torque?",
                "expected": {
                    "response_type": "specification",
                    "status": "not_found",
                    "failure_contains": "human verification is missing",
                },
            }
        )

    cases.extend(
        [
            {
                "id": "accepted-compatibility",
                "source_id": "test-source-1",
                "evidence_type": "compatibility",
                "question": "Is hose barb 1 compatible with the Trail Post 1 A2 seatpost?",
                "expected": {
                    "response_type": "compatibility",
                    "status": "supported",
                    "claim_ids": ["verified-barb-1"],
                    "citations": [{"document_id": "test-source-1", "physical_page": 1}],
                    "compatibility_outcome": "compatible",
                },
            },
            {
                "id": "accepted-procedure",
                "source_id": "test-source-1",
                "evidence_type": "procedure",
                "question": "What are the steps for Trail Post 1 spring replacement?",
                "expected": {
                    "response_type": "procedure",
                    "status": "supported",
                    "claim_ids": [
                        ("test-source-1#trail-post-1-spring-replacement-p1#step-1"),
                        ("test-source-1#trail-post-1-spring-replacement-p1#step-1-warning-1"),
                        ("test-source-1#trail-post-1-spring-replacement-p1#step-2"),
                        ("test-source-1#trail-post-1-spring-replacement-p1#step-3"),
                    ],
                    "citations": [{"document_id": "test-source-1", "physical_page": 1}],
                },
            },
        ]
    )
    coverage_set_path = tmp_path / "coverage-set.json"
    coverage_set_path.write_text(
        json.dumps(
            {
                "coverage_set_id": "test-coverage-set-v1",
                "cases": cases,
                "unanswerable_content": [
                    {
                        "id": "figure-only-tool-marking",
                        "source_id": "test-source-2",
                        "evidence_type": "specification",
                        "physical_page": 1,
                        "question": "What is the Ghost Figure 2 friction paste torque?",
                        "reason": (
                            "Figure-only tool markings have no human transcription "
                            "with an exact citation."
                        ),
                        "expected_failure_contains": (
                            "No human-verified structured evidence matches"
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return coverage_set_path


def test_cli_reports_verified_coverage_for_every_frozen_document(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_coverage_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )
    coverage_set_path = write_coverage_fixture(tmp_path)

    result = run_cli(
        "coverage",
        "--manifest",
        str(manifest_path),
        "--coverage-set",
        str(coverage_set_path),
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report: dict[str, Any] = json.loads(result.stdout)
    assert report["coverage_set_id"] == "test-coverage-set-v1"
    assert report["source_pack_id"] == "test-coverage-1"
    assert report["passed"] is True
    assert len(report["sources"]) == 6
    assert all(source["accepted_case_count"] >= 1 for source in report["sources"])
    assert all(source["rejected_case_count"] >= 1 for source in report["sources"])
    assert all(source["unanswerable_count"] >= 1 for source in report["sources"])
    assert all(result["passed"] for result in report["case_results"])
    assert report["unanswerable_content"][0]["reason"] == (
        "Figure-only tool markings have no human transcription with an exact citation."
    )


def test_cli_fails_when_a_frozen_document_has_no_accepted_coverage_case(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_coverage_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )
    coverage_set_path = write_coverage_fixture(tmp_path)
    coverage_set: dict[str, Any] = json.loads(coverage_set_path.read_text(encoding="utf-8"))
    coverage_set["cases"] = [
        case for case in coverage_set["cases"] if case["id"] != "accepted-specification-6"
    ]
    coverage_set_path.write_text(json.dumps(coverage_set), encoding="utf-8")

    result = run_cli(
        "coverage",
        "--manifest",
        str(manifest_path),
        "--coverage-set",
        str(coverage_set_path),
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 1
    report: dict[str, Any] = json.loads(result.stdout)
    assert report["passed"] is False
    assert report["issues"] == ["source test-source-6 has no accepted CLI coverage case"]


def test_cli_rejects_generated_evidence_from_a_different_source_pack(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_coverage_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )
    coverage_set_path = write_coverage_fixture(tmp_path)
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["manifest_version"] = "test-coverage-2"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_cli(
        "coverage",
        "--manifest",
        str(manifest_path),
        "--coverage-set",
        str(coverage_set_path),
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 1
    report: dict[str, Any] = json.loads(result.stdout)
    assert report["passed"] is False
    assert "specification evidence source-pack ID does not match the manifest" in report["issues"]
    assert "compatibility evidence source-pack ID does not match the manifest" in report["issues"]
    assert "retrieval evidence source-pack ID does not match the manifest" in report["issues"]
