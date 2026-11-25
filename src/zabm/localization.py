from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from zabm.providers import ModelProvider
from zabm.response import (
    CanonicalResponse,
    LocalizationMetadata,
    LocalizedAnswer,
    LocalizedClaim,
    LocalizedProcedure,
    LocalizedProcedureStep,
    ProcedureWarning,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KOREAN_SAMPLE_SET = REPO_ROOT / "data" / "korean" / "sample-set-v1.json"
DEFAULT_KOREAN_REVIEW = REPO_ROOT / "data" / "korean" / "review-v1.json"
KOREAN_OUTPUT_ENV = "ZABM_KOREAN_OUTPUT"
KOREAN_SAMPLE_SET_ENV = "ZABM_KOREAN_SAMPLE_SET"
KOREAN_REVIEW_ENV = "ZABM_KOREAN_REVIEW"
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
UNIT_PATTERN = re.compile(
    r"(?<![\w.])(?:N[·.]?m|in[-·]lb|mm|cm|kg|psi|bar)(?![\w.])",
    re.IGNORECASE,
)
HANGUL_PATTERN = re.compile(r"[\uac00-\ud7a3]")
SAMPLE_FAMILIES = {
    "specification",
    "compatibility",
    "procedure",
    "clarification",
    "refusal",
}


class KoreanReviewScores(BaseModel):
    correctness: float | None = Field(default=None, ge=0, le=1)
    fluency: float | None = Field(default=None, ge=0, le=1)


class KoreanReviewChecks(BaseModel):
    values_preserved: bool
    units_preserved: bool
    conditions_preserved: bool
    statuses_preserved: bool
    warnings_preserved: bool
    citations_preserved: bool


class KoreanReview(BaseModel):
    artifact_version: Literal["korean-review-v1"]
    review_id: str = Field(min_length=1)
    language: Literal["ko"]
    sample_set_id: str = Field(min_length=1)
    sample_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["pending", "approved", "rejected"]
    reviewer: str | None = None
    reviewed_at: date | None = None
    scores: KoreanReviewScores
    checks: KoreanReviewChecks

    def approval_error(self, sample_set: KoreanSampleSet, sample_sha256: str) -> str | None:
        if self.status != "approved":
            return "Korean output is disabled until its separate review passes."
        if self.sample_set_id != sample_set.sample_set_id:
            return "Korean output is disabled because the reviewed sample set does not match."
        if self.sample_set_sha256 != sample_sha256:
            return "Korean output is disabled because the reviewed sample set has changed."
        if self.reviewer is None or not self.reviewer.strip():
            return "Korean output is disabled because the review has no named reviewer."
        if self.reviewed_at is None:
            return "Korean output is disabled because the review has no review date."
        if (
            self.scores.correctness is None
            or self.scores.fluency is None
            or self.scores.correctness < 0.95
            or self.scores.fluency < 0.95
        ):
            return "Korean output is disabled because its correctness or fluency review failed."
        if not all(self.checks.model_dump().values()):
            return "Korean output is disabled because its answer-invariant review failed."
        return None


class KoreanReferenceAnswer(BaseModel):
    claims: list[str]
    values: list[str] = Field(default_factory=list[str])
    units: list[str] = Field(default_factory=list[str])
    conditions: list[str] = Field(default_factory=list[str])
    warnings: list[str] = Field(default_factory=list[str])
    citation_pages: list[int] = Field(default_factory=list[int])
    clarification_message: str | None = None
    failure_message: str | None = None


class KoreanSampleCase(BaseModel):
    id: str = Field(min_length=1)
    family: Literal["specification", "compatibility", "procedure", "clarification", "refusal"]
    question: str = Field(min_length=1)
    expected_status: Literal[
        "supported",
        "clarification_required",
        "not_found",
        "conflicting_evidence",
        "out_of_scope",
    ]
    expected_response_type: Literal[
        "specification",
        "compatibility",
        "procedure",
        "out_of_scope",
        "ambiguous",
    ]
    korean: KoreanReferenceAnswer

    @model_validator(mode="after")
    def validate_family_shape(self) -> KoreanSampleCase:
        if self.family in {"specification", "compatibility", "procedure"}:
            if self.expected_status != "supported" or not self.korean.claims:
                raise ValueError(f"Korean {self.family} samples require supported claims")
            if not self.korean.citation_pages:
                raise ValueError(f"Korean {self.family} samples require citation pages")
        if self.family == "clarification" and (
            self.expected_status != "clarification_required"
            or self.korean.clarification_message is None
        ):
            raise ValueError("Korean clarification samples require a clarification message")
        if self.family == "refusal" and (
            self.expected_status == "supported" or self.korean.failure_message is None
        ):
            raise ValueError("Korean refusal samples require a failure message")
        korean_text = [
            *self.korean.claims,
            *self.korean.conditions,
            *self.korean.warnings,
            *(
                [self.korean.clarification_message]
                if self.korean.clarification_message is not None
                else []
            ),
            *([self.korean.failure_message] if self.korean.failure_message is not None else []),
        ]
        if not korean_text or not all(HANGUL_PATTERN.search(text) for text in korean_text):
            raise ValueError("every reviewed Korean sample string must contain Korean text")
        return self


class KoreanSampleSet(BaseModel):
    artifact_version: Literal["korean-sample-set-v1"]
    sample_set_id: str = Field(min_length=1)
    language: Literal["ko"]
    cases: list[KoreanSampleCase] = Field(min_length=5)

    @model_validator(mode="after")
    def validate_coverage(self) -> KoreanSampleSet:
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Korean sample case IDs must be unique")
        families = {case.family for case in self.cases}
        missing = SAMPLE_FAMILIES - families
        if missing:
            raise ValueError("Korean sample set is missing families: " + ", ".join(sorted(missing)))
        return self


class KoreanReviewResults(BaseModel):
    artifact_version: Literal["korean-review-results-v1"] = "korean-review-results-v1"
    sample_set_id: str
    sample_set_sha256: str
    review_id: str
    review_status: Literal["pending", "approved", "rejected"]
    enabled: bool
    reason: str | None = None
    scores: KoreanReviewScores
    checks: KoreanReviewChecks
    case_count: int
    coverage: dict[str, int]
    v1_acceptance_gate_affected: Literal[False] = False


@dataclass(frozen=True)
class KoreanOutputPolicy:
    allowed: bool
    review_id: str | None
    reason: str | None


class KoreanTranslationError(ValueError):
    pass


class TranslatedClaim(BaseModel):
    claim_id: str
    text: str


class TranslatedProcedureStep(BaseModel):
    number: int
    text: str
    warnings: list[ProcedureWarning]


class TranslatedProcedure(BaseModel):
    title: str
    steps: list[TranslatedProcedureStep]


class TranslatedAnswer(BaseModel):
    claims: list[TranslatedClaim]
    conditions: list[str]
    procedure: TranslatedProcedure | None = None
    clarification_message: str | None = None
    failure_message: str | None = None


def load_korean_output_policy(
    environ: Mapping[str, str] | None = None,
) -> KoreanOutputPolicy:
    environment = os.environ if environ is None else environ
    if environment.get(KOREAN_OUTPUT_ENV, "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return KoreanOutputPolicy(
            allowed=False,
            review_id=None,
            reason="Korean output is disabled until its separate review passes.",
        )

    sample_path = Path(environment.get(KOREAN_SAMPLE_SET_ENV, DEFAULT_KOREAN_SAMPLE_SET))
    review_path = Path(environment.get(KOREAN_REVIEW_ENV, DEFAULT_KOREAN_REVIEW))
    try:
        sample_bytes = sample_path.read_bytes()
        sample_set = KoreanSampleSet.model_validate_json(sample_bytes)
        review = KoreanReview.model_validate_json(review_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return KoreanOutputPolicy(
            allowed=False,
            review_id=None,
            reason="Korean output is disabled because its separate review is unavailable.",
        )
    sample_sha256 = hashlib.sha256(sample_bytes).hexdigest()
    approval_error = review.approval_error(sample_set, sample_sha256)
    if approval_error is not None:
        return KoreanOutputPolicy(
            allowed=False,
            review_id=None,
            reason=approval_error,
        )
    return KoreanOutputPolicy(
        allowed=True,
        review_id=review.review_id,
        reason=None,
    )


def build_korean_review_results(
    sample_set_path: Path,
    review_path: Path,
) -> KoreanReviewResults:
    sample_bytes = sample_set_path.read_bytes()
    sample_set = KoreanSampleSet.model_validate_json(sample_bytes)
    review = KoreanReview.model_validate_json(review_path.read_text(encoding="utf-8"))
    sample_sha256 = hashlib.sha256(sample_bytes).hexdigest()
    approval_error = review.approval_error(sample_set, sample_sha256)
    coverage = {
        family: sum(case.family == family for case in sample_set.cases)
        for family in sorted(SAMPLE_FAMILIES)
    }
    return KoreanReviewResults(
        sample_set_id=sample_set.sample_set_id,
        sample_set_sha256=sample_sha256,
        review_id=review.review_id,
        review_status=review.status,
        enabled=approval_error is None,
        reason=approval_error,
        scores=review.scores,
        checks=review.checks,
        case_count=len(sample_set.cases),
        coverage=coverage,
    )


def translate_response(
    response: CanonicalResponse,
    provider: ModelProvider,
    policy: KoreanOutputPolicy,
    *,
    seed: int,
) -> CanonicalResponse:
    if not policy.allowed:
        raise KoreanTranslationError(policy.reason or "Korean output is not approved")

    prompt = _translation_prompt(response)
    system_content = (
        "korean-translation: Translate the supplied canonical answer prose into natural, "
        "reviewed-quality Korean. Return only JSON with claims, conditions, procedure, "
        "clarification_message, and failure_message. Keep every claim_id, claim count, "
        "condition count, step number, step count, warning count, warning severity, "
        "numeral, unit, value, and proper technical designation exactly unchanged. Do not "
        "add advice, causes, assurances, substitutions, citations, statuses, or outcomes."
    )
    raw = provider.complete(
        [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": json.dumps(prompt, ensure_ascii=False),
            },
        ],
        seed=seed,
    )
    try:
        translated = TranslatedAnswer.model_validate_json(raw)
    except ValueError as exc:
        raise KoreanTranslationError(
            "Korean output was rejected because the model did not return valid "
            "claim-linked Korean JSON."
        ) from exc
    _validate_translation(response, translated)
    localized = LocalizedAnswer(
        claims=[
            LocalizedClaim(claim_id=claim.claim_id, text=claim.text) for claim in translated.claims
        ],
        conditions=translated.conditions,
        procedure=(
            LocalizedProcedure(
                title=translated.procedure.title,
                steps=[
                    LocalizedProcedureStep(
                        number=step.number,
                        text=step.text,
                        warnings=step.warnings,
                    )
                    for step in translated.procedure.steps
                ],
            )
            if translated.procedure is not None
            else None
        ),
        clarification_message=translated.clarification_message,
        failure_message=translated.failure_message,
    )
    return response.model_copy(
        update={
            "language": "ko",
            "localization": LocalizationMetadata(
                requested_language="ko",
                active_language="ko",
                status="translated",
                review_id=policy.review_id,
            ),
            "localized": localized,
        }
    )


def _translation_prompt(response: CanonicalResponse) -> dict[str, object]:
    conditions = _canonical_conditions(response)
    procedure = None
    if response.procedure is not None:
        procedure = {
            "title": response.procedure.title,
            "steps": [
                {
                    "number": step.number,
                    "text": step.text,
                    "warnings": [
                        {"severity": warning.severity, "text": warning.text}
                        for warning in step.warnings
                    ],
                }
                for step in response.procedure.steps
            ],
        }
    return {
        "response_type": response.response_type,
        "status": response.status,
        "claims": [{"claim_id": claim.claim_id, "text": claim.text} for claim in response.claims],
        "conditions": conditions,
        "procedure": procedure,
        "clarification_message": (
            response.clarification.message if response.clarification is not None else None
        ),
        "failure_message": response.failure.message if response.failure is not None else None,
    }


def _validate_translation(response: CanonicalResponse, translated: TranslatedAnswer) -> None:
    original_claims = {claim.claim_id: claim for claim in response.claims}
    translated_claims = {claim.claim_id: claim for claim in translated.claims}
    if len(translated_claims) != len(translated.claims) or set(translated_claims) != set(
        original_claims
    ):
        raise KoreanTranslationError("Korean output was rejected because claim IDs did not match.")
    for claim_id, original in original_claims.items():
        translated_claim = translated_claims[claim_id]
        _validate_text(translated_claim.text, original.text, label=f"claim {claim_id}")

    original_conditions = _canonical_conditions(response)
    if len(translated.conditions) != len(original_conditions):
        raise KoreanTranslationError(
            "Korean output was rejected because condition structure did not match."
        )
    for original, localized in zip(original_conditions, translated.conditions, strict=True):
        _validate_text(localized, original, label="condition")

    if response.response_type == "procedure":
        if response.procedure is None or translated.procedure is None:
            raise KoreanTranslationError(
                "Korean output was rejected because procedure structure did not match."
            )
        _validate_text(
            translated.procedure.title,
            response.procedure.title,
            label="procedure title",
        )
        if len(translated.procedure.steps) != len(response.procedure.steps):
            raise KoreanTranslationError(
                "Korean output was rejected because procedure step count did not match."
            )
        for original_step, localized_step in zip(
            response.procedure.steps,
            translated.procedure.steps,
            strict=True,
        ):
            if original_step.number != localized_step.number:
                raise KoreanTranslationError(
                    "Korean output was rejected because procedure step numbers did not match."
                )
            _validate_text(
                localized_step.text,
                original_step.text,
                label=f"procedure step {original_step.number}",
            )
            if len(localized_step.warnings) != len(original_step.warnings):
                raise KoreanTranslationError(
                    "Korean output was rejected because procedure warning count did not match."
                )
            for original_warning, localized_warning in zip(
                original_step.warnings,
                localized_step.warnings,
                strict=True,
            ):
                if original_warning.severity != localized_warning.severity:
                    raise KoreanTranslationError(
                        "Korean output was rejected because warning severity changed."
                    )
                _validate_text(
                    localized_warning.text,
                    original_warning.text,
                    label=f"procedure step {original_step.number} warning",
                )
    elif translated.procedure is not None:
        raise KoreanTranslationError("Korean output was rejected because it added a procedure.")

    _validate_optional_message(
        translated.clarification_message,
        response.clarification.message if response.clarification is not None else None,
        label="clarification message",
    )
    _validate_optional_message(
        translated.failure_message,
        response.failure.message if response.failure is not None else None,
        label="failure message",
    )

    if response.specification is not None:
        display = response.specification.value.display
        if not any(display in claim.text for claim in translated.claims):
            raise KoreanTranslationError(
                "Korean output was rejected because the canonical normalized value and unit "
                "were not preserved."
            )


def _canonical_conditions(response: CanonicalResponse) -> list[str]:
    if response.specification is not None:
        return response.specification.conditions
    if response.compatibility is not None:
        return response.compatibility.conditions
    return []


def _validate_optional_message(
    translated: str | None,
    original: str | None,
    *,
    label: str,
) -> None:
    if original is None:
        if translated is not None:
            raise KoreanTranslationError(f"Korean output was rejected because it added a {label}.")
        return
    if translated is None:
        raise KoreanTranslationError(f"Korean output was rejected because the {label} was missing.")
    _validate_text(translated, original, label=label)


def _validate_text(translated: str, original: str, *, label: str) -> None:
    clean = translated.strip()
    if not clean:
        raise KoreanTranslationError(f"Korean output was rejected because {label} was empty.")
    if HANGUL_PATTERN.search(clean) is None:
        raise KoreanTranslationError(
            f"Korean output was rejected because {label} was not Korean prose."
        )
    if Counter(NUMBER_PATTERN.findall(clean)) != Counter(NUMBER_PATTERN.findall(original)):
        raise KoreanTranslationError(
            f"Korean output was rejected because {label} changed a canonical number."
        )
    if Counter(UNIT_PATTERN.findall(clean)) != Counter(UNIT_PATTERN.findall(original)):
        raise KoreanTranslationError(
            f"Korean output was rejected because {label} changed a canonical unit."
        )
