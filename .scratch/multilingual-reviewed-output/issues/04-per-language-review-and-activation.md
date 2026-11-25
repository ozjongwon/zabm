# 04: Per-language review and activation

**What to build:** Generalize Korean review reporting into a per-language review
and activation workflow. Operators can inspect coverage, approve a profile, and
activate it without adding language-specific application code.

**Blocked by:** 01, 03.

**Status:** ready-for-agent

- [ ] Replace `zabm korean-review` with a language-neutral command that accepts a BCP 47 tag and lists or inspects available profiles.
- [ ] Validate that each sample set covers all three answer families plus clarification, not-found, conflicting-evidence, and out-of-scope outcomes.
- [ ] Require reviewer identity, review date, correctness and fluency scores, invariant checks, and exact sample-set hash before activation.
- [ ] Support a deployment allowlist of approved language profiles so approval alone does not force enablement.
- [ ] Report per-language review and evaluation results independently with an explicit non-effect on v1 acceptance gates.
- [ ] Preserve Korean review status during migration and keep it disabled while pending.
- [ ] Add CLI-seam tests for pending, approved, rejected, hash-mismatch, incomplete sample coverage, allowlisted, and non-allowlisted profiles.
- [ ] Update runtime configuration and documentation for adding and enabling a new reviewed language.

## Comments

- 2026-11-25: Initial ticket from the multilingual reviewed-output spec.
