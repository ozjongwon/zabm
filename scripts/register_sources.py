#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf._configuration import apply_configuration
from pypdf.errors import DependencyError

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "data" / "manifests" / "source-pack-v1.json"
DEFAULT_PDF_DIR = REPO_ROOT / "pdf-doc"
DEFAULT_DATA_DIR = REPO_ROOT / ".zabm"
DEFAULT_SPECIFICATIONS = REPO_ROOT / "data" / "evidence" / "verified-specifications.json"
DEFAULT_COMPATIBILITY = REPO_ROOT / "data" / "evidence" / "verified-compatibility.json"
MAX_SOURCES = 8
STREAM_PARSING_WORK_MAXIMUM_COUNT = 20_000_000


class RegistrationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedSource:
    path: Path
    source: dict[str, Any]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Register unregistered PDF files from a directory in the source manifest, "
            "then ingest the source pack."
        ),
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_SPECIFICATIONS)
    parser.add_argument(
        "--compatibility-evidence",
        type=Path,
        default=DEFAULT_COMPATIBILITY,
    )
    parser.add_argument("--retrieval-date", type=date.fromisoformat, default=date.today())
    parser.add_argument(
        "--manufacturer",
        help="Override inferred manufacturer metadata for every newly registered PDF.",
    )
    parser.add_argument("--skip-ingest", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    args = _parser().parse_args(argv)
    try:
        prepared, rejected = _prepare_sources(
            manifest_path=args.manifest,
            pdf_dir=args.pdf_dir,
            retrieval_date=args.retrieval_date,
            manufacturer_override=args.manufacturer,
        )
        _commit_sources(prepared, args.manifest)
    except (OSError, RegistrationError, ValueError) as exc:
        print(f"register-sources: {exc}", file=sys.stderr)
        return 1

    if prepared:
        for item in prepared:
            print(f"Registered {item.source['id']}: {item.path}")
            print(f"  sha256: {item.source['sha256']}")
    else:
        print("No unregistered PDF files found.")
    for path, message in rejected:
        print(f"Rejected {path}: {message}", file=sys.stderr)

    if args.skip_ingest:
        return 1 if rejected else 0

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "zabm",
            "ingest",
            "--manifest",
            str(args.manifest),
            "--evidence",
            str(args.evidence),
            "--compatibility-evidence",
            str(args.compatibility_evidence),
            "--pdf-dir",
            str(args.pdf_dir),
            "--data-dir",
            str(args.data_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        print(
            "register-sources: files were registered, but ingestion failed; "
            "fix the reported source issue and rerun ingestion.",
            file=sys.stderr,
        )
    return result.returncode or (1 if rejected else 0)


def _prepare_sources(
    *,
    manifest_path: Path,
    pdf_dir: Path,
    retrieval_date: date,
    manufacturer_override: str | None,
) -> tuple[list[PreparedSource], list[tuple[Path, str]]]:
    manifest = _read_json(manifest_path)
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise RegistrationError(f"{manifest_path} does not contain a sources array")
    if not pdf_dir.is_dir():
        raise RegistrationError(f"PDF directory does not exist: {pdf_dir}")

    registered_ids = {
        str(source["id"]) for source in sources if isinstance(source, dict) and source.get("id")
    }
    unregistered = [
        path for path in sorted(pdf_dir.glob("*.pdf")) if path.stem not in registered_ids
    ]
    prepared: list[PreparedSource] = []
    rejected: list[tuple[Path, str]] = []
    for path in unregistered:
        try:
            reader, page_count, text_page_count = _validate_pdf(path)
        except RegistrationError as exc:
            rejected.append((path, str(exc)))
            continue
        manufacturer = manufacturer_override or _infer_manufacturer(path)
        prepared.append(
            PreparedSource(
                path=path,
                source={
                    "id": path.stem,
                    "title": _infer_title(path, reader, manufacturer),
                    "manufacturer": manufacturer,
                    "url": _source_url(path),
                    "sha256": _file_sha256(path),
                    "retrieval_date": retrieval_date.isoformat(),
                    "revision": _infer_revision(path, reader),
                },
            )
        )
        print(f"Validated {path.name}: {page_count} pages, {text_page_count} with text")
    if len(sources) + len(prepared) > MAX_SOURCES:
        raise RegistrationError(
            f"candidate source pack would contain {len(sources) + len(prepared)} "
            f"documents; the maximum is {MAX_SOURCES}"
        )
    return prepared, rejected


def _commit_sources(prepared: list[PreparedSource], manifest_path: Path) -> None:
    if not prepared:
        return
    manifest = _read_json(manifest_path)
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        raise RegistrationError(f"{manifest_path} does not contain a sources array")
    manifest["manifest_version"] = _next_manifest_version(
        str(manifest.get("manifest_version", "1"))
    )
    manifest["sources"] = [*sources, *(item.source for item in prepared)]
    _write_json(manifest_path, manifest)


def _validate_pdf(path: Path) -> tuple[PdfReader, int, int]:
    with path.open("rb") as source:
        if not source.read(5).startswith(b"%PDF-"):
            raise RegistrationError(f"{path.name} is not a PDF document")
    try:
        with apply_configuration(
            stream_parsing_work_maximum_count=STREAM_PARSING_WORK_MAXIMUM_COUNT
        ):
            reader = PdfReader(path)
            if reader.is_encrypted:
                raise RegistrationError(
                    f"{path.name} is encrypted; provide a directly readable PDF or decrypt it first"
                )
            pages = [page.extract_text() or "" for page in reader.pages]
    except RegistrationError:
        raise
    except DependencyError as exc:
        raise RegistrationError(
            f"{path.name} is encrypted; provide a directly readable PDF or decrypt it first"
        ) from exc
    except Exception as exc:
        raise RegistrationError(f"cannot validate {path.name}: {exc}") from exc
    text_page_count = sum(bool(text.strip()) for text in pages)
    if not pages:
        raise RegistrationError(f"{path.name} contains no pages")
    if text_page_count == 0:
        raise RegistrationError(
            f"{path.name} has no extractable text; transcribe or OCR it before registration"
        )
    return reader, len(pages), text_page_count


def _infer_manufacturer(path: Path) -> str:
    stem = path.stem.casefold()
    if "magura" in stem:
        return "MAGURA"
    if "rockshox" in stem or "reverb" in stem:
        return "SRAM (RockShox)"
    if "sram" in stem:
        return "SRAM"
    if "shimano" in stem:
        return "Shimano"
    if "fox" in stem:
        return "FOX"
    if "campagnolo" in stem:
        return "Campagnolo"
    if "dtswiss" in stem or "dt-swiss" in stem:
        return "DT Swiss"
    first_word = re.split(r"[\s_-]+", path.stem, maxsplit=1)[0]
    return first_word.upper() if first_word.isalpha() else "Unknown"


def _infer_title(path: Path, reader: PdfReader, manufacturer: str) -> str:
    metadata_title = reader.metadata.title if reader.metadata else None
    if isinstance(metadata_title, str):
        cleaned = " ".join(metadata_title.split())
        if 4 <= len(cleaned) <= 160:
            return cleaned
    title = " ".join(
        word if word.isupper() else word.capitalize()
        for word in re.split(r"[\s_-]+", path.stem)
        if word
    )
    if _slug(title).startswith(_slug(manufacturer).split("-", maxsplit=1)[0]):
        return title
    return f"{manufacturer} {title}".strip()


def _infer_revision(path: Path, reader: PdfReader) -> str | None:
    revision = re.search(
        r"\brev(?:ision)?[\s_-]*([a-z0-9]+)\b",
        path.stem,
        re.IGNORECASE,
    )
    if revision:
        return f"Rev {revision.group(1).upper()}"
    modified = reader.metadata.get("/ModDate") if reader.metadata else None
    match = re.search(r"D:(\d{4})(\d{2})(\d{2})", str(modified or ""))
    if match:
        return f"PDF modified {match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def _source_url(path: Path) -> str:
    for suffix in (".source-url", ".url"):
        sidecar = path.with_suffix(suffix)
        if sidecar.is_file():
            value = sidecar.read_text(encoding="utf-8").strip()
            if value:
                return value
    return path.resolve().as_uri()


def _next_manifest_version(version: str) -> str:
    match = re.match(r"^(.*?)(\d+)$", version)
    if match is None:
        return f"{version}.registered-1"
    return f"{match.group(1)}{int(match.group(2)) + 1}"


def _slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")
    return slug or "source"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistrationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RegistrationError(f"{path} does not contain a JSON object")
    return payload


def _write_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(f"{path.suffix}.part")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
