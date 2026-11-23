from __future__ import annotations

import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from zabm.matching import identity_matches, tokens, unknown_tokens
from zabm.response import (
    CanonicalResponse,
    Claim,
    Clarification,
    CompatibilityAnswer,
    CompatibilityComponent,
    Failure,
    StoredCitation,
)
from zabm.specifications import (
    CitationTarget,
    HumanVerification,
    citation_issues,
    load_source_manifest,
    load_source_pages,
    normalize_text,
    write_json,
)


class VerifiedCompatibilityRule(BaseModel):
    id: str
    component_a: CompatibilityComponent
    component_b: CompatibilityComponent
    outcome: Literal["compatible", "not_compatible", "unknown"]
    conditions: list[str]
    source_id: str
    citation: CitationTarget
    evidence_excerpts: list[str]
    verification: HumanVerification


class VerifiedCompatibilityFile(BaseModel):
    compatibility_rules: list[VerifiedCompatibilityRule]


class StoredCompatibilityRule(BaseModel):
    rule: VerifiedCompatibilityRule
    citation: StoredCitation
    validation_issues: list[str] = Field(default_factory=list[str])


class CompatibilityCatalog(BaseModel):
    source_pack_id: str
    compatibility_rules: list[StoredCompatibilityRule]


class CompatibilityIngestReport(BaseModel):
    source_pack_id: str
    compatibility_rule_count: int
    eligible_compatibility_rule_count: int
    validation_issues: list[str]


def ingest_compatibility(
    manifest_path: Path,
    evidence_path: Path,
    pdf_dir: Path,
    data_dir: Path,
) -> CompatibilityIngestReport:
    manifest = load_source_manifest(manifest_path)
    evidence = VerifiedCompatibilityFile.model_validate_json(
        evidence_path.read_text(encoding="utf-8")
    )
    sources = {source.id: source for source in manifest.sources}
    page_texts = load_source_pages(manifest, pdf_dir)

    stored: list[StoredCompatibilityRule] = []
    all_issues: list[str] = []
    for rule in evidence.compatibility_rules:
        source = sources.get(rule.source_id)
        issues: list[str] = []
        if source is None:
            issues.append(f"source {rule.source_id} is not in the manifest")
            pages: list[str] = []
        else:
            pages = page_texts[rule.source_id]
            issues.extend(citation_issues(rule.citation, rule.evidence_excerpts, pages))

        issues.extend(_eligibility_issues(rule))
        citation = StoredCitation(
            document_id=rule.source_id,
            title=source.title if source else "unknown",
            manufacturer=source.manufacturer if source else rule.component_a.manufacturer,
            printed_page=rule.citation.printed_page,
            physical_page=rule.citation.physical_page,
            section=rule.citation.section,
            retrieval_date=source.retrieval_date if source else date.min,
            source_manifest_version=manifest.manifest_version,
        )
        stored.append(
            StoredCompatibilityRule(
                rule=rule,
                citation=citation,
                validation_issues=issues,
            )
        )
        all_issues.extend(f"{rule.id}: {issue}" for issue in issues)

    catalog = CompatibilityCatalog(
        source_pack_id=manifest.manifest_version,
        compatibility_rules=stored,
    )
    generated_dir = data_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    write_json(generated_dir / "compatibility.json", catalog.model_dump(mode="json"))

    return CompatibilityIngestReport(
        source_pack_id=manifest.manifest_version,
        compatibility_rule_count=len(stored),
        eligible_compatibility_rule_count=sum(not item.validation_issues for item in stored),
        validation_issues=all_issues,
    )


def answer_compatibility(question: str, data_dir: Path) -> CanonicalResponse:
    catalog_path = data_dir / "generated" / "compatibility.json"
    if not catalog_path.is_file():
        return _not_found(
            "Compatibility data has not been ingested. Run `zabm download` and "
            "`zabm ingest` first.",
            source_pack_id="unknown",
        )

    catalog = CompatibilityCatalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
    matches = [
        item for item in catalog.compatibility_rules if _matches_question(item.rule, question)
    ]
    if not matches:
        if any(
            _has_partial_component_match(item.rule, question)
            for item in catalog.compatibility_rules
        ):
            return _clarification_response(
                ["component"],
                source_pack_id=catalog.source_pack_id,
            )
        if not unknown_tokens(question, identifiers=[], supporting=[]):
            return _clarification_response(
                ["component"],
                source_pack_id=catalog.source_pack_id,
            )
        return _not_found(
            "No human-verified manufacturer compatibility rule matches this pair.",
            source_pack_id=catalog.source_pack_id,
        )
    if len(matches) > 1:
        return _clarification_required(
            [item.rule for item in matches],
            source_pack_id=catalog.source_pack_id,
        )

    stored = matches[0]
    issues = stored.validation_issues + _eligibility_issues(stored.rule)
    if issues:
        return _not_found(
            f"Verified compatibility evidence was rejected: {issues[0]}",
            source_pack_id=catalog.source_pack_id,
        )

    rule = stored.rule
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type="compatibility",
        language="en",
        status="supported",
        claims=[
            Claim(
                claim_id=rule.id,
                text=_claim_text(rule),
                evidence_ids=[rule.id],
            )
        ],
        compatibility=CompatibilityAnswer(
            outcome=rule.outcome,
            component_a=rule.component_a,
            component_b=rule.component_b,
            conditions=rule.conditions,
        ),
        citations=[stored.citation],
        source_pack_id=catalog.source_pack_id,
    )


def _not_found(message: str, source_pack_id: str) -> CanonicalResponse:
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type="compatibility",
        language="en",
        status="not_found",
        failure=Failure(code="not_found", message=message),
        compatibility=CompatibilityAnswer(
            outcome="not_found",
            component_a=None,
            component_b=None,
            conditions=[],
        ),
        source_pack_id=source_pack_id,
    )


def _clarification_required(
    rules: list[VerifiedCompatibilityRule],
    *,
    source_pack_id: str,
) -> CanonicalResponse:
    missing = (
        ["component pair"] if len({rule.component_b.name for rule in rules}) > 1 else ["component"]
    )
    return _clarification_response(missing, source_pack_id=source_pack_id)


def _clarification_response(
    missing: list[str],
    *,
    source_pack_id: str,
) -> CanonicalResponse:
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type="compatibility",
        language="en",
        status="clarification_required",
        clarification=Clarification(
            message=f"Please identify the exact {' and '.join(missing)}.",
            missing_information=missing,
        ),
        source_pack_id=source_pack_id,
    )


def _has_partial_component_match(rule: VerifiedCompatibilityRule, question: str) -> bool:
    supporting = [
        rule.component_a.manufacturer,
        rule.component_b.manufacturer,
        *rule.conditions,
    ]
    if unknown_tokens(
        question,
        identifiers=[rule.component_a.name, rule.component_b.name],
        aliases=[*rule.component_a.aliases, *rule.component_b.aliases],
        supporting=supporting,
    ):
        return False
    question_tokens = set(tokens(question))
    present = [
        _component_tokens_match(component, question_tokens)
        for component in (rule.component_a, rule.component_b)
    ]
    return any(present) and not all(present)


def _component_tokens_match(
    component: CompatibilityComponent,
    question_tokens: set[str],
) -> bool:
    if set(tokens(component.name)) <= question_tokens:
        return True
    return any(
        alias_tokens <= question_tokens
        for alias in component.aliases
        if (alias_tokens := set(tokens(alias)))
    )


def _eligibility_issues(rule: VerifiedCompatibilityRule) -> list[str]:
    issues: list[str] = []
    verification = rule.verification
    if verification.status != "human_verified":
        issues.append("human verification is missing")
    if not verification.verified_by.strip():
        issues.append("human verifier is missing")
    if verification.verified_at is None:
        issues.append("human verification date is missing")
    if not rule.conditions:
        issues.append("source-defined applicability conditions are missing")
    if not rule.evidence_excerpts:
        issues.append("compatibility evidence excerpt is missing")
    if not _explicit_rule_evidence(rule):
        issues.append("evidence does not contain an explicit compatibility statement")
    return issues


def _explicit_rule_evidence(rule: VerifiedCompatibilityRule) -> bool:
    evidence = normalize_text(" ".join(rule.evidence_excerpts))
    if rule.outcome == "compatible":
        return "compatible with" in evidence or "chain compatible tools" in evidence
    if rule.outcome == "not_compatible":
        return any(
            cue in evidence
            for cue in (
                "cannot be used with",
                "do not use",
                "is not compatible with",
                "must not be used with",
                "never use",
            )
        )
    return any(
        cue in evidence
        for cue in (
            "does not establish compatibility",
            "not established",
            "not specified",
            "remains unresolved",
            "unresolved",
        )
    )


def _matches_question(rule: VerifiedCompatibilityRule, question: str) -> bool:
    return identity_matches(
        question,
        identifiers=[rule.component_a.name, rule.component_b.name],
        aliases=[*rule.component_a.aliases, *rule.component_b.aliases],
        supporting=[
            rule.component_a.manufacturer,
            rule.component_b.manufacturer,
            *rule.conditions,
        ],
    )


def _claim_text(rule: VerifiedCompatibilityRule) -> str:
    if rule.outcome == "unknown":
        return f"{rule.component_a.name} compatibility with {rule.component_b.name} is unresolved."
    relationship = "is compatible with"
    if rule.outcome == "not_compatible":
        relationship = "is not compatible with"
    return f"{rule.component_a.name} {relationship} {rule.component_b.name}."
