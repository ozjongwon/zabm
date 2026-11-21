# 05: Local grounded agent and safe request handling

**What to build:** The local open-weight reference path across all three question families. The assistant recognizes aliases, asks for the minimum missing detail through `clarification_required`, refuses false premises without substitutions, declines out-of-scope requests without searching, and lets the model route, rewrite, select procedure evidence, or phrase validated claims without taking control of evidence gates.

**Blocked by:** 02, 03, 04.

**Status:** ready-for-agent

- [ ] A local OpenAI-compatible model and embedding provider can run through one provider interface used by the application service and CLI.
- [ ] Responses record the provider, model, configuration, and source-pack identifiers and remain correct without remote-provider access.
- [ ] Model output cannot set terminal status, compatibility outcome, citations, claim-to-evidence links, numerical validity, or procedure completeness.
- [ ] A generated substantive sentence without a validated claim causes the answer to be rejected.
- [ ] Model names, part numbers, common names, and reordered aliases can resolve to one canonical entity.
- [ ] An ambiguous alias returns `clarification_required` and asks for the minimum identifying detail rather than selecting a nearby entity.
- [ ] A false-premise part or specification returns `not_found` without an alternative component or speculative value.
- [ ] Non-maintenance requests return `out_of_scope` without an evidence search or adjacent advice.
- [ ] CLI-seam tests cover alias resolution, ambiguity, false premises, out-of-scope requests, invalid generated prose, and provider identity in the canonical response.

