# 05: Local grounded agent and safe request handling

**What to build:** The local open-weight reference path across all three question families. The assistant recognizes aliases, asks for the minimum missing detail through `clarification_required`, refuses false premises without substitutions, declines out-of-scope requests without searching, and lets the model route, rewrite, select procedure evidence, or phrase validated claims without taking control of evidence gates.

**Blocked by:** 02, 03, 04.

**Status:** resolved

- [x] A local OpenAI-compatible model and embedding provider can run through one provider interface used by the application service and CLI.
- [x] Responses record the provider, model, configuration, and source-pack identifiers and remain correct without remote-provider access.
- [x] Model output cannot set terminal status, compatibility outcome, citations, claim-to-evidence links, numerical validity, or procedure completeness.
- [x] A generated substantive sentence without a validated claim causes the answer to be rejected.
- [x] Model names, part numbers, common names, and reordered aliases can resolve to one canonical entity.
- [x] An ambiguous alias returns `clarification_required` and asks for the minimum identifying detail rather than selecting a nearby entity.
- [x] A false-premise part or specification returns `not_found` without an alternative component or speculative value.
- [x] Non-maintenance requests return `out_of_scope` without an evidence search or adjacent advice.
- [x] CLI-seam tests cover alias resolution, ambiguity, false premises, out-of-scope requests, invalid generated prose, and provider identity in the canonical response.

## Comments

- 2026-11-23: Added one grounded application service with deterministic offline
  and OpenAI-compatible provider paths, provider identity in every canonical
  response, token-level canonical entity matching, minimum-detail
  clarification across all three answer families, false-premise refusal, and
  scope classification before evidence or model access.
- 2026-11-23: Generated prose must map every validated claim exactly once.
  Malformed JSON, model-owned response fields, extra sentences, unsupported
  numeric values, and unsupported advice attached to a valid claim ID all
  return `not_found` with no substantive payload.
- 2026-11-23: CLI-seam tests exercise provider-backed specification,
  compatibility, and procedure phrasing, reordered part-number aliases,
  ambiguity, missing details, adjacent models, general out-of-scope requests,
  and plain-text clarification/refusal rendering. `make verify` passes with 54
  tests.

