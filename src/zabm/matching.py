from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

QUESTION_TOKENS = {
    "a",
    "about",
    "after",
    "an",
    "and",
    "apply",
    "applicable",
    "are",
    "allow",
    "approve",
    "approved",
    "be",
    "can",
    "compatibility",
    "compatible",
    "condition",
    "contact",
    "could",
    "did",
    "do",
    "does",
    "during",
    "exact",
    "fit",
    "for",
    "give",
    "i",
    "in",
    "installing",
    "install",
    "instruction",
    "is",
    "it",
    "its",
    "know",
    "limit",
    "list",
    "manual",
    "map",
    "me",
    "my",
    "need",
    "numbered",
    "of",
    "on",
    "or",
    "owner",
    "please",
    "provide",
    "range",
    "seating",
    "service",
    "seatpost",
    "should",
    "show",
    "spec",
    "specification",
    "specify",
    "standard",
    "statement",
    "technical",
    "tell",
    "that",
    "these",
    "the",
    "they",
    "this",
    "those",
    "to",
    "together",
    "through",
    "use",
    "used",
    "user",
    "using",
    "value",
    "was",
    "were",
    "what",
    "when",
    "which",
    "will",
    "with",
    "work",
    "would",
}
TOKEN_ALIASES = {
    "bolt": "fastener",
    "calliper": "caliper",
    "screw": "fastener",
    "tightening": "torque",
}
OMITTED_CONTEXT_TOKENS = {"mounting"}


def identity_matches(
    question: str,
    *,
    identifiers: Iterable[str],
    aliases: Iterable[str] = (),
    supporting: Iterable[str] = (),
) -> bool:
    identifiers = tuple(identifiers)
    aliases = tuple(aliases)
    supporting = tuple(supporting)
    question_tokens = set(tokens(question))
    identifier_token_sets = [set(tokens(value)) for value in identifiers if value.strip()]
    alias_token_sets = [set(tokens(value)) for value in aliases if value.strip()]
    recognized = any(
        alias_tokens and alias_tokens <= question_tokens for alias_tokens in alias_token_sets
    )
    if not recognized:
        recognized = bool(identifier_token_sets) and all(
            identifier_tokens <= question_tokens for identifier_tokens in identifier_token_sets
        )
    if not recognized:
        return False

    return not unknown_tokens(
        question,
        identifiers=identifiers,
        aliases=aliases,
        supporting=supporting,
    )


def unknown_tokens(
    question: str,
    *,
    identifiers: Iterable[str],
    aliases: Iterable[str] = (),
    supporting: Iterable[str] = (),
) -> set[str]:
    identifiers = tuple(identifiers)
    aliases = tuple(aliases)
    supporting = tuple(supporting)
    question_tokens = set(tokens(question))
    allowed = set(QUESTION_TOKENS)
    for value in [*identifiers, *aliases, *supporting]:
        allowed.update(tokens(value))
    return question_tokens - allowed


def tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"['\u2019]s\b", "", normalized)
    result: list[str] = []
    for token in re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)?", normalized):
        for part in re.split(r"[.-]", token):
            word = _singularize(part)
            if word not in OMITTED_CONTEXT_TOKENS:
                result.append(TOKEN_ALIASES.get(word, word))
    return result


def _singularize(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 4 and token.endswith("s") and not token.endswith(("is", "ss", "us")):
        return token[:-1]
    return token
