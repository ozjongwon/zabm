# 11: Procedure action vocabulary and aliases

**What to build:** A reviewed, language-aware vocabulary that maps user actions
such as install, fit, remove, replace, shorten, and bleed to procedure headings
without weakening manufacturer or model constraints.

**Blocked by:** 05, 06.

**Status:** resolved

- [x] Define normalized maintenance actions and heading aliases in versioned data.
- [x] Support relationships such as install/fitting, remove/removal, replace/replacement, and shorten/cut.
- [x] Require all identity tokens and manufacturer/model constraints to continue matching.
- [x] Record when an answer matched through an alias rather than literal title text.
- [x] Prevent aliases from crossing component, revision, side, or manufacturer boundaries.
- [x] Add tests where the intended procedure heading uses different action wording from the question.
- [x] Add a rejection test proving a MAGURA query cannot match a RockShox procedure through an alias.

## Comments

- 2026-11-24: The source heading “Fitting and aligning the brake hose” may not
  match a user request phrased as “install the rear brake hose” even after
  extraction is fixed.

- 2026-11-24: Implemented in parser `pdf-ingestion-v10`. Reviewed action
  aliases are stored in the selected versioned ingestion profile and copied to
  retrieval provenance with the profile language. Procedure matching requires
  an equivalent action plus every non-action title identity token, and keeps
  manufacturer and revision available as source constraints. Supported answers
  record literal-title or action-alias provenance with the canonical action and
  profile version. CLI-seam tests cover compound headings, the four requested
  action relationships, literal matching, profile normalization, and isolation
  across manufacturers, revisions, components, sides, and models. `make verify`
  passes with 204 tests.
