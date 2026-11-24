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
    "04": "ticket 04 layout-aware spans and fonts is not implemented yet",
}
EXPECTED_PAGE_KINDS = {
    "cover-page": "cover",
    "contents-page": "contents",
    "dotted-contents-page": "contents",
    "index-page": "index",
    "contact-page": "contact",
    "legal-page": "legal",
    "advertisement-page": "advertisement",
    "navigation-page": "navigation",
    "torque-table-page": "table",
    "figure-only-page": "figure",
    "warning-page": "warning",
    "paragraph-page": "paragraph",
    "single-column": "procedure-step",
    "two-column": "procedure-step",
    "uncertain-page": "unknown",
}
EXPECTED_BLOCK_KINDS = {
    "single-column": {"heading", "warning", "procedure-step"},
    "two-column": {"heading", "warning", "procedure-step", "figure"},
    "torque-table-page": {"heading", "table"},
    "contents-page": {"heading", "paragraph"},
    "paragraph-page": {"heading", "paragraph"},
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
        "index_pages",
        "advertisement_pages",
        "navigation_pages",
        "uncertain_pages",
        "torque_table_pages",
        "mixed_table_and_procedure",
        "contact_information_pages",
        "legal_pages",
        "cover_pages",
        "figure_only_pages",
        "warning_pages",
        "paragraph_pages",
        "magura_false_positives",
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


def test_corpus_records_page_and_block_classifications(
    corpus_workspace: CorpusWorkspace,
) -> None:
    catalog = read_catalog(corpus_workspace)
    pages_by_document = {
        source["document_id"]: source["pages"]
        for source in catalog["sources"]
        if source["document_id"] in EXPECTED_PAGE_KINDS
    }

    assert {
        document_id: source_pages[0]["page_kind"]
        for document_id, source_pages in pages_by_document.items()
    } == EXPECTED_PAGE_KINDS
    for source_pages in pages_by_document.values():
        for page in source_pages:
            assert 0 <= page["classification_confidence"] <= 1
            if page["page_kind"] == "unknown":
                assert page["classification_uncertain"] is True
                assert page["classification_uncertainty"]
            else:
                assert page["classification_uncertain"] is False
    for document_id, expected_kinds in EXPECTED_BLOCK_KINDS.items():
        blocks = [block for page in pages_by_document[document_id] for block in page["blocks"]]
        assert {block["classified_kind"] for block in blocks} >= expected_kinds


def test_page_furniture_is_retained_but_not_classified_as_steps(
    corpus_workspace: CorpusWorkspace,
) -> None:
    catalog = read_catalog(corpus_workspace)
    page = next(
        page
        for source in catalog["sources"]
        if source["document_id"] == "single-column"
        for page in source["pages"]
        if page["physical_page"] == 1
    )

    assert "Release the hub clamp before disassembly." in page["text"]
    assert page["text"].strip().endswith("12")
    assert all(
        block["classified_kind"] != "procedure-step" or block["text"].strip() != "12"
        for block in page["blocks"]
    )


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


def test_profile_page_classification_exception_fails_closed_for_procedures(
    tmp_path: Path,
) -> None:
    workspace = materialize_corpus(tmp_path)
    profiles = json.loads(workspace.profile_path.read_text(encoding="utf-8"))
    two_column = next(
        profile for profile in profiles["profiles"] if profile["id"] == "two-column-en"
    )
    two_column["page_classification"]["exceptions"] = [
        {
            "physical_page": 1,
            "kind": "table",
            "reason": "Maintainer-reviewed exception for this layout.",
        }
    ]
    workspace.profile_path.write_text(json.dumps(profiles), encoding="utf-8")

    ingest_corpus(workspace)
    catalog = read_catalog(workspace)
    page = next(
        page
        for source in catalog["sources"]
        if source["document_id"] == "two-column"
        for page in source["pages"]
    )

    assert page["page_kind"] == "table"
    assert page["classification_confidence"] == 1.0
    assert page["classification_uncertain"] is False
    assert page["blocks"][0]["classification_uncertainty"].startswith(
        "profile page classification exception:"
    )
    result = run_cli(
        "evidence",
        "What are the steps to bleed the brake?",
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    inspection: dict[str, Any] = json.loads(result.stdout)
    assert inspection["matches"] == []


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
