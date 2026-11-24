from __future__ import annotations

import re
from collections.abc import Sequence

from zabm.ingestion import (
    BlockClassification,
    DocumentProfile,
    LayoutSpan,
    LayoutStageResult,
    PageBlockClassificationResult,
    PageKind,
    PageRegion,
    PdfPageObservation,
)

CONTENTS_HEADING = re.compile(r"\b(?:table\s+of\s+)?contents\b", re.IGNORECASE)
INDEX_HEADING = re.compile(r"^\s*(?:alphabetical\s+)?index\b", re.IGNORECASE)
DOTTED_LEADER = re.compile(r"\.{3,}\s*\d{1,3}\s*$")
PAGE_REFERENCE = re.compile(r"(?:\.{2,}|\s{2,})\s*\d{1,3}\s*$")
PAGE_NUMBER = re.compile(r"^\d{1,3}$")
SECTION_ENTRY = re.compile(r"^\d{1,2}(?:\.\d{1,2})?\s+[A-Za-z]")
ALPHABETICAL_ENTRY = re.compile(r"^[A-Z]\s+\S.*\d{1,3}$")
NUMBERED_LINE = re.compile(r"^\d{1,2}\s+\S")
TABLE_HEADING = re.compile(
    r"\b(?:table|torque|tightening\s+torques?|specifications?)\b",
    re.IGNORECASE,
)
MEASUREMENT = re.compile(r"\b\d+(?:\.\d+)?\s*(?:N\s*m|Nm|mm|in-lb|lbf)\b", re.IGNORECASE)
COVER_HEADING = re.compile(r"^\s*(?:cover|title\s+page)\b", re.IGNORECASE)
CONTACT_HEADING = re.compile(
    r"\b(?:contact(?:\s+information)?|customer\s+(?:service|support)|"
    r"technical\s+support|support\s+information)\b",
    re.IGNORECASE,
)
LEGAL_HEADING = re.compile(
    r"\b(?:legal(?:\s+notice)?|liability|warranty|copyright|disclaimer|terms\s+and\s+conditions)\b",
    re.IGNORECASE,
)
ADVERTISEMENT_HEADING = re.compile(
    r"\b(?:advertisement|sponsored|buy\s+now|shop\s+now)\b",
    re.IGNORECASE,
)
NAVIGATION_HEADING = re.compile(r"^\s*(?:navigation|contents\s+map)\b", re.IGNORECASE)
NAVIGATION_TEXT = re.compile(
    r"\b(?:proceed\s+to|see\s+(?:section|page)|go\s+to\s+(?:section|page)|next\s+section)\b",
    re.IGNORECASE,
)
FIGURE_TEXT = re.compile(r"\b(?:figure|fig\.|illustration|diagram)\b", re.IGNORECASE)
FIGURE_CALLOUT = re.compile(r"^[A-Z]\s+\S")
WARNING_TEXT = re.compile(r"^(?:warning|notice|caution|danger)\b", re.IGNORECASE)
SERVICE_HEADING = re.compile(r"^(?:\d+/)?\d+\s+Hour\s+Service\b", re.IGNORECASE)
NON_PROCEDURE_PAGE_KINDS = frozenset[PageKind](
    {
        "cover",
        "contents",
        "index",
        "contact",
        "legal",
        "advertisement",
        "navigation",
        "table",
        "figure",
        "warning",
    }
)


class DeterministicPageBlockClassifier:
    def classify(
        self,
        observation: PdfPageObservation,
        layout: LayoutStageResult,
        profile: DocumentProfile,
    ) -> PageBlockClassificationResult:
        override = next(
            (
                exception
                for exception in profile.page_classification.exceptions
                if exception.physical_page == observation.physical_page
            ),
            None,
        )
        if override is not None:
            return self._result(
                observation,
                layout,
                override.kind,
                confidence=1.0,
                uncertainty=f"profile page classification exception: {override.reason}",
                profile=profile,
            )

        texts = [_normalize(span.text) for span in layout.spans if _normalize(span.text)]
        if not texts:
            return self._result(
                observation,
                layout,
                "unknown",
                confidence=0.0,
                uncertainty="the page has no extractable text",
                profile=profile,
            )

        title_text = next(
            (text for text in texts[:2] if not PAGE_NUMBER.fullmatch(text)),
            texts[0],
        )
        dotted_leaders = sum(bool(DOTTED_LEADER.search(text)) for text in texts)
        page_references = sum(bool(PAGE_REFERENCE.search(text)) for text in texts)
        section_entries = sum(bool(SECTION_ENTRY.match(text)) for text in texts)
        alphabetical_entries = sum(bool(ALPHABETICAL_ENTRY.match(text)) for text in texts)
        if (
            CONTENTS_HEADING.search(title_text)
            or dotted_leaders >= 2
            or (page_references >= 2 and section_entries >= 2)
        ):
            return self._result(
                observation,
                layout,
                "contents",
                confidence=0.98,
                profile=profile,
            )
        if INDEX_HEADING.search(title_text) or (page_references >= 3 and alphabetical_entries >= 3):
            return self._result(observation, layout, "index", confidence=0.98, profile=profile)

        table_rows = sum(_looks_like_table_row(span.raw_text) for span in layout.spans)
        if TABLE_HEADING.search(title_text) or (table_rows >= 2 and table_rows >= len(texts) / 2):
            return self._result(
                observation,
                layout,
                "table",
                confidence=0.96,
                profile=profile,
            )

        if FIGURE_TEXT.search(title_text):
            return self._result(
                observation,
                layout,
                "figure",
                confidence=0.96,
                profile=profile,
            )
        if CONTACT_HEADING.search(title_text):
            return self._result(
                observation,
                layout,
                "contact",
                confidence=0.96,
                profile=profile,
            )
        if LEGAL_HEADING.search(title_text):
            return self._result(observation, layout, "legal", confidence=0.96, profile=profile)
        if ADVERTISEMENT_HEADING.search(title_text):
            return self._result(
                observation,
                layout,
                "advertisement",
                confidence=0.96,
                profile=profile,
            )
        if (
            NAVIGATION_HEADING.search(title_text)
            or sum(bool(NAVIGATION_TEXT.search(text)) for text in texts) >= 2
        ):
            return self._result(
                observation,
                layout,
                "navigation",
                confidence=0.96,
                profile=profile,
            )
        if WARNING_TEXT.match(title_text) and not any(NUMBERED_LINE.match(text) for text in texts):
            return self._result(observation, layout, "warning", confidence=0.92, profile=profile)
        if COVER_HEADING.search(title_text) or (
            observation.physical_page == 1
            and len(texts) <= 4
            and not any(NUMBERED_LINE.match(text) for text in texts)
        ):
            return self._result(observation, layout, "cover", confidence=0.9, profile=profile)

        page_kind: PageKind = (
            "procedure-step" if any(NUMBERED_LINE.match(text) for text in texts) else "paragraph"
        )
        return self._result(observation, layout, page_kind, confidence=0.75, profile=profile)

    def _result(
        self,
        observation: PdfPageObservation,
        layout: LayoutStageResult,
        page_kind: PageKind,
        *,
        confidence: float,
        uncertainty: str | None = None,
        profile: DocumentProfile,
    ) -> PageBlockClassificationResult:
        page_has_figure = any(FIGURE_TEXT.search(_normalize(span.text)) for span in layout.spans)
        blocks = [
            BlockClassification(
                block_id=f"{span.span_id}:block",
                kind=_block_kind(
                    span,
                    index=index,
                    page_kind=page_kind,
                    profile=profile,
                    page_has_figure=page_has_figure,
                ),
                text=span.text,
                span_ids=[span.span_id],
                confidence=confidence,
                uncertainty=uncertainty,
            )
            for index, span in enumerate(layout.spans)
        ]
        uncertain = page_kind == "unknown" or confidence < 0.55
        return PageBlockClassificationResult(
            document_id=observation.document_id,
            physical_page=observation.physical_page,
            page_kind=page_kind,
            confidence=confidence,
            blocks=blocks,
            uncertain=uncertain,
            rejection_reason=uncertainty if uncertain else None,
        )


def page_allows_procedure_extraction(page_kind: PageKind, *, uncertain: bool) -> bool:
    return not uncertain and page_kind not in NON_PROCEDURE_PAGE_KINDS


def _block_kind(
    span: LayoutSpan,
    *,
    index: int,
    page_kind: PageKind,
    profile: DocumentProfile,
    page_has_figure: bool,
) -> PageKind:
    normalized = _normalize(span.text)
    if WARNING_TEXT.match(normalized):
        return "warning"
    if _in_regions(span, profile.figures.excluded_regions):
        return "figure"
    if _in_regions(span, profile.tables.excluded_regions):
        return "table"
    if index == 0 or SERVICE_HEADING.search(normalized):
        return "heading"
    if page_kind in {"contents", "index", "contact", "legal", "advertisement", "navigation"}:
        return "paragraph"
    if page_kind == "table" or _looks_like_table_row(span.raw_text):
        return "table"
    if (
        page_kind == "figure"
        or FIGURE_TEXT.search(normalized)
        or (page_has_figure and FIGURE_CALLOUT.match(normalized))
    ):
        return "figure"
    if NUMBERED_LINE.match(normalized):
        return "procedure-step"
    return "paragraph"


def _in_regions(span: LayoutSpan, regions: Sequence[PageRegion]) -> bool:
    center_x = (span.box.x_min + span.box.x_max) / 2
    center_y = (span.box.y_min + span.box.y_max) / 2
    return any(
        region.box.x_min <= center_x <= region.box.x_max
        and region.box.y_min <= center_y <= region.box.y_max
        for region in regions
    )


def _looks_like_table_row(text: str) -> bool:
    measurement_count = len(MEASUREMENT.findall(text))
    return measurement_count >= 2 or ("  " in text and len(text.split()) >= 3)


def _normalize(text: str) -> str:
    return " ".join(text.split())
