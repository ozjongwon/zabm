from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from zabm.compatibility import answer_compatibility
from zabm.localization import (
    KoreanTranslationError,
    load_korean_output_policy,
    resolve_output_language,
    translate_response,
)
from zabm.matching import QUESTION_TOKENS, tokens
from zabm.procedures import answer_procedure
from zabm.providers import ModelProvider, ProviderError
from zabm.response import (
    CanonicalResponse,
    Claim,
    Clarification,
    CompatibilityAnswer,
    Failure,
    LocalizationMetadata,
    RoutingMetadata,
    default_provider_identity,
)
from zabm.routing import (
    ROUTING_VERSION,
    IntentRouter,
    ModelIntentRouter,
    PrototypeIntentRouter,
    RequestRoute,
    routing_metadata,
)
from zabm.specifications import answer_specification

logger = logging.getLogger("zabm.agent")

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
    output_language: Literal["auto", "en", "ko"] = "auto",
    seed: int = 0,
    prompt_budget: int | None = None,
    router: IntentRouter | None = None,
) -> CanonicalResponse:
    response = _answer_canonical_question(
        question,
        data_dir,
        provider,
        seed=seed,
        prompt_budget=prompt_budget,
        router=router,
    )
    effective_output_language = resolve_output_language(question, output_language)
    if effective_output_language == "en":
        return response
    policy = load_korean_output_policy()
    if not policy.allowed:
        return response.model_copy(
            update={
                "localization": LocalizationMetadata(
                    requested_language="ko",
                    active_language="en",
                    status="disabled",
                    reason=policy.reason,
                )
            }
        )
    if provider is None:
        return response.model_copy(
            update={
                "localization": LocalizationMetadata(
                    requested_language="ko",
                    active_language="en",
                    status="fallback",
                    review_id=policy.review_id,
                    reason="Korean output requires a translation model; English was returned.",
                )
            }
        )
    try:
        return translate_response(response, provider, policy, seed=seed)
    except (KoreanTranslationError, ProviderError) as exc:
        return response.model_copy(
            update={
                "localization": LocalizationMetadata(
                    requested_language="ko",
                    active_language="en",
                    status="fallback",
                    review_id=policy.review_id,
                    reason=f"{exc} English was returned.",
                )
            }
        )


def _answer_canonical_question(
    question: str,
    data_dir: Path,
    provider: ModelProvider | None = None,
    *,
    seed: int = 0,
    prompt_budget: int | None = None,
    router: IntentRouter | None = None,
) -> CanonicalResponse:
    original_question = question
    if router is None:
        router = PrototypeIntentRouter() if provider is None else ModelIntentRouter(provider)
    route = router.route(question)
    response_type = route.intent
    question = route.normalized_question
    logger.debug(
        "route question=%s response_type=%s routing_version=%s",
        question,
        response_type,
        ROUTING_VERSION,
    )
    metadata = routing_metadata(route, router.strategy)
    if response_type == "out_of_scope":
        response = CanonicalResponse(
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
            routing=metadata,
            source_pack_id="not-consulted",
        )
        _log_response(response)
        return response
    if response_type == "ambiguous":
        response = _routing_clarification(
            response_type="ambiguous",
            metadata=metadata,
            missing_information=[
                "question family",
                *(
                    field
                    for field in (route.missing_fields + route.ambiguous_fields)
                    if field != "question_family"
                ),
            ],
            message=(
                "Please clarify whether you need a specification, compatibility "
                "result, or procedure."
            ),
            provider=provider,
        )
        _log_response(response)
        return response
    if route.missing_fields or route.ambiguous_fields:
        missing = [
            field.replace("_", " ") for field in route.missing_fields + route.ambiguous_fields
        ]
        response = _routing_clarification(
            response_type=response_type,
            metadata=metadata,
            missing_information=missing,
            message=f"Please identify the exact {' and '.join(missing)}.",
            provider=provider,
        )
        _log_response(response)
        return response

    response = _answer_from_valid_route(route, question, data_dir)
    response = response.model_copy(update={"routing": metadata})
    if response.status == "not_found" and router.strategy == "model":
        fallback_router = PrototypeIntentRouter()
        fallback_route = fallback_router.route(original_question)
        if (
            fallback_route.intent not in {"ambiguous", "out_of_scope"}
            and not fallback_route.missing_fields
            and not fallback_route.ambiguous_fields
        ):
            fallback_response = _answer_from_valid_route(
                fallback_route,
                fallback_route.normalized_question,
                data_dir,
            )
            if fallback_response.status == "supported":
                response = fallback_response
                question = fallback_route.normalized_question
                metadata = routing_metadata(
                    fallback_route,
                    fallback_router.strategy,
                )
                response = response.model_copy(update={"routing": metadata})
                logger.debug(
                    "route-fallback model_intent=%s fallback_intent=%s question=%s",
                    response_type,
                    fallback_route.intent,
                    fallback_route.normalized_question,
                )
    if provider is None:
        _log_response(response)
        return response
    response = response.model_copy(update={"provider": provider.identity})
    if response.status != "supported":
        _log_response(response)
        return response
    phrased = _phrase_validated_claims(
        response,
        question,
        provider,
        seed=seed,
        prompt_budget=prompt_budget,
    )
    _log_response(phrased)
    return phrased


def _answer_from_valid_route(
    route: RequestRoute,
    question: str,
    data_dir: Path,
) -> CanonicalResponse:
    if route.intent == "compatibility":
        return answer_compatibility(question, data_dir)
    if route.intent == "procedure":
        return answer_procedure(question, data_dir)
    return answer_specification(question, data_dir)


def _routing_clarification(
    *,
    response_type: Literal[
        "specification",
        "compatibility",
        "procedure",
        "ambiguous",
    ],
    metadata: RoutingMetadata,
    missing_information: list[str],
    message: str,
    provider: ModelProvider | None,
) -> CanonicalResponse:
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type=response_type,
        language="en",
        status="clarification_required",
        clarification=Clarification(
            message=message,
            missing_information=missing_information,
        ),
        provider=provider.identity if provider is not None else default_provider_identity(),
        routing=metadata,
        source_pack_id="not-consulted",
    )


def _log_response(response: CanonicalResponse) -> None:
    logger.debug(
        "response response_type=%s status=%s claims=%d citations=%d",
        response.response_type,
        response.status,
        len(response.claims),
        len(response.citations),
    )


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
        excerpt = _response_excerpt(raw)
        return _reject_generated_answer(
            response,
            "Generated answer was rejected because the model response was not valid "
            f"claim-linked JSON. Response: {excerpt}",
        )
    return _apply_generated_prose(response, generated)


def _response_excerpt(raw: str, limit: int = 500) -> str:
    compact = " ".join(raw.split())
    if not compact:
        return "<empty>"
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _apply_generated_prose(
    response: CanonicalResponse,
    generated: GeneratedProse,
) -> CanonicalResponse:
    original = {claim.claim_id: claim for claim in response.claims}
    generated_ids = [sentence.claim_id for sentence in generated.sentences]
    if len(generated_ids) != len(set(generated_ids)) or set(generated_ids) != set(original):
        expected = ", ".join(sorted(original))
        received = ", ".join(sorted(set(generated_ids)))
        return _reject_generated_answer(
            response,
            "Generated answer was rejected because claim IDs did not match. "
            f"Expected: {expected}. Received: {received or '<none>'}.",
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
