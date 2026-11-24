from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from test_cli_procedure import run_cli

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "cross-layout-v1"


@dataclass(frozen=True)
class CorpusWorkspace:
    root: Path
    manifest_path: Path
    specification_evidence_path: Path
    compatibility_evidence_path: Path
    profile_path: Path
    pdf_dir: Path
    data_dir: Path


def load_corpus() -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / "corpus.json").read_text(encoding="utf-8"))


def materialize_corpus(root: Path) -> CorpusWorkspace:
    root.mkdir(parents=True, exist_ok=True)
    corpus = load_corpus()
    pdf_dir = root / "pdf-doc"
    pdf_dir.mkdir(exist_ok=True)

    sources: list[dict[str, Any]] = []
    for document in corpus["documents"]:
        source_path = pdf_dir / f"{document['id']}.pdf"
        write_positioned_pdf(source_path, document["pages"])
        source = {
            "id": document["id"],
            "title": document["title"],
            "manufacturer": document["manufacturer"],
            "url": source_path.as_uri(),
            "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "retrieval_date": corpus["retrieval_date"],
            "revision": "Corpus Rev 1",
        }
        if "ingestion_metadata" in document:
            source["ingestion_metadata"] = document["ingestion_metadata"]
        sources.append(source)

    manifest_path = root / "source-manifest.json"
    _write_json(
        manifest_path,
        {
            "manifest_version": corpus["manifest_version"],
            "sources": sources,
        },
    )
    specification_evidence_path = root / "verified-specifications.json"
    _write_json(specification_evidence_path, {"specifications": []})
    compatibility_evidence_path = root / "verified-compatibility.json"
    _write_json(compatibility_evidence_path, {"compatibility_rules": []})
    profile_path = root / "ingestion-profiles.json"
    shutil.copyfile(FIXTURE_DIR / "profiles.json", profile_path)
    return CorpusWorkspace(
        root=root,
        manifest_path=manifest_path,
        specification_evidence_path=specification_evidence_path,
        compatibility_evidence_path=compatibility_evidence_path,
        profile_path=profile_path,
        pdf_dir=pdf_dir,
        data_dir=root / "data",
    )


def ingest_corpus(
    workspace: CorpusWorkspace,
    *,
    language: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    download = run_cli(
        "download",
        "--manifest",
        str(workspace.manifest_path),
        "--pdf-dir",
        str(workspace.pdf_dir),
        "--json",
    )
    assert download.returncode == 0, download.stderr

    ingest_args = [
        "ingest",
        "--manifest",
        str(workspace.manifest_path),
        "--evidence",
        str(workspace.specification_evidence_path),
        "--compatibility-evidence",
        str(workspace.compatibility_evidence_path),
        "--ingestion-profiles",
        str(workspace.profile_path),
        "--pdf-dir",
        str(workspace.pdf_dir),
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    ]
    if language is not None:
        ingest_args.extend(["--language", language])
    ingest = run_cli(*ingest_args)
    assert ingest.returncode == 0, ingest.stderr
    report: dict[str, Any] = json.loads(ingest.stdout)
    catalog = read_catalog(workspace)
    return report, catalog


def read_catalog(workspace: CorpusWorkspace) -> dict[str, Any]:
    return json.loads(
        (workspace.data_dir / "generated" / "retrieval.json").read_text(encoding="utf-8")
    )


def write_positioned_pdf(path: Path, pages: list[dict[str, Any]]) -> None:
    page_object_numbers = [6 + index * 2 for index in range(len(pages))]
    content_object_numbers = [number + 1 for number in page_object_numbers]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            f"<< /Type /Pages /Count {len(pages)} /Kids "
            f"[{' '.join(f'{number} 0 R' for number in page_object_numbers)}] >>"
        ).encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic >>",
    ]
    for page, content_number in zip(
        pages,
        content_object_numbers,
        strict=True,
    ):
        objects.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R "
                    f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
                    f"/MediaBox [0 0 612 792] /Contents {content_number} 0 R >>"
                ).encode(),
                _content_stream(page["lines"]),
            ]
        )

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


def _content_stream(lines: list[list[Any]]) -> bytes:
    commands = ["BT"]
    for entry in lines:
        y, x, text, *rest = entry
        style: dict[str, Any] = rest[0] if rest else {}
        font = str(style.get("font", "F1"))
        size = float(style.get("size", 10))
        commands.append(f"/{font} {size:g} Tf")
        commands.append(f"1 0 0 1 {x} {y} Tm ({_pdf_escape(text)}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1")
    return f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
