# 09: Figure-only, OCR, and human-transcription policy

**What to build:** Explicit classification and handling for figure-only,
scanned, and image-derived procedure content. Such content must not be promoted
to answers by OCR or model inference without a human-verified transcription.

**Blocked by:** 03, 04, 08.

**Status:** resolved

- [x] Classify text-free pages, diagram-heavy instruction sheets, and callout-only procedures.
- [x] Exclude figure callouts from numbered procedure steps.
- [x] Provide an ingestion outcome for content requiring transcription rather than treating it as an ordinary partial procedure.
- [x] Define a human-transcription artifact with exact source location, reviewer, and verification date.
- [x] Permit an accepted procedure only through the verified transcription evidence plane.
- [x] Keep unverified OCR or vision output inspectable but ineligible for answers.
- [x] Add CLI-seam tests for figure-only refusal and verified-transcription acceptance.

## Comments

- 2026-11-24: MT A2 pages 1-2 are a multilingual figure-based reach-adjust sheet;
  page labels and callouts are currently misread as steps.

- 2026-11-24: Implemented in parser `pdf-ingestion-v8`. Figure-only,
  callout-only, and text-free pages report `transcription-required` without
  producing procedures. The `--transcriptions` artifact provides source-boxed,
  contiguous steps and warnings, a boundary, and named human verification;
  accepted procedures use the separate `verified-transcription` evidence plane.
  Unverified entries remain visible in page diagnostics but ineligible; invalid
  verified entries fail closed, and the artifact hash is recorded in ingestion
  provenance. See `docs/adr/0006-verified-transcription-evidence-plane.md`.
