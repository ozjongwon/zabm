from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from test_cli_specification import FIXTURE_PDF, run_cli


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def prepare_freeze_fixture(
    tmp_path: Path,
    *,
    source_count: int = 1,
) -> tuple[Path, Path, Path]:
    sources: list[dict[str, str]] = []
    for index in range(1, source_count + 1):
        source_path = tmp_path / f"source-{index}.pdf"
        source_path.write_bytes(FIXTURE_PDF)
        sources.append(
            {
                "id": f"test-manual-{index}",
                "title": f"Test Bicycle Manual {index}",
                "manufacturer": "Test Manufacturer",
                "url": source_path.as_uri(),
                "sha256": hashlib.sha256(FIXTURE_PDF).hexdigest(),
                "retrieval_date": "2026-11-23",
                "revision": "Rev C",
            }
        )

    manifest_path = tmp_path / "source-manifest.json"
    write_json(
        manifest_path,
        {
            "manifest_version": "test-frozen-1",
            "sources": sources,
        },
    )
    pdf_dir = tmp_path / "pdf-doc"
    data_dir = tmp_path / "data"
    download = run_cli(
        "download",
        "--manifest",
        str(manifest_path),
        "--pdf-dir",
        str(pdf_dir),
        "--json",
    )
    assert download.returncode == 0, download.stderr

    specification_evidence_path = tmp_path / "verified-specifications.json"
    write_json(specification_evidence_path, {"specifications": []})
    compatibility_evidence_path = tmp_path / "verified-compatibility.json"
    write_json(compatibility_evidence_path, {"compatibility_rules": []})
    ingest = run_cli(
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
    assert ingest.returncode == 0, ingest.stderr
    return manifest_path, data_dir, tmp_path


def write_retrieval_smoke_fixture(
    tmp_path: Path,
    *,
    expected_source_id: str = "test-manual-1",
) -> tuple[Path, Path]:
    smoke_set_path = tmp_path / "retrieval-smoke-set.json"
    write_json(
        smoke_set_path,
        {
            "smoke_set_id": "test-retrieval-smoke-v1",
            "items": [
                {
                    "id": "specification-clamp-torque",
                    "evidence_type": "specification",
                    "query": "Torque table clamp bolt",
                    "expected_evidence": [
                        {
                            "source_id": expected_source_id,
                            "physical_pages": [1],
                        }
                    ],
                },
                {
                    "id": "compatibility-remote",
                    "evidence_type": "compatibility",
                    "query": "Standard Remote clamp bolt compatible",
                    "expected_evidence": [
                        {
                            "source_id": expected_source_id,
                            "physical_pages": [1],
                        }
                    ],
                },
                {
                    "id": "procedure-torque",
                    "evidence_type": "procedure",
                    "query": "Install Standard Remote clamp bolt",
                    "expected_evidence": [
                        {
                            "source_id": expected_source_id,
                            "physical_pages": [1],
                        }
                    ],
                },
            ],
        },
    )
    retrieval_config_path = tmp_path / "retrieval-config.json"
    write_json(
        retrieval_config_path,
        {
            "configuration_id": "test-lexical-v1",
            "top_k": 5,
            "required_recall_at_5": 0.85,
            "minimum_passing_paths": 1,
            "paths": [
                {
                    "id": "page-bm25",
                    "kind": "bm25",
                    "k1": 1.2,
                    "b": 0.75,
                    "title_boost": 2.0,
                    "section_boost": 2.0,
                }
            ],
        },
    )
    return smoke_set_path, retrieval_config_path


def test_cli_freezes_a_passing_retrieval_only_smoke_run(tmp_path: Path) -> None:
    manifest_path, data_dir, _ = prepare_freeze_fixture(tmp_path)
    smoke_set_path, retrieval_config_path = write_retrieval_smoke_fixture(tmp_path)
    report_path = tmp_path / "retrieval-smoke-report.json"
    freeze_path = tmp_path / "source-freeze.json"

    result = run_cli(
        "retrieval-smoke",
        "--manifest",
        str(manifest_path),
        "--smoke-set",
        str(smoke_set_path),
        "--retrieval-config",
        str(retrieval_config_path),
        "--data-dir",
        str(data_dir),
        "--report",
        str(report_path),
        "--freeze",
        str(freeze_path),
        "--maintainer-review",
        "ticket-08-test-review",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report: dict[str, Any] = json.loads(result.stdout)
    assert report["evaluation_mode"] == "retrieval-only"
    assert report["source_pack_id"] == "test-frozen-1"
    assert {item["evidence_type"] for item in report["item_results"]} == {
        "specification",
        "compatibility",
        "procedure",
    }
    path_result = report["path_results"][0]
    assert path_result["path_id"] == "page-bm25"
    assert path_result["recall_at_5"] == 1.0
    assert path_result["passed"] is True
    assert report["threshold_decision"] == {
        "required_recall_at_5": 0.85,
        "minimum_passing_paths": 1,
        "passing_paths": ["page-bm25"],
        "passed": True,
    }
    assert json.loads(report_path.read_text(encoding="utf-8")) == report

    freeze: dict[str, Any] = json.loads(freeze_path.read_text(encoding="utf-8"))
    assert freeze["manifest_version"] == "test-frozen-1"
    assert (
        freeze["source_pack_manifest_sha256"]
        == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    )
    assert freeze["smoke_set_sha256"] == hashlib.sha256(smoke_set_path.read_bytes()).hexdigest()
    assert (
        freeze["retrieval_config_sha256"]
        == hashlib.sha256(retrieval_config_path.read_bytes()).hexdigest()
    )
    assert (
        freeze["retrieval_smoke_report_sha256"]
        == hashlib.sha256(report_path.read_bytes()).hexdigest()
    )
    assert freeze["threshold_decision"] == report["threshold_decision"]
    assert freeze["maintainer_review"] == "ticket-08-test-review"
    assert freeze["update_policy"] == {
        "requires_explicit_manifest_change": True,
        "requires_maintainer_review": True,
        "requires_complete_evaluation_rerun": True,
    }


def test_cli_records_and_enforces_the_recall_threshold(tmp_path: Path) -> None:
    manifest_path, data_dir, _ = prepare_freeze_fixture(tmp_path, source_count=6)
    smoke_set_path, retrieval_config_path = write_retrieval_smoke_fixture(
        tmp_path,
        expected_source_id="test-manual-6",
    )
    report_path = tmp_path / "retrieval-smoke-report.json"
    freeze_path = tmp_path / "source-freeze.json"

    result = run_cli(
        "retrieval-smoke",
        "--manifest",
        str(manifest_path),
        "--smoke-set",
        str(smoke_set_path),
        "--retrieval-config",
        str(retrieval_config_path),
        "--data-dir",
        str(data_dir),
        "--report",
        str(report_path),
        "--freeze",
        str(freeze_path),
        "--maintainer-review",
        "ticket-08-test-review",
        "--json",
    )

    assert result.returncode == 1
    assert "no retrieval path met the required Recall@5 threshold" in result.stderr
    report: dict[str, Any] = json.loads(result.stdout)
    path_result = report["path_results"][0]
    assert path_result["hit_count"] == 0
    assert path_result["recall_at_5"] == 0.0
    assert path_result["passed"] is False
    assert report["threshold_decision"] == {
        "required_recall_at_5": 0.85,
        "minimum_passing_paths": 1,
        "passing_paths": [],
        "passed": False,
    }
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert not freeze_path.exists()


def test_cli_rejects_an_unreviewed_change_to_a_frozen_source_pack(tmp_path: Path) -> None:
    manifest_path, data_dir, _ = prepare_freeze_fixture(tmp_path)
    smoke_set_path, retrieval_config_path = write_retrieval_smoke_fixture(tmp_path)
    report_path = tmp_path / "retrieval-smoke-report.json"
    freeze_path = tmp_path / "source-freeze.json"
    freeze_result = run_cli(
        "retrieval-smoke",
        "--manifest",
        str(manifest_path),
        "--smoke-set",
        str(smoke_set_path),
        "--retrieval-config",
        str(retrieval_config_path),
        "--data-dir",
        str(data_dir),
        "--report",
        str(report_path),
        "--freeze",
        str(freeze_path),
        "--maintainer-review",
        "ticket-08-test-review",
        "--json",
    )
    assert freeze_result.returncode == 0, freeze_result.stderr
    frozen_bytes = freeze_path.read_bytes()
    frozen_report_bytes = report_path.read_bytes()

    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"][0]["revision"] = "Rev D"
    write_json(manifest_path, manifest)

    result = run_cli(
        "retrieval-smoke",
        "--manifest",
        str(manifest_path),
        "--smoke-set",
        str(smoke_set_path),
        "--retrieval-config",
        str(retrieval_config_path),
        "--data-dir",
        str(data_dir),
        "--report",
        str(report_path),
        "--freeze",
        str(freeze_path),
        "--maintainer-review",
        "ticket-08-test-review",
        "--json",
    )

    assert result.returncode == 1
    assert "source updates require" in result.stderr
    assert "complete evaluation rerun" in result.stderr
    assert freeze_path.read_bytes() == frozen_bytes
    assert report_path.read_bytes() == frozen_report_bytes


def test_cli_rejects_a_smoke_set_that_misses_an_evidence_family(tmp_path: Path) -> None:
    manifest_path, data_dir, _ = prepare_freeze_fixture(tmp_path)
    smoke_set_path, retrieval_config_path = write_retrieval_smoke_fixture(tmp_path)
    smoke_set: dict[str, Any] = json.loads(smoke_set_path.read_text(encoding="utf-8"))
    smoke_set["items"] = [
        item for item in smoke_set["items"] if item["evidence_type"] != "procedure"
    ]
    write_json(smoke_set_path, smoke_set)

    result = run_cli(
        "retrieval-smoke",
        "--manifest",
        str(manifest_path),
        "--smoke-set",
        str(smoke_set_path),
        "--retrieval-config",
        str(retrieval_config_path),
        "--data-dir",
        str(data_dir),
        "--report",
        str(tmp_path / "report.json"),
        "--json",
    )

    assert result.returncode == 1
    assert "must cover specification, compatibility, and procedure evidence" in result.stderr


def test_ingest_rejects_an_unreviewed_change_to_a_frozen_pack(tmp_path: Path) -> None:
    manifest_path, data_dir, _ = prepare_freeze_fixture(tmp_path)
    smoke_set_path, retrieval_config_path = write_retrieval_smoke_fixture(tmp_path)
    report_path = tmp_path / "retrieval-smoke-report.json"
    freeze_path = tmp_path / "source-freeze.json"
    freeze_result = run_cli(
        "retrieval-smoke",
        "--manifest",
        str(manifest_path),
        "--smoke-set",
        str(smoke_set_path),
        "--retrieval-config",
        str(retrieval_config_path),
        "--data-dir",
        str(data_dir),
        "--report",
        str(report_path),
        "--freeze",
        str(freeze_path),
        "--maintainer-review",
        "ticket-08-test-review",
        "--json",
    )
    assert freeze_result.returncode == 0, freeze_result.stderr
    generated_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (data_dir / "generated").iterdir()
    }
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"][0]["revision"] = "Rev D"
    write_json(manifest_path, manifest)

    result = run_cli(
        "ingest",
        "--manifest",
        str(manifest_path),
        "--evidence",
        str(tmp_path / "verified-specifications.json"),
        "--compatibility-evidence",
        str(tmp_path / "verified-compatibility.json"),
        "--pdf-dir",
        str(tmp_path / "pdf-doc"),
        "--data-dir",
        str(data_dir),
        "--freeze",
        str(freeze_path),
        "--json",
    )

    assert result.returncode == 1
    assert "source updates require" in result.stderr
    assert {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (data_dir / "generated").iterdir()
    } == generated_hashes


def test_freeze_binds_the_candidate_audit_to_the_pack(tmp_path: Path) -> None:
    manifest_path, data_dir, _ = prepare_freeze_fixture(tmp_path)
    smoke_set_path, retrieval_config_path = write_retrieval_smoke_fixture(tmp_path)
    candidate_audit_path = tmp_path / "candidate-audit.json"
    write_json(
        candidate_audit_path,
        {
            "audit_id": "test-audit-v1",
            "candidates": [
                {
                    "source_id": "test-manual-1",
                    "decision": {
                        "included": True,
                        "reasons": ["Public first-party source passed extraction review."],
                    },
                }
            ],
        },
    )
    report_path = tmp_path / "retrieval-smoke-report.json"
    freeze_path = tmp_path / "source-freeze.json"
    result = run_cli(
        "retrieval-smoke",
        "--manifest",
        str(manifest_path),
        "--smoke-set",
        str(smoke_set_path),
        "--retrieval-config",
        str(retrieval_config_path),
        "--candidate-audit",
        str(candidate_audit_path),
        "--data-dir",
        str(data_dir),
        "--report",
        str(report_path),
        "--freeze",
        str(freeze_path),
        "--maintainer-review",
        "ticket-08-test-review",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    freeze: dict[str, Any] = json.loads(freeze_path.read_text(encoding="utf-8"))
    assert freeze["candidate_audit_path"] == str(candidate_audit_path)
    assert (
        freeze["candidate_audit_sha256"]
        == hashlib.sha256(candidate_audit_path.read_bytes()).hexdigest()
    )

    candidate_audit_path.write_text(
        candidate_audit_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    ingest = run_cli(
        "ingest",
        "--manifest",
        str(manifest_path),
        "--evidence",
        str(tmp_path / "verified-specifications.json"),
        "--compatibility-evidence",
        str(tmp_path / "verified-compatibility.json"),
        "--pdf-dir",
        str(tmp_path / "pdf-doc"),
        "--data-dir",
        str(data_dir),
        "--freeze",
        str(freeze_path),
        "--json",
    )
    assert ingest.returncode == 1
    assert "candidate audit differs from the frozen source pack" in ingest.stderr
