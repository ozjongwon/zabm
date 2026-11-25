# Korean output review

Korean output is an optional reviewed capability. It is disabled unless both
`ZABM_KOREAN_OUTPUT=1` is set and the configured review record approves the
exact bytes of the separately authored sample set.

## Runtime boundary

Output language defaults to `auto`. For a Korean request, the original question
is routed to a normalized English evidence query, and application code builds
the canonical English response. When reviewed Korean output is enabled, the
answer prose is translated back into Korean. The translation call receives only
the validated prose and structure. It cannot set status, compatibility outcome,
citation, evidence IDs, or final acceptance. Explicit `--language en` or
`--language ko` overrides automatic language matching.

The application rejects a translation when any of these invariants changes:

- claim IDs or claim count;
- numbers, normalized specification display, or units;
- condition count or order;
- procedure title, step numbers, step count, warning count, or warning severity;
- clarification or failure-message presence;
- use of non-Korean prose.

The canonical `status`, typed answer fields, warnings, and citation objects
remain available in the response. Accepted Korean prose is recorded separately
under `localized`; `language` becomes `ko`. The CLI renders that localized prose
with the canonical citations.

If the flag is off, the review is pending or rejected, the sample set has
changed since review, no translation provider is configured, or validation
fails, the user receives the canonical English answer. Localization metadata
records that English fallback.

## Sample set and review record

`data/korean/sample-set-v1.json` covers all three supported question families
plus clarification and refusal outcomes. It is independent of the 120-item
v1 evaluation set and acceptance report.

The review record is a JSON object with:

- `artifact_version`: `korean-review-v1`;
- `review_id`, `reviewer`, and `reviewed_at`;
- the sample-set ID and SHA-256;
- `status`: `pending`, `approved`, or `rejected`;
- correctness and fluency scores, each at least `0.95` for approval;
- checks confirming values, units, conditions, statuses, warnings, and citations
  were preserved.

The committed review is pending. Do not mark it approved until a reviewer has
checked Korean correctness and fluency and all invariant checks. Changing the
sample set requires a new SHA-256 and a new review.

Validate and report the review independently:

```bash
./.venv/bin/python -m zabm korean-review --json
```

The report includes the correctness and fluency scores, every preserved-answer
invariant check, and `v1_acceptance_gate_affected: false`. Korean review results
must not be added to or used to pass the v1 acceptance gates.

## Enabling after review

```bash
export ZABM_KOREAN_OUTPUT=1
export ZABM_KOREAN_SAMPLE_SET="$PWD/data/korean/sample-set-v1.json"
export ZABM_KOREAN_REVIEW=/path/to/approved-korean-review.json

./.venv/bin/python -m zabm ask \
  "록쇽 리버 스탠다드 리모트 클램프 볼트의 토크는 얼마입니까?" \
  --provider openai-compatible \
  --provider-url http://127.0.0.1:8000/v1 \
  --model local-open-weight-model \
  --embedding-model local-embedding-model
```

Use `--json` to inspect both canonical English fields and the accepted
`localized` Korean prose. The canonical field values and citations remain the
machine-readable source of truth.
