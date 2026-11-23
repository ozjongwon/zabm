from __future__ import annotations

import hashlib
import json
from pathlib import Path

from test_cli_compatibility import download_and_ingest, run_cli, write_fixture_pdf


def _verified_compatibility_rule(
    *,
    rule_id: str,
    outcome: str,
    excerpt: str,
) -> dict[str, object]:
    return {
        "id": rule_id,
        "component_a": {
            "manufacturer": "Test Manufacturer",
            "name": "Trail Post A2 seatpost",
            "aliases": [],
        },
        "component_b": {
            "manufacturer": "Test Manufacturer",
            "name": "Trail Post B1 seatpost",
            "aliases": [],
        },
        "outcome": outcome,
        "conditions": [
            "Seatpost A: Trail Post A2, 31.6 mm",
            "Seatpost B: Trail Post B1, 30.9 mm",
        ],
        "source_id": "test-manual",
        "citation": {
            "printed_page": 17,
            "physical_page": 1,
            "section": "Compatibility table",
        },
        "evidence_excerpts": [excerpt],
        "verification": {
            "status": "human_verified",
            "verified_by": "repository-maintainer",
            "verified_at": "2026-11-23",
        },
    }


def prepare_compatibility_conflict_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, Path]:
    source_path = tmp_path / "manual.pdf"
    compatible_excerpt = (
        "A 31.6 mm Trail Post A2 seatpost is compatible with a 30.9 mm Trail Post B1 seatpost."
    )
    prohibited_excerpt = (
        "Do not use a 31.6 mm Trail Post A2 seatpost with a 30.9 mm Trail Post B1 seatpost."
    )
    write_fixture_pdf(
        source_path,
        [
            "17 Compatibility table",
            compatible_excerpt,
            prohibited_excerpt,
            "Revision C supersedes Revision B for this pairing.",
        ],
    )
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

    manifest_path = tmp_path / "source-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "compatibility-conflict-test-1",
                "sources": [
                    {
                        "id": "test-manual",
                        "title": "Test Bicycle Manual",
                        "manufacturer": "Test Manufacturer",
                        "url": source_path.as_uri(),
                        "sha256": source_hash,
                        "retrieval_date": "2026-11-23",
                        "revision": "Rev C",
                    }
                ],
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
        json.dumps(
            {
                "compatibility_rules": [
                    _verified_compatibility_rule(
                        rule_id="test-a2-b1-compatible",
                        outcome="compatible",
                        excerpt=compatible_excerpt,
                    ),
                    _verified_compatibility_rule(
                        rule_id="test-a2-b1-prohibited",
                        outcome="not_compatible",
                        excerpt=prohibited_excerpt,
                    ),
                ]
            }
        ),
        encoding="utf-8",
    )
    return (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        tmp_path / "data",
    )


def prepare_conflict_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    source_path = tmp_path / "manual.pdf"
    write_fixture_pdf(
        source_path,
        [
            "17 Torque table",
            "Standard Remote: tighten the remote clamp bolt to 2.8-3.4 N*m (25-30 in-lb).",
            "Standard Remote: tighten the remote clamp bolt to 4.0-5.0 N*m (35-45 in-lb).",
            "Revision C supersedes Revision B for this torque.",
            "Revision C is newer.",
            "The 2011 manual gives this torque.",
        ],
    )
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

    manifest_path = tmp_path / "source-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "conflict-test-1",
                "sources": [
                    {
                        "id": "test-manual",
                        "title": "Test Bicycle Manual",
                        "manufacturer": "Test Manufacturer",
                        "url": source_path.as_uri(),
                        "sha256": source_hash,
                        "retrieval_date": "2026-11-23",
                        "revision": "Rev C",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    first = {
        "id": "test-clamp-torque-rev-b",
        "manufacturer": "Test Manufacturer",
        "model": "Trail Post",
        "component": "remote clamp bolt",
        "attribute": "torque",
        "aliases": ["Trail Post remote clamp torque"],
        "value": {
            "minimum": 2.8,
            "maximum": 3.4,
            "unit": "N·m",
            "display": "2.8-3.4 N·m (25-30 in-lb)",
        },
        "conditions": [
            "Remote: Standard Remote",
            "Fastener: remote clamp bolt",
            "Tool: T25 TORX wrench",
        ],
        "source_id": "test-manual",
        "citation": {
            "printed_page": 17,
            "physical_page": 1,
            "section": "Torque table",
        },
        "evidence_excerpts": [
            "Standard Remote: tighten the remote clamp bolt to 2.8-3.4 N*m (25-30 in-lb)."
        ],
        "verification": {
            "status": "human_verified",
            "verified_by": "repository-maintainer",
            "verified_at": "2026-11-23",
        },
    }
    second = {
        **first,
        "id": "test-clamp-torque-rev-c",
        "value": {
            "minimum": 4.0,
            "maximum": 5.0,
            "unit": "N·m",
            "display": "4.0-5.0 N·m (35-45 in-lb)",
        },
        "evidence_excerpts": [
            "Standard Remote: tighten the remote clamp bolt to 4.0-5.0 N*m (35-45 in-lb)."
        ],
    }

    specification_evidence_path = tmp_path / "verified-specifications.json"
    specification_evidence_path.write_text(
        json.dumps({"specifications": [first, second]}),
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
        tmp_path / "data",
    )


def test_cli_reports_unresolved_specification_conflict_with_every_source(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, compatibility_path, data_dir = prepare_conflict_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, compatibility_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "conflicting_evidence"
    assert response["response_type"] == "specification"
    assert response["failure"]["code"] == "conflicting_evidence"
    assert response["claims"] == []
    assert response["specification"] is None
    assert response["conflicts"]["precedence_established"] is False
    assert response["conflicts"]["selected_claim_id"] is None
    assert response["conflicts"]["candidates"] == [
        {
            "claim_id": "test-clamp-torque-rev-b",
            "claim": (
                "Test Manufacturer Trail Post remote clamp bolt torque: 2.8-3.4 N·m (25-30 in-lb)."
            ),
            "evidence_ids": ["test-clamp-torque-rev-b"],
            "excerpts": [
                "Standard Remote: tighten the remote clamp bolt to 2.8-3.4 N*m (25-30 in-lb)."
            ],
            "citations": [
                {
                    "document_id": "test-manual",
                    "title": "Test Bicycle Manual",
                    "manufacturer": "Test Manufacturer",
                    "printed_page": 17,
                    "physical_page": 1,
                    "section": "Torque table",
                    "retrieval_date": "2026-11-23",
                    "source_manifest_version": "conflict-test-1",
                }
            ],
            "selected": False,
        },
        {
            "claim_id": "test-clamp-torque-rev-c",
            "claim": (
                "Test Manufacturer Trail Post remote clamp bolt torque: 4.0-5.0 N·m (35-45 in-lb)."
            ),
            "evidence_ids": ["test-clamp-torque-rev-c"],
            "excerpts": [
                "Standard Remote: tighten the remote clamp bolt to 4.0-5.0 N*m (35-45 in-lb)."
            ],
            "citations": [
                {
                    "document_id": "test-manual",
                    "title": "Test Bicycle Manual",
                    "manufacturer": "Test Manufacturer",
                    "printed_page": 17,
                    "physical_page": 1,
                    "section": "Torque table",
                    "retrieval_date": "2026-11-23",
                    "source_manifest_version": "conflict-test-1",
                }
            ],
            "selected": False,
        },
    ]

    plain_result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
    )

    assert plain_result.returncode == 0, plain_result.stderr
    assert plain_result.stdout.startswith("conflicting_evidence: ")
    assert "2.8-3.4 N·m (25-30 in-lb)" in plain_result.stdout
    assert "4.0-5.0 N·m (35-45 in-lb)" in plain_result.stdout
    assert "Traceback" not in plain_result.stderr


def test_cli_uses_cited_supersession_and_keeps_rejected_evidence_visible(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, compatibility_path, data_dir = prepare_conflict_fixture(tmp_path)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["specifications"][1]["precedence"] = {
        "kind": "supersession",
        "supersedes": ["test-clamp-torque-rev-b"],
        "reason": "Revision C supersedes Revision B for this torque.",
        "source_id": "test-manual",
        "citation": {
            "printed_page": 17,
            "physical_page": 1,
            "section": "Torque table",
        },
        "evidence_excerpts": ["Revision C supersedes Revision B for this torque."],
    }
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    download_and_ingest(manifest_path, evidence_path, compatibility_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["response_type"] == "specification"
    assert response["specification"]["value"] == {
        "minimum": 4.0,
        "maximum": 5.0,
        "unit": "N·m",
        "display": "4.0-5.0 N·m (35-45 in-lb)",
    }
    assert response["claims"] == [
        {
            "claim_id": "test-clamp-torque-rev-c",
            "text": (
                "Test Manufacturer Trail Post remote clamp bolt torque: 4.0-5.0 N·m (35-45 in-lb)."
            ),
            "evidence_ids": ["test-clamp-torque-rev-c"],
        }
    ]
    assert response["conflicts"]["precedence_established"] is True
    assert response["conflicts"]["selected_claim_id"] == "test-clamp-torque-rev-c"
    assert response["conflicts"]["rejected_claim_ids"] == ["test-clamp-torque-rev-b"]
    assert [candidate["selected"] for candidate in response["conflicts"]["candidates"]] == [
        False,
        True,
    ]
    assert response["conflicts"]["candidates"][0]["claim"] == (
        "Test Manufacturer Trail Post remote clamp bolt torque: 2.8-3.4 N·m (25-30 in-lb)."
    )
    assert response["conflicts"]["precedence"] == {
        "kind": "supersession",
        "reason": "Revision C supersedes Revision B for this torque.",
        "supersedes": ["test-clamp-torque-rev-b"],
        "excerpt": "Revision C supersedes Revision B for this torque.",
        "citation": {
            "document_id": "test-manual",
            "title": "Test Bicycle Manual",
            "manufacturer": "Test Manufacturer",
            "printed_page": 17,
            "physical_page": 1,
            "section": "Torque table",
            "retrieval_date": "2026-11-23",
            "source_manifest_version": "conflict-test-1",
        },
    }

    plain_result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
    )

    assert plain_result.returncode == 0, plain_result.stderr
    assert "2.8-3.4 N·m (25-30 in-lb)" in plain_result.stdout
    assert "Revision C supersedes Revision B for this torque." in plain_result.stdout
    assert "Source: Test Bicycle Manual, printed page 17" in plain_result.stdout
    assert "Traceback" not in plain_result.stderr


def test_cli_does_not_use_precedence_with_an_invalid_citation(tmp_path: Path) -> None:
    manifest_path, evidence_path, compatibility_path, data_dir = prepare_conflict_fixture(tmp_path)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["specifications"][1]["precedence"] = {
        "kind": "supersession",
        "supersedes": ["test-clamp-torque-rev-b"],
        "reason": "Revision C supersedes Revision B for this torque.",
        "source_id": "test-manual",
        "citation": {
            "printed_page": 17,
            "physical_page": 1,
            "section": "Missing section",
        },
        "evidence_excerpts": ["Revision C supersedes Revision B for this torque."],
    }
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    download_and_ingest(manifest_path, evidence_path, compatibility_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "conflicting_evidence"
    assert response["conflicts"]["precedence_established"] is False
    assert response["conflicts"]["precedence"] is None
    assert response["claims"] == []


def test_cli_does_not_use_precedence_without_an_explicit_source_statement(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, compatibility_path, data_dir = prepare_conflict_fixture(tmp_path)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["specifications"][1]["precedence"] = {
        "kind": "supersession",
        "supersedes": ["test-clamp-torque-rev-b"],
        "reason": "The newer revision should win.",
        "source_id": "test-manual",
        "citation": {
            "printed_page": 17,
            "physical_page": 1,
            "section": "Torque table",
        },
        "evidence_excerpts": ["Revision C is newer."],
    }
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    download_and_ingest(manifest_path, evidence_path, compatibility_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "conflicting_evidence"
    assert response["conflicts"]["precedence_established"] is False
    assert response["conflicts"]["precedence"] is None
    assert response["claims"] == []


def test_cli_does_not_treat_a_model_year_as_revision_precedence(tmp_path: Path) -> None:
    manifest_path, evidence_path, compatibility_path, data_dir = prepare_conflict_fixture(tmp_path)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload["specifications"][1]["precedence"] = {
        "kind": "revision_date",
        "supersedes": ["test-clamp-torque-rev-b"],
        "reason": "The value comes from the 2011 manual.",
        "source_id": "test-manual",
        "citation": {
            "printed_page": 17,
            "physical_page": 1,
            "section": "Torque table",
        },
        "evidence_excerpts": ["The 2011 manual gives this torque."],
    }
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    download_and_ingest(manifest_path, evidence_path, compatibility_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "conflicting_evidence"
    assert response["conflicts"]["precedence_established"] is False
    assert response["conflicts"]["precedence"] is None
    assert response["claims"] == []


def test_cli_does_not_use_matching_dimensions_to_resolve_compatibility_conflict(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, compatibility_path, data_dir = (
        prepare_compatibility_conflict_fixture(tmp_path)
    )
    download_and_ingest(manifest_path, evidence_path, compatibility_path, data_dir)

    result = run_cli(
        "ask",
        ("Is a 31.6 mm Trail Post A2 seatpost compatible with a 30.9 mm Trail Post B1 seatpost?"),
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "conflicting_evidence"
    assert response["response_type"] == "compatibility"
    assert response["failure"]["code"] == "conflicting_evidence"
    assert response["compatibility"] is None
    assert response["claims"] == []
    assert response["conflicts"]["precedence_established"] is False
    assert response["conflicts"]["selected_claim_id"] is None
    assert [candidate["claim"] for candidate in response["conflicts"]["candidates"]] == [
        "Trail Post A2 seatpost is compatible with Trail Post B1 seatpost.",
        "Trail Post A2 seatpost is not compatible with Trail Post B1 seatpost.",
    ]


def test_cli_applies_cited_compatibility_precedence_without_hiding_rejected_rule(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, compatibility_path, data_dir = (
        prepare_compatibility_conflict_fixture(tmp_path)
    )
    payload = json.loads(compatibility_path.read_text(encoding="utf-8"))
    payload["compatibility_rules"][1]["precedence"] = {
        "kind": "supersession",
        "supersedes": ["test-a2-b1-compatible"],
        "reason": "Revision C supersedes Revision B for this pairing.",
        "source_id": "test-manual",
        "citation": {
            "printed_page": 17,
            "physical_page": 1,
            "section": "Compatibility table",
        },
        "evidence_excerpts": ["Revision C supersedes Revision B for this pairing."],
    }
    compatibility_path.write_text(json.dumps(payload), encoding="utf-8")
    download_and_ingest(manifest_path, evidence_path, compatibility_path, data_dir)

    result = run_cli(
        "ask",
        ("Is a 31.6 mm Trail Post A2 seatpost compatible with a 30.9 mm Trail Post B1 seatpost?"),
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["response_type"] == "compatibility"
    assert response["compatibility"]["outcome"] == "not_compatible"
    assert response["claims"] == [
        {
            "claim_id": "test-a2-b1-prohibited",
            "text": ("Trail Post A2 seatpost is not compatible with Trail Post B1 seatpost."),
            "evidence_ids": ["test-a2-b1-prohibited"],
        }
    ]
    assert response["conflicts"]["precedence_established"] is True
    assert response["conflicts"]["selected_claim_id"] == "test-a2-b1-prohibited"
    assert response["conflicts"]["rejected_claim_ids"] == ["test-a2-b1-compatible"]
    assert response["conflicts"]["candidates"][0]["selected"] is False
    assert response["conflicts"]["candidates"][0]["claim"] == (
        "Trail Post A2 seatpost is compatible with Trail Post B1 seatpost."
    )
    assert response["conflicts"]["candidates"][0]["citations"][0]["printed_page"] == 17
    assert response["conflicts"]["precedence"]["excerpt"] == (
        "Revision C supersedes Revision B for this pairing."
    )
