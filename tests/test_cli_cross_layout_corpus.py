from __future__ import annotations

import hashlib
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
    write_positioned_pdf,
)
from test_cli_procedure import run_cli

from zabm.ingestion import normalize_pdf_text

CORPUS = load_corpus()
CASES = {case["id"]: case for case in CORPUS["cases"]}
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


@pytest.mark.parametrize("case_id", [case["id"] for case in CORPUS["cases"]])
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


def test_catalog_preserves_font_span_and_box_metadata(
    corpus_workspace: CorpusWorkspace,
) -> None:
    catalog = read_catalog(corpus_workspace)
    page = next(
        page
        for source in catalog["sources"]
        if source["document_id"] == "two-column"
        for page in source["pages"]
    )

    assert page["columns"] == [
        {"id": "left", "x_min": 0.0, "x_max": 0.5},
        {"id": "right", "x_min": 0.5, "x_max": 1.0},
    ]
    assert page["languages"] == ["en"]
    assert page["spans"]
    assert len({span["span_id"] for span in page["spans"]}) == len(page["spans"])
    assert all(span["line_id"] for span in page["spans"])
    assert all(span["document_id"] == "two-column" for span in page["spans"])
    assert all(span["physical_page"] == 1 for span in page["spans"])
    assert all(span["font_name"] == "Helvetica" for span in page["spans"])
    assert all(span["font_size"] == 10.0 for span in page["spans"])
    assert all(span["bold"] is False and span["italic"] is False for span in page["spans"])
    assert page["page_width"] == 612.0
    assert page["page_height"] == 792.0
    assert all(
        span["raw_text"]
        and span["text"]
        and span["box"]["x_min"] < span["box"]["x_max"]
        and span["page_box"]["x_min"] < span["page_box"]["x_max"]
        and span["page_box"]["y_min"] < span["page_box"]["y_max"]
        for span in page["spans"]
    )
    assert [span["column_id"] for span in page["spans"]] == [
        "left",
        "left",
        "left",
        "left",
        "left",
        "left",
        "left",
        "right",
        "right",
        "right",
    ]


def test_multilingual_spans_and_steps_remain_language_isolated(
    corpus_workspace: CorpusWorkspace,
) -> None:
    catalog = read_catalog(corpus_workspace)
    page = next(
        page
        for source in catalog["sources"]
        if source["document_id"] == "multilingual"
        for page in source["pages"]
    )

    assert page["languages"] == ["en", "de"]
    assert [span["column_id"] for span in page["spans"]] == [
        "english",
        "english",
        "english",
        "english",
        "english",
        "german",
        "german",
        "german",
    ]
    assert [span["language"] for span in page["spans"]] == [
        "en",
        "en",
        "en",
        "en",
        "en",
        "de",
        "de",
        "de",
    ]
    assert all(
        "Umwerfer" not in block["text"] for block in page["blocks"] if block["kind"] == "step"
    )


def test_multi_column_procedure_evidence_never_joins_distinct_columns(
    corpus_workspace: CorpusWorkspace,
) -> None:
    catalog = read_catalog(corpus_workspace)
    procedure = next(
        procedure for procedure in catalog["procedures"] if procedure["document_id"] == "two-column"
    )

    for step in procedure["steps"]:
        evidence_spans = step["evidence"]["spans"]
        assert len({span["column_id"] for span in evidence_spans}) == 1
        assert all(span["span_id"] in step["evidence"]["span_ids"] for span in evidence_spans)
        for warning in step["warnings"]:
            assert len({span["column_id"] for span in warning["evidence"]["spans"]}) == 1


def test_font_weight_and_style_hints_are_preserved_in_spans(tmp_path: Path) -> None:
    workspace = materialize_corpus(tmp_path)
    document_id = "styled-layout"
    lines = [
        [720, 72, "32 Replace the styled lever", {"font": "F2", "size": 16}],
        [690, 72, "1 Remove the lever.", {"font": "F3", "size": 11}],
        [672, 72, "2 Install the lever.", {"font": "F1", "size": 9}],
        [654, 72, "This concludes the styled lever replacement."],
    ]
    _replace_with_single_source(
        workspace,
        document_id=document_id,
        title="Styled Layout Manual",
        lines=lines,
    )

    _, catalog = ingest_corpus(workspace)
    spans = catalog["sources"][0]["pages"][0]["spans"]

    assert spans[0]["font_name"] == "Helvetica-Bold"
    assert spans[0]["font_size"] == 16.0
    assert spans[0]["bold"] is True
    assert spans[0]["italic"] is False
    assert spans[1]["font_name"] == "Times-Italic"
    assert spans[1]["font_size"] == 11.0
    assert spans[1]["bold"] is False
    assert spans[1]["italic"] is True


def test_auto_detected_columns_keep_a_right_column_procedure_in_source_order(
    tmp_path: Path,
) -> None:
    workspace = materialize_corpus(tmp_path)
    document_id = "auto-columns"
    _replace_with_single_source(
        workspace,
        document_id=document_id,
        title="Auto Column Manual",
        lines=[
            [720, 72, "33 Replace the right brake pad"],
            [690, 72, "Left column installation notes."],
            [690, 330, "1 Remove the right brake pad."],
            [672, 330, "2 Install the right brake pad."],
            [654, 330, "This concludes the right brake pad replacement."],
        ],
    )

    _, catalog = ingest_corpus(workspace)
    page = catalog["sources"][0]["pages"][0]
    assert [column["id"] for column in page["columns"]] == ["auto-left", "auto-right"]
    result = run_cli(
        "evidence",
        "What are the steps to replace the right brake pad?",
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    inspection: dict[str, Any] = json.loads(result.stdout)
    assert len(inspection["matches"]) == 1
    match = inspection["matches"][0]
    assert match["complete"] is True
    assert [step["text"] for step in match["steps"]] == [
        "Remove the right brake pad.",
        "Install the right brake pad.",
    ]
    assert all("Left column" not in step["text"] for step in match["steps"])


def test_auto_detected_multilingual_columns_do_not_merge_french_into_english(
    tmp_path: Path,
) -> None:
    workspace = materialize_corpus(tmp_path)
    document_id = "auto-multilingual"
    _replace_with_single_source(
        workspace,
        document_id=document_id,
        title="Automatic Multilingual Manual",
        lines=[
            [720, 72, "34 Replace the brake lever"],
            [690, 72, "1 Remove the brake lever."],
            [672, 72, "2 Install the brake lever."],
            [654, 72, "This concludes the brake lever replacement."],
            [690, 330, "1 Retirez la vis de l'etrier."],
            [672, 330, "2 Installez la vis."],
        ],
    )

    _, catalog = ingest_corpus(workspace)
    page = catalog["sources"][0]["pages"][0]
    assert page["languages"] == ["en", "fr"]
    assert [span["language"] for span in page["spans"]] == ["en", "en", "en", "en", "fr", "fr"]
    result = run_cli(
        "evidence",
        "What are the steps to replace the brake lever?",
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    inspection: dict[str, Any] = json.loads(result.stdout)
    assert len(inspection["matches"]) == 1
    assert [step["text"] for step in inspection["matches"][0]["steps"]] == [
        "Remove the brake lever.",
        "Install the brake lever.",
    ]
    assert all("Retirez" not in step["text"] for step in inspection["matches"][0]["steps"])


def test_cli_requested_language_selects_german_without_merging_english(
    tmp_path: Path,
) -> None:
    workspace = materialize_corpus(tmp_path)
    _, catalog = ingest_corpus(workspace, language="de")
    page = next(
        page
        for source in catalog["sources"]
        if source["document_id"] == "multilingual"
        for page in source["pages"]
    )

    assert page["extraction_language"] == "de"
    step_texts = [block["text"] for block in page["blocks"] if block["kind"] == "step"]
    assert len(step_texts) == 3
    assert all(
        "Loosen" not in text and "Align" not in text and "Tighten" not in text
        for text in step_texts
    )
    assert any("Losen Sie" in text for text in step_texts)


def _replace_with_single_source(
    workspace: CorpusWorkspace,
    *,
    document_id: str,
    title: str,
    lines: list[list[Any]],
) -> None:
    source_path = workspace.pdf_dir / f"{document_id}.pdf"
    write_positioned_pdf(source_path, [{"lines": lines}])
    workspace.manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": f"{document_id}-v1",
                "sources": [
                    {
                        "id": document_id,
                        "title": title,
                        "manufacturer": "Cross Layout Fixtures",
                        "url": source_path.as_uri(),
                        "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                        "retrieval_date": "2026-11-24",
                        "revision": "Fixture Rev 1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_ingestion_provenance_records_pinned_pdf_dependency_versions(
    corpus_workspace: CorpusWorkspace,
) -> None:
    provenance = read_catalog(corpus_workspace)["ingestion_provenance"]

    assert provenance["fonttools_version"] == "4.68.0"
    assert provenance["pypdf_version"] == "6.21.4"


def test_pdf_text_normalization_handles_ligatures_soft_hyphens_tabs_and_breaks() -> None:
    assert normalize_pdf_text("O\ufb03ce\u00ad\tmanual") == "Office manual"
    assert normalize_pdf_text("Remove the hy-\ndraulic hose.") == "Remove the hydraulic hose."


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


def test_repeated_running_header_continues_one_procedure_across_pages(
    corpus_workspace: CorpusWorkspace,
) -> None:
    catalog = read_catalog(corpus_workspace)
    procedure = next(
        procedure
        for procedure in catalog["procedures"]
        if procedure["document_id"] == "single-column"
    )

    assert procedure["page_numbers"] == [1, 2]
    assert procedure["grouping_decisions"] == [
        {
            "decision": "merged",
            "reason": "continued step numbering on the adjacent page",
            "pages": [1, 2],
        }
    ]


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
            "warnings": [
                {"severity": warning["severity"], "text": warning["text"]}
                for warning in step["warnings"]
            ],
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
