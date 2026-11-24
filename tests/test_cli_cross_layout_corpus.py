from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from cross_layout_corpus import (
    CorpusWorkspace,
    ingest_corpus,
    load_corpus,
    materialize_corpus,
    read_catalog,
)
from test_cli_procedure import run_cli

CORPUS = load_corpus()
CASES = {case["id"]: case for case in CORPUS["cases"]}
KNOWN_GAP_REASONS = {
    "03": "ticket 03 page and block classification is not implemented yet",
    "04": "ticket 04 layout-aware spans and fonts is not implemented yet",
}


@pytest.fixture(scope="module")
def corpus_workspace(tmp_path_factory: pytest.TempPathFactory) -> CorpusWorkspace:
    workspace = materialize_corpus(tmp_path_factory.mktemp("cross-layout-corpus"))
    ingest_corpus(workspace)
    return workspace


def test_corpus_contract_names_every_required_layout_and_page_kind() -> None:
    required = {
        "single_column_procedures",
        "two_column_procedures",
        "multilingual_multi_column_pages",
        "contents_pages",
        "torque_table_pages",
        "contact_information_pages",
        "legal_pages",
        "cover_pages",
        "figure_only_pages",
        "repeated_headers",
        "warnings",
        "page_numbers",
        "figure_callouts",
        "broken_words",
        "complete_procedures",
        "missing_first_steps",
        "missing_final_steps",
        "duplicate_numbering",
        "ambiguous_continuations",
        "declarative_profile_required",
    }
    coverage: dict[str, list[str]] = CORPUS["coverage"]
    assert set(coverage) == required
    assert all(case_ids for case_ids in coverage.values())
    assert {case_id for case_ids in coverage.values() for case_id in case_ids} <= set(CASES)


def _case_parameter(case: dict[str, Any]) -> pytest.ParameterSet:
    if "known_gap" not in case:
        return pytest.param(case["id"])
    gap = case["known_gap"]
    return pytest.param(
        case["id"],
        marks=pytest.mark.xfail(
            strict=True,
            reason=KNOWN_GAP_REASONS[gap],
        ),
    )


@pytest.mark.parametrize("case_id", [_case_parameter(case) for case in CORPUS["cases"]])
def test_cli_cross_layout_corpus_case(
    case_id: str,
    corpus_workspace: CorpusWorkspace,
) -> None:
    case = CASES[case_id]
    if case["kind"] == "evidence":
        _assert_evidence_case(case, corpus_workspace)
    else:
        _assert_ask_case(case, corpus_workspace)


def test_corpus_ingestion_is_byte_stable(
    corpus_workspace: CorpusWorkspace,
) -> None:
    catalog_path = corpus_workspace.data_dir / "generated" / "retrieval.json"
    first_catalog = catalog_path.read_bytes()
    first_provenance = read_catalog(corpus_workspace)["ingestion_provenance"]

    _, second_catalog = ingest_corpus(corpus_workspace)

    assert catalog_path.read_bytes() == first_catalog
    assert second_catalog["ingestion_provenance"] == first_provenance


def test_corpus_pdf_generation_is_deterministic(tmp_path: Path) -> None:
    first = materialize_corpus(tmp_path / "first")
    second = materialize_corpus(tmp_path / "second")

    first_pdfs = {path.name: path.read_bytes() for path in sorted(first.pdf_dir.glob("*.pdf"))}
    second_pdfs = {path.name: path.read_bytes() for path in sorted(second.pdf_dir.glob("*.pdf"))}
    assert first_pdfs == second_pdfs
    assert first.profile_path.read_bytes() == second.profile_path.read_bytes()


def test_two_column_completion_requires_the_declarative_profile(
    tmp_path: Path,
) -> None:
    workspace = materialize_corpus(tmp_path)
    profiles = json.loads(workspace.profile_path.read_text(encoding="utf-8"))
    two_column = next(
        profile for profile in profiles["profiles"] if profile["id"] == "two-column-en"
    )
    two_column["end_boundaries"]["markers"] = ["This concludes"]
    workspace.profile_path.write_text(json.dumps(profiles), encoding="utf-8")

    ingest_corpus(workspace)
    result = run_cli(
        "evidence",
        "What are the steps to bleed the brake?",
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    inspection: dict[str, Any] = json.loads(result.stdout)
    assert len(inspection["matches"]) == 1
    match = inspection["matches"][0]
    assert match["complete"] is False
    assert any("procedure end was not found" in issue for issue in match["validation_issues"])


def _assert_evidence_case(
    case: dict[str, Any],
    workspace: CorpusWorkspace,
) -> None:
    result = run_cli(
        "evidence",
        case["question"],
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    inspection: dict[str, Any] = json.loads(result.stdout)
    expected: dict[str, Any] = case["expected"]
    assert len(inspection["matches"]) == expected["match_count"]
    if expected["match_count"] == 0:
        return

    match = inspection["matches"][0]
    assert match["complete"] is expected["complete"]
    assert match["title"] == expected["title"]
    assert [
        {
            "number": step["number"],
            "text": step["text"],
            "warnings": step["warnings"],
        }
        for step in match["steps"]
    ] == expected["steps"]
    assert sorted({page["printed_page"] for page in match["pages"]}) == expected["printed_pages"]
    for step in match["steps"]:
        assert step["citation"]["document_id"] == case["document_id"]

    if "profile_id" in expected:
        catalog = read_catalog(workspace)
        source = next(
            source for source in catalog["sources"] if source["document_id"] == case["document_id"]
        )
        assert source["ingestion_profile"]["profile_id"] == expected["profile_id"]


def _assert_ask_case(
    case: dict[str, Any],
    workspace: CorpusWorkspace,
) -> None:
    result = run_cli(
        "ask",
        case["question"],
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    expected: dict[str, Any] = case["expected"]
    assert response["status"] == expected["status"]

    if expected["status"] == "supported":
        assert response["procedure"]["title"] == expected["procedure_title"]
        assert [step["number"] for step in response["procedure"]["steps"]] == expected[
            "step_numbers"
        ]
        assert [
            {
                "document_id": citation["document_id"],
                "printed_page": citation["printed_page"],
                "physical_page": citation["physical_page"],
                "section": citation["section"],
            }
            for citation in response["citations"]
        ] == expected["citations"]
        return

    assert response["procedure"] is None
    assert response["claims"] == []
    assert response["citations"] == []
    if expected["status"] == "not_found":
        assert expected["message_contains"] in response["failure"]["message"]
    else:
        assert response["clarification"]["missing_information"] == ["task"]
