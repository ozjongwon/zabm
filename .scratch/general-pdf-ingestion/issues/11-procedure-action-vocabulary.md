# 11: Procedure action vocabulary and aliases

**What to build:** A reviewed, language-aware vocabulary that maps user actions
such as install, fit, remove, replace, shorten, and bleed to procedure headings
without weakening manufacturer or model constraints.

**Blocked by:** 05, 06.

**Status:** ready-for-agent

- [ ] Define normalized maintenance actions and heading aliases in versioned data.
- [ ] Support relationships such as install/fitting, remove/removal, replace/replacement, and shorten/cut.
- [ ] Require all identity tokens and manufacturer/model constraints to continue matching.
- [ ] Record when an answer matched through an alias rather than literal title text.
- [ ] Prevent aliases from crossing component, revision, side, or manufacturer boundaries.
- [ ] Add tests where the intended procedure heading uses different action wording from the question.
- [ ] Add a rejection test proving a MAGURA query cannot match a RockShox procedure through an alias.

## Comments

- 2026-11-24: The source heading “Fitting and aligning the brake hose” may not
  match a user request phrased as “install the rear brake hose” even after
  extraction is fixed.
