from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from test_cli_specification import provider_server

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, "-m", "zabm", *args],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def write_fixture_pdf(path: Path, lines: list[str]) -> None:
    commands = [f"({_pdf_escape(line)}) Tj 0 -18 Td" for line in lines]
    stream = f"BT /F1 10 Tf 72 720 Td {' '.join(commands)} ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        (
            b"<< /Type /Page /Parent 2 0 R "
            b"/Resources << /Font << /F1 4 0 R >> >> "
            b"/MediaBox [0 0 612 792] /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    ]

    document = bytearray(b"%PDF-1.3\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode())
        document.extend(body)
        document.extend(b"\nendobj\n")

    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    path.write_bytes(document)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def prepare_compatibility_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    source_path = tmp_path / "manual.pdf"
    write_fixture_pdf(
        source_path,
        [
            "17 Compatibility table",
            "Hose barb with barb sleeve is compatible with Trail Post A2 and B1.",
            (
                "Do not use syringes exposed to DOT brake fluid with the "
                "Trail Post hydraulic system."
            ),
            (
                "Compatibility of the Trail Post 1x Remote with an unspecified "
                "third-party brake lever remains unresolved."
            ),
            "31.6 mm matches 31.6 mm.",
            "Seatpost and seat tube diameters must be the same.",
        ],
    )
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

    manifest_path = tmp_path / "source-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "test-1",
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
                    {
                        "id": "test-barb-trail-post-a2",
                        "component_a": {
                            "manufacturer": "Test Manufacturer",
                            "name": "hose barb with barb sleeve",
                            "aliases": ["hose barb and sleeve"],
                        },
                        "component_b": {
                            "manufacturer": "Test Manufacturer",
                            "name": "Trail Post A2 or B1 seatpost",
                            "aliases": [
                                "Trail Post A2 seatpost",
                                "Trail Post B1 seatpost",
                            ],
                        },
                        "outcome": "compatible",
                        "conditions": [
                            "Connection: hose barb with barb sleeve",
                            "Seatpost: Trail Post A2 or B1",
                        ],
                        "source_id": "test-manual",
                        "citation": {
                            "printed_page": 17,
                            "physical_page": 1,
                            "section": "Compatibility table",
                        },
                        "evidence_excerpts": [
                            ("Hose barb with barb sleeve is compatible with Trail Post A2 and B1.")
                        ],
                        "verification": {
                            "status": "human_verified",
                            "verified_by": "repository-maintainer",
                            "verified_at": "2026-11-23",
                        },
                    },
                    {
                        "id": "test-dot-syringe-trail-post",
                        "component_a": {
                            "manufacturer": "Test Manufacturer",
                            "name": "Trail Post hydraulic system",
                            "aliases": ["Trail Post remote hydraulic system"],
                        },
                        "component_b": {
                            "manufacturer": "Test Manufacturer",
                            "name": "syringe exposed to DOT brake fluid",
                            "aliases": ["DOT-contaminated syringe"],
                        },
                        "outcome": "not_compatible",
                        "conditions": [
                            "Fluid: DOT brake fluid",
                            "Component: syringe used with the Trail Post hydraulic system",
                        ],
                        "source_id": "test-manual",
                        "citation": {
                            "printed_page": 17,
                            "physical_page": 1,
                            "section": "Compatibility table",
                        },
                        "evidence_excerpts": [
                            (
                                "Do not use syringes exposed to DOT brake fluid with "
                                "the Trail Post hydraulic system."
                            )
                        ],
                        "verification": {
                            "status": "human_verified",
                            "verified_by": "repository-maintainer",
                            "verified_at": "2026-11-23",
                        },
                    },
                    {
                        "id": "test-trail-post-1x-third-party-brake",
                        "component_a": {
                            "manufacturer": "Test Manufacturer",
                            "name": "Trail Post 1x Remote",
                            "aliases": [],
                        },
                        "component_b": {
                            "manufacturer": "Unspecified",
                            "name": "third-party brake lever",
                            "aliases": [],
                        },
                        "outcome": "unknown",
                        "conditions": ["Brake lever: third-party, unspecified model"],
                        "source_id": "test-manual",
                        "citation": {
                            "printed_page": 17,
                            "physical_page": 1,
                            "section": "Compatibility table",
                        },
                        "evidence_excerpts": [
                            (
                                "Compatibility of the Trail Post 1x Remote with an "
                                "unspecified third-party brake lever remains unresolved."
                            )
                        ],
                        "verification": {
                            "status": "human_verified",
                            "verified_by": "repository-maintainer",
                            "verified_at": "2026-11-23",
                        },
                    },
                    {
                        "id": "test-trail-post-mismatched-seat-tube",
                        "component_a": {
                            "manufacturer": "Test Manufacturer",
                            "name": "Trail Post A2 seatpost",
                            "aliases": ["30.9 mm Trail Post A2 seatpost"],
                        },
                        "component_b": {
                            "manufacturer": "Test Manufacturer",
                            "name": "seat tube with a different diameter",
                            "aliases": ["31.6 mm seat tube"],
                        },
                        "outcome": "not_compatible",
                        "conditions": [
                            "Seatpost diameter: 30.9 mm, 31.6 mm, or 34.9 mm",
                            "Seat tube diameter: must equal seatpost diameter",
                        ],
                        "source_id": "test-manual",
                        "citation": {
                            "printed_page": 17,
                            "physical_page": 1,
                            "section": "Compatibility table",
                        },
                        "evidence_excerpts": [
                            "Seatpost and seat tube diameters must be the same."
                        ],
                        "verification": {
                            "status": "human_verified",
                            "verified_by": "repository-maintainer",
                            "verified_at": "2026-11-23",
                        },
                    },
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


def download_and_ingest(
    manifest_path: Path,
    specification_evidence_path: Path,
    compatibility_evidence_path: Path,
    data_dir: Path,
) -> None:
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
        "--pdf-dir",
        str(pdf_dir),
        "--data-dir",
        str(data_dir),
        "--json",
    )
    assert ingest.returncode == 0, ingest.stderr


def update_compatibility_rule(
    evidence_path: Path,
    *,
    rule_updates: dict[str, Any] | None = None,
    citation_updates: dict[str, Any] | None = None,
) -> None:
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    rule = payload["compatibility_rules"][0]
    if rule_updates:
        rule.update(rule_updates)
    if citation_updates:
        rule["citation"].update(citation_updates)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")


def test_cli_returns_compatible_for_an_explicit_manufacturer_rule(tmp_path: Path) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Is the hose barb with barb sleeve compatible with the Trail Post A2 seatpost?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["response_type"] == "compatibility"
    assert response["compatibility"] == {
        "outcome": "compatible",
        "component_a": {
            "manufacturer": "Test Manufacturer",
            "name": "hose barb with barb sleeve",
            "aliases": ["hose barb and sleeve"],
        },
        "component_b": {
            "manufacturer": "Test Manufacturer",
            "name": "Trail Post A2 or B1 seatpost",
            "aliases": ["Trail Post A2 seatpost", "Trail Post B1 seatpost"],
        },
        "conditions": [
            "Connection: hose barb with barb sleeve",
            "Seatpost: Trail Post A2 or B1",
        ],
    }
    assert response["claims"] == [
        {
            "claim_id": "test-barb-trail-post-a2",
            "text": ("hose barb with barb sleeve is compatible with Trail Post A2 or B1 seatpost."),
            "evidence_ids": ["test-barb-trail-post-a2"],
        }
    ]
    assert response["citations"] == [
        {
            "document_id": "test-manual",
            "title": "Test Bicycle Manual",
            "manufacturer": "Test Manufacturer",
            "printed_page": 17,
            "physical_page": 1,
            "section": "Compatibility table",
            "retrieval_date": "2026-11-23",
            "source_manifest_version": "test-1",
        }
    ]


def test_cli_returns_not_compatible_for_an_explicit_equal_diameter_requirement(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Is a 30.9 mm Trail Post A2 seatpost compatible with a 31.6 mm seat tube?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["compatibility"]["outcome"] == "not_compatible"
    assert response["compatibility"]["conditions"] == [
        "Seatpost diameter: 30.9 mm, 31.6 mm, or 34.9 mm",
        "Seat tube diameter: must equal seatpost diameter",
    ]
    assert response["claims"][0]["claim_id"] == "test-trail-post-mismatched-seat-tube"


def test_cli_uses_the_local_provider_for_compatibility_phrasing(tmp_path: Path) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )
    generated = {
        "sentences": [
            {
                "claim_id": "test-barb-trail-post-a2",
                "text": (
                    "The hose barb with barb sleeve is compatible with the "
                    "Trail Post A2 or B1 seatpost."
                ),
            }
        ]
    }

    with provider_server(generated) as (provider_url, requests):
        result = run_cli(
            "ask",
            "Is the hose barb with barb sleeve compatible with the Trail Post A2 seatpost?",
            "--data-dir",
            str(data_dir),
            "--provider-url",
            provider_url,
            "--model",
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["compatibility"]["outcome"] == "compatible"
    assert response["provider"]["provider"] == "openai-compatible"
    assert response["claims"][0]["text"].endswith("Trail Post A2 or B1 seatpost.")
    assert len(requests) == 2


def test_cli_returns_not_compatible_for_an_explicit_manufacturer_prohibition(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        (
            "Is a syringe exposed to DOT brake fluid compatible with the "
            "Trail Post hydraulic system?"
        ),
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["response_type"] == "compatibility"
    assert response["compatibility"]["outcome"] == "not_compatible"
    assert response["claims"] == [
        {
            "claim_id": "test-dot-syringe-trail-post",
            "text": (
                "Trail Post hydraulic system is not compatible with "
                "syringe exposed to DOT brake fluid."
            ),
            "evidence_ids": ["test-dot-syringe-trail-post"],
        }
    ]
    assert response["citations"][0]["printed_page"] == 17


def test_cli_routes_use_with_questions_to_compatibility(tmp_path: Path) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Can I use the hose barb with barb sleeve with the Trail Post A2 seatpost?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["response_type"] == "compatibility"
    assert response["compatibility"]["outcome"] == "compatible"


def test_cli_matches_a_compatibility_question_with_a_passive_verb(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Can the hose barb and sleeve be used with the Trail Post B1 seatpost?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["compatibility"]["outcome"] == "compatible"


def test_cli_routes_a_compatibility_paraphrase_by_meaning(tmp_path: Path) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )
    route = {
        "intent": "compatibility",
        "normalized_question": (
            "Is the hose barb with barb sleeve compatible with the Trail Post A2 seatpost?"
        ),
        "entities": [
            {"kind": "component_a", "text": "hose barb with barb sleeve"},
            {"kind": "component_b", "text": "Trail Post A2 seatpost"},
        ],
        "missing_fields": [],
        "ambiguous_fields": [],
        "candidate_intents": [],
    }
    generated = {
        "sentences": [
            {
                "claim_id": "test-barb-trail-post-a2",
                "text": (
                    "The hose barb with barb sleeve is compatible with the "
                    "Trail Post A2 or B1 seatpost."
                ),
            }
        ]
    }

    with provider_server(generated, route_response=route) as (provider_url, requests):
        result = run_cli(
            "ask",
            "Would the barb and sleeve be a safe pairing for the Trail Post A2 post?",
            "--data-dir",
            str(data_dir),
            "--provider",
            "openai-compatible",
            "--provider-url",
            provider_url,
            "--model",
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["response_type"] == "compatibility"
    assert response["compatibility"]["outcome"] == "compatible"
    assert response["routing"]["normalized_question"] == route["normalized_question"]
    assert len(requests) == 2


def test_cli_returns_cited_unknown_when_evidence_leaves_the_pair_unresolved(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        ("Is the Trail Post 1x Remote compatible with an unspecified third-party brake lever?"),
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["response_type"] == "compatibility"
    assert response["compatibility"]["outcome"] == "unknown"
    assert response["claims"] == [
        {
            "claim_id": "test-trail-post-1x-third-party-brake",
            "text": (
                "Trail Post 1x Remote compatibility with third-party brake lever is unresolved."
            ),
            "evidence_ids": ["test-trail-post-1x-third-party-brake"],
        }
    ]
    assert response["citations"][0]["physical_page"] == 1


def test_cli_does_not_infer_compatibility_from_matching_dimensions(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        ("Are a 31.6 mm Trail Post A2 seatpost and a 30.9 mm Trail Post B1 seatpost compatible?"),
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["response_type"] == "compatibility"
    assert response["compatibility"] == {
        "outcome": "not_found",
        "component_a": None,
        "component_b": None,
        "conditions": [],
    }
    assert response["failure"]["code"] == "not_found"
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_refuses_a_false_premise_connector_without_a_nearby_substitute(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Is a hose barb with barb sleeve V2 compatible with the Trail Post A2 seatpost?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["compatibility"]["outcome"] == "not_found"
    assert response["compatibility"]["component_a"] is None
    assert response["compatibility"]["component_b"] is None
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_asks_for_the_component_when_a_compatibility_alias_is_ambiguous(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    payload = json.loads(compatibility_evidence_path.read_text(encoding="utf-8"))
    first = payload["compatibility_rules"][0]
    first["component_a"]["aliases"].append("Trail Post hose connector")
    second = copy.deepcopy(first)
    second["id"] = "test-barb-type-b-trail-post-a2"
    second["component_a"]["name"] = "hose barb with barb sleeve Type B"
    second["component_a"]["aliases"] = ["Trail Post hose connector"]
    payload["compatibility_rules"].append(second)
    compatibility_evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Is the Trail Post hose connector compatible with the Trail Post A2 seatpost?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "clarification_required"
    assert response["clarification"] == {
        "message": "Please identify the exact component.",
        "missing_information": ["component"],
    }
    assert response["compatibility"] is None
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_asks_for_the_missing_component_of_a_compatibility_pair(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Is the hose barb with barb sleeve compatible?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "clarification_required"
    assert response["clarification"] == {
        "message": "Please identify the exact component.",
        "missing_information": ["component"],
    }
    assert response["compatibility"] is None
    assert response["claims"] == []


def test_cli_asks_for_an_abbreviated_component_instead_of_not_found(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Is the hose barb compatible with the Trail Post seatpost?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "clarification_required"
    assert response["clarification"]["missing_information"] == ["component"]


def test_cli_asks_for_a_component_when_the_compatibility_request_has_no_subject(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Is it compatible?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "clarification_required"
    assert response["clarification"] == {
        "message": "Please identify the exact component.",
        "missing_information": ["component"],
    }
    assert response["compatibility"] is None


def test_cli_rejects_dimension_only_evidence_labelled_as_compatible(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    update_compatibility_rule(
        compatibility_evidence_path,
        rule_updates={"evidence_excerpts": ["31.6 mm matches 31.6 mm."]},
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Is the hose barb with barb sleeve compatible with the Trail Post A2 seatpost?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["compatibility"]["outcome"] == "not_found"
    assert "explicit compatibility statement" in response["failure"]["message"]
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_rejects_an_unverified_compatibility_rule(tmp_path: Path) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    update_compatibility_rule(
        compatibility_evidence_path,
        rule_updates={
            "verification": {
                "status": "machine_extracted",
                "verified_by": "",
                "verified_at": None,
            }
        },
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Is the hose barb with barb sleeve compatible with the Trail Post A2 seatpost?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["compatibility"]["outcome"] == "not_found"
    assert "human verification" in response["failure"]["message"]
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_rejects_a_compatibility_rule_with_an_invalid_citation(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_compatibility_fixture(tmp_path)
    )
    update_compatibility_rule(
        compatibility_evidence_path,
        citation_updates={"section": "Missing section"},
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Is the hose barb with barb sleeve compatible with the Trail Post A2 seatpost?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["compatibility"]["outcome"] == "not_found"
    assert "cited section" in response["failure"]["message"]
    assert response["claims"] == []
    assert response["citations"] == []
