# 08: Retrieval-smoke audit and source-pack freeze

**What to build:** A frozen, defensible source pack selected before answer-accuracy work. Each candidate has an auditable inclusion or exclusion decision, and the retained pack passes a fixed retrieval-only smoke test at the required Recall@5 threshold on at least one predeclared path.

**Blocked by:** 07.

**Status:** resolved

- [x] Every candidate records its authority, public-availability, extraction, page-alignment, heading, table, warning, and procedure-order checks.
- [x] A fixed retrieval-only smoke set covers specification, compatibility, and procedure evidence without running answer-accuracy baselines.
- [x] At least one predeclared retrieval path reaches 85% Recall@5, and results are recorded separately for every tested path.
- [x] Candidate inclusion and exclusion decisions record the metrics and reasons supporting each decision.
- [x] The source pack, source manifest, smoke set, retrieval configuration, and smoke results are frozen together before any answer-accuracy baseline.
- [x] Documents are not removed merely because later answer baselines perform poorly.
- [x] A source update requires an explicit manifest change, maintainer review, and complete evaluation rerun.
- [x] CLI-seam tests verify the frozen manifest, retrieval-smoke report, threshold decision, and rejection of an unreviewed source change.

## Comments

- 2026-11-23: Audited eight local candidates and froze six included sources
  from three manufacturers. The reviewed set contains 149 text-aligned pages,
  451 table rows, 21 warnings, 55 procedure candidates, and two complete
  source-defined procedures. Candidate checks, exclusions, per-path smoke
  metrics, and reasons are recorded in
  `data/audits/source-pack-candidates-v1.json`.
- 2026-11-23: Added a fixed 16-item retrieval-only smoke set spanning
  specification, compatibility, and procedure evidence. The page BM25 path
  reached 100% Recall@5 (16/16); the token-overlap comparison reached 68.8%
  (11/16). Both are recorded independently in
  `data/retrieval-smoke/report-v1.json`, and the threshold decision passes with
  one required passing path at or above 85%.
- 2026-11-23: Froze the manifest, smoke set, retrieval configuration, and
  report in `data/manifests/source-pack-freeze-v1.json`, with the reviewed
  candidate audit hash bound into the same descriptor. Normal ingestion and
  the default smoke command now verify that descriptor before writing evidence
  and fail closed on any unreviewed source-pack change.

