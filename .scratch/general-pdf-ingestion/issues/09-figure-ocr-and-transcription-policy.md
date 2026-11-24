# 09: Figure-only, OCR, and human-transcription policy

**What to build:** Explicit classification and handling for figure-only,
scanned, and image-derived procedure content. Such content must not be promoted
to answers by OCR or model inference without a human-verified transcription.

**Blocked by:** 03, 04, 08.

**Status:** ready-for-agent

- [ ] Classify text-free pages, diagram-heavy instruction sheets, and callout-only procedures.
- [ ] Exclude figure callouts from numbered procedure steps.
- [ ] Provide an ingestion outcome for content requiring transcription rather than treating it as an ordinary partial procedure.
- [ ] Define a human-transcription artifact with exact source location, reviewer, and verification date.
- [ ] Permit an accepted procedure only through the verified transcription evidence plane.
- [ ] Keep unverified OCR or vision output inspectable but ineligible for answers.
- [ ] Add CLI-seam tests for figure-only refusal and verified-transcription acceptance.

## Comments

- 2026-11-24: MT A2 pages 1-2 are a multilingual figure-based reach-adjust sheet;
  page labels and callouts are currently misread as steps.
