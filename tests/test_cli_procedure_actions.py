from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from cross_layout_corpus import ingest_corpus, materialize_corpus, write_positioned_pdf
from test_cli_procedure import download_and_ingest, run_cli, write_fixture_pdf


def prepare_action_fixture(
    tmp_path: Path,
    documents: list[tuple[str, str, list[str]]],
) -> tuple[Path, Path, Path, Path]:
    sources: list[dict[str, str]] = []
    for source_id, manufacturer, lines in documents:
        source_path = tmp_path / f"{source_id}.pdf"
        write_fixture_pdf(source_path, lines)
        sources.append(
            {
                "id": source_id,
                "title": f"{manufacturer} Service Manual",
                "manufacturer": manufacturer,
                "url": source_path.as_uri(),
                "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                "retrieval_date": "2026-11-24",
                "revision": "Rev C",
            }
        )

    manifest_path = tmp_path / "source-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "action-vocabulary-test-1",
                "sources": sources,
            }
        ),
        encoding="utf-8",
    )
    specification_evidence_path = tmp_path / "verified-specifications.json"
    specification_evidence_path.write_text(json.dumps({"specifications": []}), encoding="utf-8")
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


def test_cli_matches_a_procedure_through_a_reviewed_action_alias(tmp_path: Path) -> None:
    lines = [
        "17 Fitting and aligning the rear brake hose",
        "1 Remove the old hose.",
        "2 Fit the new hose.",
        "3 Bleed the brake.",
        "This concludes the rear brake hose fitting procedure.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_action_fixture(
            tmp_path,
            [("magura-manual", "MAGURA", lines)],
        )
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "How do I install the rear brake hose?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["procedure"]["title"] == "Fitting and aligning the rear brake hose"
    assert response["procedure"]["match"] == {
        "basis": "action-alias",
        "canonical_action": "install",
        "heading_action": "fitting",
        "question_action": "install",
        "profile_id": "standard-en",
        "profile_version": "1",
    }


def test_cli_does_not_use_an_action_alias_across_manufacturers(tmp_path: Path) -> None:
    lines = [
        "17 Fitting the rear brake hose",
        "1 Remove the old hose.",
        "2 Fit the new hose.",
        "This concludes the rear brake hose fitting procedure.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_action_fixture(
            tmp_path,
            [
                ("magura-manual", "MAGURA", lines),
                ("rockshox-manual", "RockShox", lines),
            ],
        )
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "How do I install the MAGURA rear brake hose?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["procedure"]["title"] == "Fitting the rear brake hose"
    assert {citation["manufacturer"] for citation in response["citations"]} == {"MAGURA"}


def test_cli_does_not_use_an_action_alias_across_revisions(tmp_path: Path) -> None:
    lines = [
        "17 Fitting the rear brake hose",
        "1 Remove the old hose.",
        "2 Fit the new hose.",
        "This concludes the rear brake hose fitting procedure.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_action_fixture(
            tmp_path,
            [
                ("revision-c-manual", "MAGURA", lines),
                ("revision-d-manual", "MAGURA", lines),
            ],
        )
    )
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"][0]["revision"] = "Rev C"
    manifest["sources"][1]["revision"] = "Rev D"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "How do I install the rear brake hose in Rev C?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert {citation["document_id"] for citation in response["citations"]} == {"revision-c-manual"}


def test_cli_action_aliases_preserve_component_side_and_model_identity(
    tmp_path: Path,
) -> None:
    lines = [
        "17 Fitting the front MT7 brake hose",
        "1 Remove the old hose.",
        "2 Fit the new hose.",
        "This concludes the front MT7 brake hose fitting procedure.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_action_fixture(
            tmp_path,
            [("magura-manual", "MAGURA", lines)],
        )
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    for question in (
        "How do I install the rear MT7 brake hose?",
        "How do I install the front MT8 brake hose?",
        "How do I install the front MT7 brake lever?",
    ):
        result = run_cli(
            "ask",
            question,
            "--data-dir",
            str(data_dir),
            "--json",
        )
        assert result.returncode == 0, result.stderr
        response: dict[str, Any] = json.loads(result.stdout)
        assert response["status"] == "not_found"
        assert response["procedure"] is None


def test_cli_normalizes_reviewed_action_relationships(tmp_path: Path) -> None:
    documents = [
        (
            "fitting-manual",
            "Fixture Manufacturer",
            [
                "17 Fitting the front MT7 brake hose",
                "1 Fit the brake hose.",
                "This concludes the front MT7 brake hose fitting procedure.",
            ],
        ),
        (
            "removal-manual",
            "Fixture Manufacturer",
            [
                "17 Removal of the brake pad",
                "1 Remove the brake pad.",
                "This concludes the brake pad removal procedure.",
            ],
        ),
        (
            "replacement-manual",
            "Fixture Manufacturer",
            [
                "17 Replacement of the brake pad",
                "1 Replace the brake pad.",
                "This concludes the brake pad replacement procedure.",
            ],
        ),
        (
            "cutting-manual",
            "Fixture Manufacturer",
            [
                "17 Cutting the brake hose",
                "1 Cut the brake hose.",
                "This concludes the brake hose cutting procedure.",
            ],
        ),
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_action_fixture(tmp_path, documents)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    cases = [
        ("How do I install the front MT7 brake hose?", "install", "fitting"),
        ("How do I remove the brake pad?", "remove", "removal"),
        ("How do I replace the brake pad?", "replace", "replacement"),
        ("How do I shorten the brake hose?", "shorten", "cutting"),
    ]
    for question, canonical_action, heading_action in cases:
        result = run_cli(
            "ask",
            question,
            "--data-dir",
            str(data_dir),
            "--json",
        )
        assert result.returncode == 0, result.stderr
        response: dict[str, Any] = json.loads(result.stdout)
        assert response["status"] == "supported"
        assert response["procedure"]["match"]["basis"] == "action-alias"
        assert response["procedure"]["match"]["canonical_action"] == canonical_action
        assert response["procedure"]["match"]["heading_action"] == heading_action


def test_cli_records_a_literal_title_match(tmp_path: Path) -> None:
    lines = [
        "17 Fitting the rear brake hose",
        "1 Fit the new hose.",
        "This concludes the rear brake hose fitting procedure.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_action_fixture(
            tmp_path,
            [("magura-manual", "MAGURA", lines)],
        )
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "What are the steps for fitting the rear brake hose?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["procedure"]["match"] == {
        "basis": "literal-title",
        "canonical_action": "install",
        "heading_action": "fitting",
        "question_action": "fitting",
        "profile_id": "standard-en",
        "profile_version": "1",
    }


def test_cli_does_not_treat_an_action_alias_substring_as_a_procedure_heading(
    tmp_path: Path,
) -> None:
    workspace = materialize_corpus(tmp_path)
    source_path = workspace.pdf_dir / "warranty-manual.pdf"
    write_positioned_pdf(
        source_path,
        [
            {
                "lines": [
                    [720, 72, "Benefit and warranty overview", {"font": "F2", "size": 16}],
                    [690, 72, "1 Inspect the frame."],
                    [672, 72, "2 Check the brakes."],
                    [654, 72, "This concludes the warranty overview."],
                ]
            }
        ],
    )
    workspace.manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "action-vocabulary-substring-1",
                "sources": [
                    {
                        "id": "warranty-manual",
                        "title": "Warranty Manual",
                        "manufacturer": "Fixture Manufacturer",
                        "url": source_path.as_uri(),
                        "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                        "retrieval_date": "2026-11-24",
                        "revision": "Rev C",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    profiles: dict[str, Any] = json.loads(workspace.profile_path.read_text(encoding="utf-8"))
    profiles["profiles"][0]["action_aliases"] = {"install": ["fit"]}
    workspace.profile_path.write_text(json.dumps(profiles), encoding="utf-8")

    _, catalog = ingest_corpus(workspace)

    assert catalog["procedures"] == []
    page = catalog["sources"][0]["pages"][0]
    assert {candidate["reason"] for candidate in page["rejected_step_candidates"]} == {
        "missing-procedure-heading"
    }
