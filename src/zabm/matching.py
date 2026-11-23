from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

QUESTION_TOKENS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "can",
    "compatibility",
    "compatible",
    "could",
    "did",
    "do",
    "does",
    "fit",
    "for",
    "give",
    "i",
    "in",
    "is",
    "it",
    "know",
    "me",
    "my",
    "need",
    "of",
    "on",
    "or",
    "please",
    "should",
    "show",
    "spec",
    "specification",
    "standard",
    "tell",
    "these",
    "the",
    "they",
    "those",
    "to",
    "together",
    "use",
    "used",
    "value",
    "was",
    "were",
    "what",
    "which",
    "will",
    "with",
    "work",
    "would",
}


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
    return re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)?", normalized)
