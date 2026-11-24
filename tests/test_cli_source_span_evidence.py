from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from test_cli_procedure import (
    complete_procedure_lines,
    download_and_ingest,
    prepare_procedure_fixture,
    run_cli,
)

LIGATURE = "\ufb03"


def write_ligature_fixture_pdf(path: Path, lines: list[str]) -> None:
    commands = [f"({_pdf_escape(line.replace(LIGATURE, chr(1)))}) Tj 0 -18 Td" for line in lines]
    stream = f"BT /F1 10 Tf 72 720 Td {' '.join(commands)} ET".encode("latin-1")
    to_unicode = b"""/CIDInit /ProcSet findresource begin
12 dict begin
begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def
/CMapName /Adobe-Identity-UCS def
/CMapType 2 def
1 begincodespacerange
<00> <FF>
endcodespacerange
1 beginbfchar
<01> <FB03>
endbfchar
endcmap
CMapName currentdict /CMap defineresource pop
end
end
"""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        (
            b"<< /Type /Page /Parent 2 0 R "
            b"/Resources << /Font << /F1 4 0 R >> >> "
            b"/MediaBox [0 0 612 792] /Contents 6 0 R >>"
        ),
        (
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
            b"/Encoding /WinAnsiEncoding /ToUnicode 5 0 R >>"
        ),
        f"<< /Length {len(to_unicode)} >>\nstream\n".encode() + to_unicode + b"endstream",
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


def test_catalog_binds_steps_and_warnings_to_exact_source_spans(tmp_path: Path) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, complete_procedure_lines())
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    catalog: dict[str, Any] = json.loads(
        (data_dir / "generated" / "retrieval.json").read_text(encoding="utf-8")
    )
    page = catalog["sources"][0]["pages"][0]
    page_spans = {span["span_id"]: span for span in page["spans"]}
    step = catalog["procedures"][0]["steps"][0]
    warning = step["warnings"][0]

    assert step["evidence"]["span_ids"] == ["test-manual:p1:l3:s0"]
    assert step["evidence"]["raw_text"] == "1 Remove the spring cap."
    assert step["evidence"]["normalized_text"] == "1 Remove the spring cap."
    assert step["evidence"]["section"] == "Trail Post spring replacement"
    assert warning["evidence"]["span_ids"] == [
        "test-manual:p1:l4:s0",
        "test-manual:p1:l5:s0",
    ]
    assert warning["evidence"]["raw_text"] == ("NOTICE\nHold the spring under compression.")
    assert warning["evidence"]["normalized_text"] == ("NOTICE Hold the spring under compression.")

    for evidence in (step["evidence"], warning["evidence"]):
        assert evidence["document_id"] == "test-manual"
        assert evidence["physical_page"] == 1
        assert evidence["printed_page"] == 17
        assert [span["span_id"] for span in evidence["spans"]] == evidence["span_ids"]
        for span in evidence["spans"]:
            source_span = page_spans[span["span_id"]]
            assert span["page_box"] == source_span["page_box"]
            assert span["box"] == source_span["box"]
            assert span["raw_text"] == source_span["raw_text"]
            assert span["normalized_text"] == source_span["text"]


def test_span_provenance_is_available_on_request_but_not_in_answers(tmp_path: Path) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, complete_procedure_lines())
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    answer_result = run_cli(
        "ask",
        "What are the steps to replace the Trail Post spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )
    evidence_result = run_cli(
        "evidence",
        "What are the steps to replace the Trail Post spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert answer_result.returncode == 0, answer_result.stderr
    assert evidence_result.returncode == 0, evidence_result.stderr
    answer: dict[str, Any] = json.loads(answer_result.stdout)
    evidence: dict[str, Any] = json.loads(evidence_result.stdout)

    assert all("evidence" not in step for step in answer["procedure"]["steps"])
    assert all(
        "evidence" not in warning
        for step in answer["procedure"]["steps"]
        for warning in step["warnings"]
    )
    assert evidence["matches"][0]["steps"][0]["evidence"]["span_ids"]
    assert evidence["matches"][0]["steps"][0]["warnings"][0]["evidence"]["span_ids"]


def test_broken_word_evidence_preserves_raw_lines_and_normalizes_the_join(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(
            tmp_path,
            [
                "17 Replace hydraulic hose",
                "1 Remove the hy-",
                "draulic hose.",
                "2 Install the new hose.",
                "This concludes the Replace hydraulic hose.",
            ],
        )
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    catalog: dict[str, Any] = json.loads(
        (data_dir / "generated" / "retrieval.json").read_text(encoding="utf-8")
    )
    evidence = catalog["procedures"][0]["steps"][0]["evidence"]

    assert evidence["raw_text"] == "1 Remove the hy-\ndraulic hose."
    assert evidence["normalized_text"] == "1 Remove the hydraulic hose."


def test_ligature_evidence_preserves_the_source_and_normalizes_for_comparison(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(
            tmp_path,
            [
                f"17 O{LIGATURE}ce spring replacement",
                f"1 Inspect the O{LIGATURE}ce latch.",
                f"2 Close the O{LIGATURE}ce latch.",
                f"This concludes the O{LIGATURE}ce spring replacement.",
            ],
            pdf_writer=write_ligature_fixture_pdf,
        )
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    catalog: dict[str, Any] = json.loads(
        (data_dir / "generated" / "retrieval.json").read_text(encoding="utf-8")
    )
    evidence = catalog["procedures"][0]["steps"][0]["evidence"]

    assert LIGATURE in evidence["raw_text"]
    assert LIGATURE in evidence["spans"][0]["raw_text"]
    assert LIGATURE not in evidence["normalized_text"]
    assert evidence["normalized_text"] == "1 Inspect the Office latch."


def test_catalog_rejects_a_step_when_its_stored_excerpt_does_not_resolve(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, complete_procedure_lines())
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )
    catalog_path = data_dir / "generated" / "retrieval.json"
    catalog: dict[str, Any] = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["procedures"][0]["steps"][0]["evidence"]["normalized_text"] = (
        "Remove the spring cap from another page."
    )
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    evidence_result = run_cli(
        "evidence",
        "What are the steps to replace the Trail Post spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )
    answer_result = run_cli(
        "ask",
        "What are the steps to replace the Trail Post spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert evidence_result.returncode == 0, evidence_result.stderr
    assert answer_result.returncode == 0, answer_result.stderr
    inspection: dict[str, Any] = json.loads(evidence_result.stdout)
    answer: dict[str, Any] = json.loads(answer_result.stdout)
    match = inspection["matches"][0]

    assert match["complete"] is False
    assert any(
        "step 1" in issue and "evidence excerpt" in issue for issue in match["validation_issues"]
    )
    assert [step["number"] for step in match["steps"]] == [2, 3]
    assert answer["status"] == "not_found"
    assert answer["procedure"] is None


def test_catalog_rejects_a_step_when_its_document_locator_does_not_resolve(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, complete_procedure_lines())
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )
    catalog_path = data_dir / "generated" / "retrieval.json"
    catalog: dict[str, Any] = json.loads(catalog_path.read_text(encoding="utf-8"))
    step = catalog["procedures"][0]["steps"][1]
    step["citation"]["document_id"] = "other-manual"
    step["evidence"]["document_id"] = "other-manual"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    evidence_result = run_cli(
        "evidence",
        "What are the steps to replace the Trail Post spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert evidence_result.returncode == 0, evidence_result.stderr
    match = json.loads(evidence_result.stdout)["matches"][0]
    assert match["complete"] is False
    assert any("step 2" in issue and "document" in issue for issue in match["validation_issues"])
    assert [step["number"] for step in match["steps"]] == [1, 3]


def test_catalog_rejects_a_step_when_print_and_physical_locators_disagree(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, complete_procedure_lines())
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )
    catalog_path = data_dir / "generated" / "retrieval.json"
    catalog: dict[str, Any] = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["procedures"][0]["steps"][0]["citation"]["printed_page"] = 18
    catalog["procedures"][0]["steps"][1]["citation"]["physical_page"] = 2
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")

    evidence_result = run_cli(
        "evidence",
        "What are the steps to replace the Trail Post spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert evidence_result.returncode == 0, evidence_result.stderr
    match = json.loads(evidence_result.stdout)["matches"][0]
    assert match["complete"] is False
    assert any(
        "step 1" in issue and "printed page" in issue for issue in match["validation_issues"]
    )
    assert any(
        "step 2" in issue and "physical page" in issue for issue in match["validation_issues"]
    )
    assert [step["number"] for step in match["steps"]] == [3]
