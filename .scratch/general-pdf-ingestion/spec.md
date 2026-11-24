# General PDF ingestion and procedure extraction

Status: ready-for-agent

## Problem

The current procedure parser works for clean, single-layout documents but
produces invalid candidates from tables of contents, torque tables, figure
callouts, multilingual pages, and multi-column layouts. These heuristics are
global: small x-coordinate thresholds and broad numbered-line patterns can
misclassify unrelated text.

This creates two risks:

- A source with useful procedures produces no answer because extraction never
  forms a complete, citable procedure.
- An unsafe fragment is accepted as a procedure because layout noise looks like
  numbered steps.

## Solution

Refactor ingestion into a deterministic, layout-aware pipeline:

```text
PDF page
-> page and block classification
-> font, column, language, and reading-order extraction
-> heading and section hierarchy
-> procedure candidate and step extraction
-> procedure boundary and completeness validation
-> source-span evidence and citation verification
-> retrieval catalog
```

The pipeline must work automatically for common layouts. Documents that require
special handling use a versioned ingestion profile rather than manufacturer
conditionals in shared parser code.

## Shared invariants

- Contents, index, cover, legal, contact, advertisement, and pure table pages do
  not produce procedure steps.
- Figure callouts and page numbers are not procedure steps.
- A procedure has a recognizable section heading and contiguous numbered steps
  in source reading order.
- Step text never combines unrelated columns or languages.
- Every step evidence excerpt resolves to a stored source span with document,
  physical page, printed page, section, and layout locator.
- A procedure is complete only when its source-defined end or an approved,
  unambiguous section boundary is recorded.
- Figure-only and scanned content remains unavailable until transcribed and
  human-verified.
- Duplicate or ambiguous step numbering fails closed.
- Parser, profile, and dependency versions are recorded in generated artifacts.
- Re-ingestion uses the same CLI seam and passes cross-layout regression tests.

## Document profiles

Profiles are versioned data, not imperative manufacturer branches. A profile may
declare:

- page classification exceptions;
- expected column or language regions;
- heading patterns and hierarchy hints;
- accepted section-boundary strategy;
- table and figure exclusions;
- procedure action aliases.

Profiles are hashed and recorded in ingestion reports and retrieval artifacts.

## Out of scope

- Accepting partial or uncertain procedures to improve coverage.
- Automatically treating OCR or vision-model output as verified evidence.
- Manufacturer-specific parser code.
- Changing frozen evaluation labels without maintainer review.

## Tickets

- 01: Ingestion pipeline and profile contract.
- 02: Cross-layout regression corpus.
- 03: Page and block classification.
- 04: Layout-aware spans, columns, languages, and fonts.
- 05: Heading and section hierarchy.
- 06: Procedure candidate and step extraction.
- 08: Source-span evidence and citation verification.
- 07: Procedure boundaries and completeness.
- 11: Procedure action vocabulary and aliases.
- 10: Duplicate and continuation handling.
- 09: Figure-only, OCR, and human-transcription policy.
- 12: Ingestion diagnostics, provenance, and rebuild policy.

The cross-feature implementation order is maintained in
[`../implementation-order.md`](../implementation-order.md).
