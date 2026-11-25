# Multilingual reviewed output

Status: ready-for-agent
Published: 2026-11-25

## Problem Statement

The current reviewed translation implementation is Korean-specific. Language
codes, environment variables, script detection, display labels, sample artifacts,
and review metadata all assume Korean. The LLM already can translate arbitrary
text, but the application cannot request, validate, enable, or render another
reviewed language without code changes.

Using arbitrary unreviewed model translation would remove the hard-coded Korean
assumptions, but it would also remove the safety boundary that prevents an
unchecked answer from being presented as reviewed fluent output. Translation
quality, terminology, refusal language, safety warnings, and values must be
reviewed separately for each enabled output language.

## Solution

Make localization language-neutral and profile-driven. English remains built in.
Every other output language is represented by a versioned profile containing a
separately authored sample set, language-specific display labels, and a
hash-bound review record. The semantic router reports the question language;
`auto` selects that language as the requested output language, while an explicit
BCP 47 language tag overrides detection.

The LLM translates only application-validated canonical prose. Application code
continues to own values, units, conditions, statuses, compatibility outcomes,
warnings, citations, claim IDs, and final acceptance. A language without an
approved profile, or a translation that fails structural validation, falls back
to the canonical English answer.

## Requirements

1. Support output language tags beyond English and Korean without changing
   source code for each language.
2. Keep translation disabled by default for every language except English.
3. Represent each non-English language with a separately reviewed sample set
   and a review record bound to the exact sample-set hash.
4. Require every language sample set to cover specification, compatibility,
   procedure, clarification, not-found, conflicting-evidence, and out-of-scope
   outcomes.
5. Select the requested output language from an explicit BCP 47 tag or from the
   semantic router's detected question language when `--language auto` is used.
6. Preserve canonical claim IDs, counts, values, units, conditions, statuses,
   compatibility outcomes, procedure warnings, citation references, and
   conflict structure in every accepted translation.
7. Reject target-language prose when the translator reports a different target
   tag, changes canonical structure, adds unsupported content, or returns text
   that does not satisfy the profile's language checks.
8. Return the canonical English answer whenever the target profile is
   unavailable, unapproved, disabled, or translation validation fails.
9. Render localized answer prose and labels in both CLI and web adapters from
   the same canonical service.
10. Report review and evaluation results independently per language; they must
    not alter the v1 English acceptance gates.
11. Preserve the existing Korean sample content and review history through an
    explicit migration to the generic profile layout.

## Language profile contract

The implementation should use one directory per normalized BCP 47 tag:

```text
data/localization/<language-tag>/
├── profile.json
├── sample-set-v1.json
└── review-v1.json
```

`profile.json` identifies the language tag, human-readable display name, display
labels needed by adapters, and any script or language-identification checks used
to reject obviously wrong output. The sample set and review record must be
separate artifacts so the review can bind to the sample bytes.

The exact schema is an implementation decision, but it must reject path
traversal, duplicate language tags, unresolved tags, and review records whose
sample hash or language tag does not match the active profile.

## Implementation Decisions

- Extend semantic routing with a validated question-language field rather than
  inferring every language through hard-coded script tests.
- Keep English as the built-in canonical output and the universal fallback.
- Keep translation output separate from canonical English fields; do not mutate
  application-owned values, outcomes, warnings, or citations.
- Use a profile-level language check plus the reviewed sample set. Do not claim
  that a model's self-reported language tag alone proves translation quality.
- Allow deployment to restrict which approved profiles are active.
- Generalize the existing `korean-review` command and `ZABM_KOREAN_*`
  configuration rather than adding one command and flag set per language.
- Migrate Korean artifacts and tests without weakening the existing pending
  review requirement.

## Testing Decisions

- Use the CLI command surface as the automated seam.
- Use deterministic fake providers to exercise accepted and rejected
  translations for at least two non-English language tags.
- Verify automatic selection from the router, explicit-language overrides,
  unsupported-language fallback, disabled-profile fallback, invalid review
  fallback, and structural-change fallback.
- Verify reviewed sample coverage, review hash binding, and independent
  per-language reporting.
- Exercise the web adapter manually against the same canonical responses; do
  not add a second web-specific answer or validation path.

## Out of Scope

- Automatically approving new languages from model output alone.
- Shipping reviewed profiles for every possible language.
- Translating manufacturer identifiers, source titles, or citation locators into
  values used for matching or evidence ownership.
- Changing English answer semantics, evidence gates, or v1 acceptance results.
- Speech input, speech output, or automatic language detection without the
  semantic model provider.
