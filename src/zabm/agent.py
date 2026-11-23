from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from zabm.compatibility import answer_compatibility
from zabm.matching import QUESTION_TOKENS, tokens
from zabm.procedures import answer_procedure
from zabm.providers import ModelProvider
from zabm.response import (
    CanonicalResponse,
    Claim,
    CompatibilityAnswer,
    Failure,
    default_provider_identity,
)
from zabm.specifications import answer_specification

COMPATIBILITY_CUES = (
    "compatible",
    "compatibility",
    "fit together",
    "use together",
    "used together",
    "work together",
)
PROCEDURE_CUES = (
    "how do i ",
    "how to ",
    "procedure",
    "service steps",
    "steps",
    "walk me through",
)
PROCEDURE_ACTIONS = {
    "adjust",
    "assemble",
    "bleed",
    "disassemble",
    "install",
    "prepare",
    "remove",
    "replace",
}
BUYING_CUES = {
    "best",
    "buy",
    "buying",
    "choose",
    "purchase",
    "recommend",
    "recommendation",
}
BICYCLE_NOUNS = {
    "bicycle",
    "bike",
    "clothing",
    "component",
    "cycling",
    "frame",
    "helmet",
    "part",
    "saddle",
    "seatpost",
    "shoe",
    "shoes",
    "shifting",
}
FIT_CUES = {"fitting", "size", "sizing"}
RIDER_NOUNS = {
    "body",
    "crank",
    "frame",
    "handlebar",
    "reach",
    "rider",
    "saddle",
    "stack",
    "stem",
}
TRAINING_CUES = {"coach", "coaching"}
TRAINING_ACTIVITY_CUES = {"train", "training", "workout"}
TRAINING_CONTEXT_CUES = {"fitness", "for", "improve", "plan", "program", "race", "schedule"}
RIDING_CUES = {"ride", "riding"}
RIDING_CONTEXT_CUES = {
    "better",
    "bike",
    "bicycle",
    "corner",
    "descend",
    "faster",
    "jump",
    "position",
    "skills",
    "technique",
}
INPUT_CUES = {"audio", "image", "photo", "picture", "upload", "voice"}
WEB_CUES = {"internet", "web", "website"}
MAINTENANCE_TOKENS = (
    BICYCLE_NOUNS
    | PROCEDURE_ACTIONS
    | {
        "adjust",
        "align",
        "axle",
        "bar",
        "battery",
        "bearing",
        "bleed",
        "bolt",
        "bottom",
        "brake",
        "bracket",
        "cable",
        "caliper",
        "cassette",
        "chain",
        "charger",
        "check",
        "clamp",
        "clean",
        "cleat",
        "cog",
        "compatible",
        "compatibility",
        "controller",
        "crank",
        "derailleur",
        "disc",
        "fix",
        "fluid",
        "fork",
        "freehub",
        "grip",
        "headset",
        "hose",
        "housing",
        "hub",
        "hydraulic",
        "inspect",
        "lever",
        "light",
        "lubricate",
        "maintenance",
        "motor",
        "nipple",
        "overhaul",
        "pad",
        "pedal",
        "procedure",
        "remote",
        "repair",
        "replacement",
        "rockshox",
        "rotor",
        "saddle",
        "seat",
        "service",
        "shifter",
        "shimano",
        "shock",
        "spec",
        "specification",
        "spoke",
        "spring",
        "sram",
        "step",
        "steps",
        "suspension",
        "task",
        "tension",
        "tire",
        "tool",
        "torque",
        "true",
        "tube",
        "tyre",
        "valve",
        "wheel",
    }
)
NUMBER_PATTERN = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
PHRASING_TOKENS = QUESTION_TOKENS | {
    "according",
    "be",
    "been",
    "being",
    "eighth",
    "fifth",
    "first",
    "fourth",
    "ninth",
    "only",
    "second",
    "seventh",
    "sixth",
    "states",
    "step",
    "tenth",
    "third",
    "verified",
}


class GeneratedSentence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    text: str


class GeneratedProse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentences: list[GeneratedSentence]


def answer_question(
    question: str,
    data_dir: Path,
    provider: ModelProvider | None = None,
    *,
    seed: int = 0,
    prompt_budget: int | None = None,
) -> CanonicalResponse:
    response_type = classify_question(question)
    if response_type == "out_of_scope":
        return CanonicalResponse(
            request_id=os.urandom(16).hex(),
            timestamp=datetime.now(UTC),
            response_type="out_of_scope",
            language="en",
            status="out_of_scope",
            failure=Failure(
                code="out_of_scope",
                message=(
                    "This assistant only answers bicycle maintenance questions from the "
                    "frozen source pack."
                ),
            ),
            provider=provider.identity if provider is not None else default_provider_identity(),
            source_pack_id="not-consulted",
        )

    if response_type == "compatibility":
        response = answer_compatibility(question, data_dir)
    elif response_type == "procedure":
        response = answer_procedure(question, data_dir)
    else:
        response = answer_specification(question, data_dir)
    if provider is None:
        return response
    response = response.model_copy(update={"provider": provider.identity})
    if response.status != "supported":
        return response
    return _phrase_validated_claims(
        response,
        question,
        provider,
        seed=seed,
        prompt_budget=prompt_budget,
    )


def classify_question(
    question: str,
) -> Literal["specification", "compatibility", "procedure", "out_of_scope"]:
    if _is_out_of_scope(question):
        return "out_of_scope"
    if _is_compatibility_question(question):
        return "compatibility"
    if _is_procedure_question(question):
        return "procedure"
    return "specification"


def _phrase_validated_claims(
    response: CanonicalResponse,
    question: str,
    provider: ModelProvider,
    *,
    seed: int,
    prompt_budget: int | None,
) -> CanonicalResponse:
    prompt = {
        "question": question,
        "claims": [
            {
                "claim_id": claim.claim_id,
                "text": claim.text,
                "evidence_ids": claim.evidence_ids,
            }
            for claim in response.claims
        ],
    }
    system_content = (
        "Phrase every supplied validated claim once. Do not add advice, "
        "causes, assurances, substitutions, citations, statuses, or numbers "
        "that are absent from the claim. Return only JSON with a sentences "
        "array; each sentence must contain claim_id and text."
    )
    user_content = json.dumps(prompt, ensure_ascii=False)
    if prompt_budget is not None and len(system_content) + len(user_content) > prompt_budget:
        return _reject_generated_answer(
            response,
            "Generated answer was not requested because the phrasing prompt exceeded "
            "the frozen prompt budget.",
        )
    raw = provider.complete(
        [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        seed=seed,
    )
    try:
        generated = GeneratedProse.model_validate_json(raw)
    except ValueError:
        return _reject_generated_answer(
            response,
            "Generated answer was rejected because it was not a complete claim-linked response.",
        )
    return _apply_generated_prose(response, generated)


def _apply_generated_prose(
    response: CanonicalResponse,
    generated: GeneratedProse,
) -> CanonicalResponse:
    original = {claim.claim_id: claim for claim in response.claims}
    generated_ids = [sentence.claim_id for sentence in generated.sentences]
    if len(generated_ids) != len(set(generated_ids)) or set(generated_ids) != set(original):
        return _reject_generated_answer(
            response,
            "Generated answer was rejected because every validated claim must appear exactly once.",
        )

    phrased: list[Claim] = []
    for sentence in generated.sentences:
        claim = original[sentence.claim_id]
        text = sentence.text.strip()
        if not text:
            return _reject_generated_answer(
                response,
                "Generated answer was rejected because a substantive sentence was empty.",
            )
        generated_numbers = set(NUMBER_PATTERN.findall(text))
        claim_numbers = set(NUMBER_PATTERN.findall(claim.text))
        if not generated_numbers <= claim_numbers:
            return _reject_generated_answer(
                response,
                "Generated answer was rejected because a sentence introduced an "
                "unsupported number.",
            )
        unsupported = set(tokens(text)) - set(tokens(claim.text)) - PHRASING_TOKENS
        if unsupported:
            return _reject_generated_answer(
                response,
                "Generated answer was rejected because a sentence contained unsupported content.",
            )
        phrased.append(
            Claim(
                claim_id=claim.claim_id,
                text=text,
                evidence_ids=claim.evidence_ids,
            )
        )
    return response.model_copy(update={"claims": phrased})


def _reject_generated_answer(
    response: CanonicalResponse,
    message: str,
) -> CanonicalResponse:
    compatibility = response.compatibility
    if compatibility is not None:
        compatibility = CompatibilityAnswer(
            outcome="not_found",
            component_a=None,
            component_b=None,
            conditions=[],
        )
    return response.model_copy(
        update={
            "status": "not_found",
            "failure": Failure(code="not_found", message=message),
            "claims": [],
            "specification": None,
            "compatibility": compatibility,
            "procedure": None,
            "conflicts": None,
            "citations": [],
        }
    )


def _is_out_of_scope(question: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+", question.casefold()))
    if words & BUYING_CUES and words & BICYCLE_NOUNS:
        return True
    if words & FIT_CUES and words & RIDER_NOUNS:
        return True
    if "fit" in words and words & {"bike", "body", "rider"}:
        return True
    if words & TRAINING_CUES:
        return True
    if words & TRAINING_ACTIVITY_CUES and words & TRAINING_CONTEXT_CUES:
        return True
    if words & WEB_CUES:
        return True
    if "firmware" in words:
        return True
    if words & INPUT_CUES:
        return True
    if words & RIDING_CUES and words & RIDING_CONTEXT_CUES:
        return True
    return not words & MAINTENANCE_TOKENS


def _is_compatibility_question(question: str) -> bool:
    normalized_question = question.casefold()
    if any(cue in normalized_question for cue in COMPATIBILITY_CUES):
        return True
    return bool(
        re.search(
            r"\b(?:can|could|may|should)\b[^?]*\buse(?:d)?\b[^?]*\bwith\b",
            normalized_question,
        )
    )


def _is_procedure_question(question: str) -> bool:
    normalized_question = question.casefold()
    if any(cue in normalized_question for cue in PROCEDURE_CUES):
        return True
    first_word = normalized_question.strip().split(maxsplit=1)[0].rstrip(".,:;?!")
    return first_word in PROCEDURE_ACTIONS
