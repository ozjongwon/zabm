from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from zabm.providers import ModelProvider, ProviderError
from zabm.response import EvidenceIntent, RouteEntity, RoutingMetadata

ROUTING_VERSION = "structured-intent-v1"
QuestionIntent = Literal[
    "specification",
    "compatibility",
    "procedure",
    "out_of_scope",
    "ambiguous",
]
WORD_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
PROCEDURE_REQUEST = re.compile(r"\b(?:procedure|steps?|walk\s+me\s+through)\b", re.IGNORECASE)
ROUTING_PROTOTYPES: dict[EvidenceIntent, tuple[str, ...]] = {
    "specification": (
        "what torque should be used for this component",
        "what is the specified value for this fastener",
        "what is the tightening value for this component",
        "which specification applies to this model and component",
        "give me the exact measurement and unit",
        "what pressure does this suspension component require",
        "welches drehmoment gilt für diese komponente",
        "quel couple faut-il appliquer à cette pièce",
        "¿qué par de apriete se usa para este componente?",
        "この部品のトルクはいくつですか",
        "이 부품의 토크는 얼마입니까",
    ),
    "compatibility": (
        "can i use this component with that component",
        "can this component be used with that model",
        "are these two parts compatible",
        "does the manufacturer approve this component for that model",
        "is this part approved for that model",
        "will these components work together",
        "is it safe to pair this part with that part",
        "does this hose fit that lever",
        "kann ich diese komponente mit jener komponente verwenden",
        "ces deux pièces sont-elles compatibles",
        "¿son compatibles estas dos piezas?",
        "この部品とその部品は互換性がありますか",
        "이 부품과 저 부품은 호환됩니까",
    ),
    "procedure": (
        "what are the steps to service this component",
        "how do i replace this component",
        "how do i check or inspect this component",
        "how do i install or fit this hose",
        "how do i adjust or shorten this hose",
        "how do i bleed or service this mechanism",
        "show me the steps to remove and install the part",
        "list the ordered steps and attached warnings",
        "walk me through servicing this mechanism",
        "what should happen when testing this mechanism",
        "what are the steps for fitting this component",
        "what is the procedure for servicing this component",
        "walk me through adjusting the mechanism",
        "replace the component",
        "wie tausche ich diese komponente aus",
        "comment remplacer cette pièce",
        "¿cómo se sustituye este componente?",
        "この部品を交換する手順を教えてください",
        "이 부품을 교체하는 절차를 알려주세요",
    ),
    "out_of_scope": (
        "what bicycle should i buy",
        "help me choose a bike for commuting",
        "what size bicycle frame fits my body",
        "recommend cycling shoes or a helmet",
        "make me a training or workout plan",
        "how can i ride faster or improve my technique",
        "change the ebike motor firmware",
        "answer from a photo or uploaded image",
        "upload a photo and identify a bicycle part",
        "search the web for this answer",
        "what is the capital of france",
    ),
}
ROUTING_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "do",
    "does",
    "for",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "should",
    "that",
    "the",
    "these",
    "this",
    "to",
    "two",
    "use",
    "used",
    "what",
    "which",
    "with",
}


class RequestRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: QuestionIntent
    normalized_question: str = Field(min_length=1, max_length=1000)
    entities: list[RouteEntity] = Field(
        default_factory=list[RouteEntity],
        max_length=32,
    )
    missing_fields: list[str] = Field(default_factory=list[str], max_length=20)
    ambiguous_fields: list[str] = Field(default_factory=list[str], max_length=20)
    candidate_intents: list[EvidenceIntent] = Field(
        default_factory=list[EvidenceIntent],
        max_length=4,
    )


class IntentRouter(Protocol):
    @property
    def strategy(self) -> Literal["model", "prototype"]: ...

    def route(self, question: str) -> RequestRoute: ...


class ModelIntentRouter:
    def __init__(self, provider: ModelProvider) -> None:
        self._provider = provider

    @property
    def strategy(self) -> Literal["model"]:
        return "model"

    def route(self, question: str) -> RequestRoute:
        system_content = (
            "request-routing: Classify this bicycle-maintenance request by meaning, "
            "not by matching a word list. Return only a JSON object with intent, "
            "normalized_question, entities, missing_fields, ambiguous_fields, and "
            "candidate_intents. intent is specification, compatibility, procedure, "
            "out_of_scope, or ambiguous. normalized_question must preserve the "
            "meaning as a concise English evidence query. entities have kind and "
            "text; kind is manufacturer, model, component, attribute, side, task, "
            "component_a, component_b, or other. Do not choose statuses, outcomes, "
            "citations, completeness, or answer text."
        )
        raw = self._provider.complete(
            [
                {"role": "system", "content": system_content},
                {
                    "role": "user",
                    "content": json.dumps({"question": question}, ensure_ascii=False),
                },
            ],
            seed=0,
        )
        try:
            route = RequestRoute.model_validate_json(raw)
        except ValidationError as exc:
            raise ProviderError("provider returned an invalid request-routing result") from exc
        if not route.normalized_question.strip():
            raise ProviderError("provider returned an empty normalized routing query")
        return route


class PrototypeIntentRouter:
    @property
    def strategy(self) -> Literal["prototype"]:
        return "prototype"

    def route(self, question: str) -> RequestRoute:
        scores: dict[EvidenceIntent, float] = {
            intent: max(_similarity(question, exemplar) for exemplar in exemplars)
            for intent, exemplars in ROUTING_PROTOTYPES.items()
        }
        ranked: list[tuple[EvidenceIntent, float]] = sorted(
            scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        best_intent, best_score = ranked[0]
        second_score = ranked[1][1]
        if PROCEDURE_REQUEST.search(question) and scores["procedure"] >= 0.12:
            return RequestRoute(
                intent="procedure",
                normalized_question=question.strip(),
            )
        if best_score < 0.12 or best_score - second_score < 0.012:
            candidates: list[EvidenceIntent] = [
                intent for intent, score in ranked if score >= max(0.12, best_score - 0.035)
            ]
            return RequestRoute(
                intent="ambiguous",
                normalized_question=question.strip(),
                candidate_intents=candidates,
            )
        return RequestRoute(
            intent=best_intent,
            normalized_question=question.strip(),
        )


def routing_metadata(
    route: RequestRoute,
    strategy: Literal["model", "prototype"],
) -> RoutingMetadata:
    return RoutingMetadata(
        routing_version=ROUTING_VERSION,
        strategy=strategy,
        intent=route.intent,
        normalized_question=route.normalized_question.strip(),
        entities=route.entities,
        missing_fields=route.missing_fields,
        ambiguous_fields=route.ambiguous_fields,
        candidate_intents=route.candidate_intents,
    )


def _similarity(question: str, exemplar: str) -> float:
    return _cosine(_word_counts(question), _word_counts(exemplar))


def _word_counts(text: str) -> Counter[str]:
    return Counter(
        word for word in WORD_PATTERN.findall(text.casefold()) if word not in ROUTING_STOPWORDS
    )


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(count * right.get(gram, 0) for gram, count in left.items())
    left_norm = math.sqrt(sum(count * count for count in left.values()))
    right_norm = math.sqrt(sum(count * count for count in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
