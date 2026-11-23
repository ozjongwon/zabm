from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from zabm.response import (
    CanonicalResponse,
    ConflictCandidate,
    ConflictReport,
    Failure,
    PrecedenceDecision,
    StoredCitation,
)


@dataclass(frozen=True)
class EvidenceCandidate:
    claim_id: str
    claim: str
    evidence_ids: tuple[str, ...]
    excerpts: tuple[str, ...]
    citations: tuple[StoredCitation, ...]
    answer_key: tuple[object, ...]
    precedence: PrecedenceDecision | None = None


@dataclass(frozen=True)
class Adjudication:
    selected: EvidenceCandidate | None
    report: ConflictReport | None


def conflicting_evidence_response(
    *,
    response_type: Literal["specification", "compatibility"],
    report: ConflictReport,
    source_pack_id: str,
) -> CanonicalResponse:
    subject = (
        "verified evidence" if response_type == "specification" else "verified compatibility rules"
    )
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type=response_type,
        language="en",
        status="conflicting_evidence",
        failure=Failure(
            code="conflicting_evidence",
            message=(
                f"Applicable {subject} disagree and no cited precedence resolves the conflict."
            ),
        ),
        conflicts=report,
        citations=[citation for candidate in report.candidates for citation in candidate.citations],
        source_pack_id=source_pack_id,
    )


def adjudicate(candidates: list[EvidenceCandidate]) -> Adjudication:
    if len(candidates) <= 1:
        return Adjudication(selected=candidates[0] if candidates else None, report=None)
    if len({candidate.answer_key for candidate in candidates}) == 1:
        return Adjudication(selected=candidates[0], report=None)

    candidate_ids = {candidate.claim_id for candidate in candidates}
    winners = [
        candidate
        for candidate in candidates
        if candidate.precedence is not None
        and set(candidate.precedence.supersedes) == candidate_ids - {candidate.claim_id}
    ]
    if len(winners) == 1:
        winner = winners[0]
        assert winner.precedence is not None
        rejected_ids = [
            candidate.claim_id for candidate in candidates if candidate.claim_id != winner.claim_id
        ]
        return Adjudication(
            selected=winner,
            report=ConflictReport(
                candidates=[
                    _conflict_candidate(
                        candidate,
                        selected=candidate.claim_id == winner.claim_id,
                    )
                    for candidate in candidates
                ],
                precedence_established=True,
                precedence=winner.precedence,
                selected_claim_id=winner.claim_id,
                rejected_claim_ids=rejected_ids,
            ),
        )

    return Adjudication(
        selected=None,
        report=ConflictReport(
            candidates=[_conflict_candidate(candidate, selected=False) for candidate in candidates]
        ),
    )


def _conflict_candidate(
    candidate: EvidenceCandidate,
    *,
    selected: bool,
) -> ConflictCandidate:
    return ConflictCandidate(
        claim_id=candidate.claim_id,
        claim=candidate.claim,
        evidence_ids=list(candidate.evidence_ids),
        excerpts=list(candidate.excerpts),
        citations=list(candidate.citations),
        selected=selected,
    )
