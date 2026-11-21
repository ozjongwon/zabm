# 08: Retrieval-smoke audit and source-pack freeze

**What to build:** A frozen, defensible source pack selected before answer-accuracy work. Each candidate has an auditable inclusion or exclusion decision, and the retained pack passes a fixed retrieval-only smoke test at the required Recall@5 threshold on at least one predeclared path.

**Blocked by:** 07.

**Status:** ready-for-agent

- [ ] Every candidate records its authority, public-availability, extraction, page-alignment, heading, table, warning, and procedure-order checks.
- [ ] A fixed retrieval-only smoke set covers specification, compatibility, and procedure evidence without running answer-accuracy baselines.
- [ ] At least one predeclared retrieval path reaches 85% Recall@5, and results are recorded separately for every tested path.
- [ ] Candidate inclusion and exclusion decisions record the metrics and reasons supporting each decision.
- [ ] The source pack, source manifest, smoke set, retrieval configuration, and smoke results are frozen together before any answer-accuracy baseline.
- [ ] Documents are not removed merely because later answer baselines perform poorly.
- [ ] A source update requires an explicit manifest change, maintainer review, and complete evaluation rerun.
- [ ] CLI-seam tests verify the frozen manifest, retrieval-smoke report, threshold decision, and rejection of an unreviewed source change.

