# 09: Verified coverage for the frozen pack

**What to build:** Answerable coverage across every document in the frozen source pack. Representative CLI questions return human-verified specifications and compatibility rules from structured evidence and complete procedures from retrieval evidence, with unsupported or figure-only material remaining unavailable.

**Blocked by:** 08.

**Status:** resolved

- [x] Every specification and compatibility rule intended to support an answer is checked by a human against its original manufacturer document.
- [x] Every verified specification includes its unit and all source-defined applicability conditions.
- [x] Every compatibility rule is explicit manufacturer evidence and cannot be replaced by dimensional or geometric comparison.
- [x] Every answerable service procedure is established from a complete source-defined procedure section with all warnings and order preserved.
- [x] Figure-only content is answerable only after a human transcribes it into text with an exact citation and verifies the transcription.
- [x] Content without adequate, verified, or complete evidence remains unanswerable and is inspectable as such.
- [x] Representative CLI questions and evidence inspection demonstrate every question family from the frozen pack.
- [x] CLI-seam tests verify representative accepted claims, citations, and rejected unverified evidence across all frozen documents.

## Comments

- 2026-11-23: Added verified coverage for all six frozen documents: five
  specifications and four compatibility rules, each with units or explicit
  conditions and exact physical-page citations. Added representative CLI cases
  for specification, compatibility, and complete-procedure answers, plus
  per-document rejection cases.
- 2026-11-23: Added `zabm coverage`, backed by
  `data/coverage/coverage-v1.json`. It runs the same application service and
  checks observed claim IDs and citation locators. Its report inventories
  structured-evidence eligibility and every partial procedure candidate, and
  marks the figure-only Reverb AXS tool torque as unanswerable until transcribed
  and verified.
- 2026-11-23: CLI tests cover all six frozen documents, accepted claims and
  citations, unverified evidence rejection, the figure-only refusal, and a
  failure when any source has no accepted coverage case.

