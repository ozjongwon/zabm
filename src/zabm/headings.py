from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import groupby
from statistics import median

from zabm.ingestion import (
    BlockClassification,
    DocumentProfile,
    HeadingHierarchyResult,
    HeadingNode,
    LayoutSpan,
    LayoutStageResult,
    PageBlockClassificationResult,
    normalize_pdf_text,
)

NUMBERED_HEADING = re.compile(
    r"^\s*(?P<number>\d{1,3}(?:\.\d{1,3}){1,5})[.)]?\s+(?P<title>[A-Za-z].*)$"
)
PRINTED_PAGE_TITLE = re.compile(r"^\s*\d{1,3}\s+(?P<title>[A-Za-z].*)$")
SERVICE_HEADING = re.compile(
    r"^(?:\d+/)?\d+\s+Hour\s+Service\s+(?P<title>.+)$",
    re.IGNORECASE,
)
WARNING_HEADING = re.compile(r"^(?:warning|notice|caution|danger)\b", re.IGNORECASE)
TERMINAL_SENTENCE = re.compile(r"[.!?]$")
STEP_TEXT = re.compile(r"^\d{1,2}(?:\s+\S|$)")
CONTINUED_TITLE = re.compile(r"\s+continued$", re.IGNORECASE)


@dataclass(frozen=True)
class _HeadingCandidate:
    spans: list[LayoutSpan]
    text: str
    title: str
    path_title: str
    level: int


class DeterministicHeadingReconstructor:
    def reconstruct(
        self,
        layout: LayoutStageResult,
        classification: PageBlockClassificationResult,
        profile: DocumentProfile,
        *,
        preceding_headings: Sequence[HeadingNode] = (),
    ) -> HeadingHierarchyResult:
        classified_by_span = {
            span_id: block for block in classification.blocks for span_id in block.span_ids
        }
        lines = [
            list(line_spans)
            for _, line_spans in groupby(layout.spans, key=lambda span: span.line_id)
        ]
        content_lines = [
            line for line in lines if line and min(span.page_box.y_min for span in line) >= 35
        ]
        font_sizes = [
            span.font_size for line in content_lines for span in line if span.font_size is not None
        ]
        body_size = median(font_sizes) if font_sizes else None
        candidates = self._candidates(
            content_lines,
            classified_by_span=classified_by_span,
            profile=profile,
            body_size=body_size,
        )
        return HeadingHierarchyResult(
            document_id=layout.document_id,
            headings=self._with_paths(candidates, preceding_headings),
        )

    def _candidates(
        self,
        lines: list[list[LayoutSpan]],
        *,
        classified_by_span: dict[str, BlockClassification],
        profile: DocumentProfile,
        body_size: float | None,
    ) -> list[_HeadingCandidate]:
        candidates: list[_HeadingCandidate] = []
        seen_titles: set[str] = set()
        for index, spans in enumerate(lines):
            text = normalize_pdf_text(" ".join(span.text for span in spans))
            if not text:
                continue
            classified = classified_by_span.get(spans[0].span_id)
            classified_kind = classified.kind if classified is not None else None
            if classified_kind in {"figure", "table", "warning"}:
                continue
            if WARNING_HEADING.match(text) or (
                STEP_TEXT.match(text) and classified_kind != "heading"
            ):
                continue

            rule_match = next(
                (
                    (rule, re.compile(rule.pattern).match(text))
                    for rule in profile.headings.rules
                    if re.compile(rule.pattern).match(text)
                ),
                None,
            )
            if rule_match is not None:
                rule, match = rule_match
                assert match is not None
                title = self._without_continuation(
                    match.group(0 if rule.title_group == 0 else rule.title_group)
                )
                if title:
                    candidates.append(
                        _HeadingCandidate(
                            spans=spans,
                            text=text,
                            title=title,
                            path_title=title,
                            level=rule.level,
                        )
                    )
                    seen_titles.add(title.casefold())
                continue

            service_match = SERVICE_HEADING.match(text)
            if service_match is not None:
                title = self._without_continuation(service_match.group("title"))
                path_title = self._without_continuation(text)
                candidates.append(
                    _HeadingCandidate(
                        spans=spans,
                        text=text,
                        title=title,
                        path_title=path_title,
                        level=2,
                    )
                )
                seen_titles.add(title.casefold())
                continue

            numbered_match = NUMBERED_HEADING.match(text)
            if numbered_match is not None and self._looks_like_heading_title(
                numbered_match.group("title")
            ):
                title = self._without_continuation(numbered_match.group("title"))
                level = min(6, numbered_match.group("number").count(".") + 1)
                candidates.append(
                    _HeadingCandidate(
                        spans=spans,
                        text=text,
                        title=title,
                        path_title=title,
                        level=level,
                    )
                )
                seen_titles.add(title.casefold())
                continue

            page_title_match = PRINTED_PAGE_TITLE.match(text)
            page_title = (
                page_title_match.group("title").strip() if page_title_match is not None else text
            )
            page_title = self._without_continuation(page_title)
            styled = self._is_visually_prominent(spans, body_size=body_size)
            if (
                index == 0 or styled or service_match is not None
            ) and self._looks_like_heading_title(page_title):
                if page_title.casefold() in seen_titles and index > 0:
                    continue
                candidates.append(
                    _HeadingCandidate(
                        spans=spans,
                        text=text,
                        title=page_title,
                        path_title=page_title,
                        level=1 if index == 0 else 2,
                    )
                )
                seen_titles.add(page_title.casefold())
        return candidates

    def _with_paths(
        self,
        candidates: list[_HeadingCandidate],
        preceding_headings: Sequence[HeadingNode],
    ) -> list[HeadingNode]:
        nodes: list[HeadingNode] = []
        stack = list(preceding_headings)
        for candidate in candidates:
            while stack and stack[-1].level >= candidate.level:
                stack.pop()
            path = (list(stack[-1].heading_path) if stack else []) + [candidate.path_title]
            parent_id = stack[-1].heading_id if stack else None
            span_id = candidate.spans[0].span_id
            node = HeadingNode(
                heading_id=f"{span_id}:heading",
                title=candidate.title,
                level=candidate.level,
                heading_path=path,
                source_span_ids=[span.span_id for span in candidate.spans],
                parent_heading_id=parent_id,
            )
            nodes.append(node)
            stack.append(node)
        return nodes

    @staticmethod
    def _without_continuation(text: str) -> str:
        return CONTINUED_TITLE.sub("", text).strip()

    @staticmethod
    def _looks_like_heading_title(text: str) -> bool:
        cleaned = text.strip()
        if not cleaned or len(cleaned) > 120 or len(cleaned.split()) > 16:
            return False
        if TERMINAL_SENTENCE.search(cleaned):
            return False
        return any(character.isalpha() for character in cleaned)

    @staticmethod
    def _is_visually_prominent(
        spans: list[LayoutSpan],
        *,
        body_size: float | None,
    ) -> bool:
        if any(
            span.bold or (span.font_weight is not None and span.font_weight >= 600)
            for span in spans
        ):
            return True
        return body_size is not None and any(
            span.font_size is not None and span.font_size >= body_size + 1.5 for span in spans
        )
