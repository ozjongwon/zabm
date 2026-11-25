# 15: Web chat adapter

**What to build:** A minimal local web chat where a portfolio viewer can ask bicycle maintenance questions and inspect the same canonical responses produced by the CLI, including supported claims, citations, clarification, conflicts, and terminal refusals.

**Blocked by:** 05, 06, 09.

**Status:** resolved

- [x] The web chat accepts a maintenance question and renders the canonical application-service response.
- [x] The web UI has no separate answer path, retrieval path, evidence gate, compatibility decision, or numerical verification logic.
- [x] Supported answers display document, printed page, section, retrieval date, claims, and compatibility outcome where applicable.
- [x] Clarification, conflict, not-found, and out-of-scope outcomes render without substantive answer text or substituted components.
- [x] Conflict responses display all applicable sources and any cited precedence explanation.
- [x] Internal structured output retains physical page information and the complete response envelope.
- [x] The local application can be started through a documented command and demonstrates the same answer, citation, and refusal behavior as the CLI.
- [x] The acceptance procedure exercises representative supported and refused questions through both CLI and web without introducing a second automated test seam.

## Comments

- 2026-11-24: Added a stdlib-only local web adapter and `zabm web` command
  over the existing `answer_question` application service. The page renders the
  canonical envelope without evidence or answer logic and exposes the complete
  JSON for inspection. Manual acceptance compared specification and
  compatibility answers, clarification, not-found, out-of-scope, and a
  two-source conflict response against `zabm ask --json`; the CLI remains the
  sole automated test seam. Full Pyright, Ruff lint, targeted Ruff formatting,
  and 211 tests pass. Repository-wide Ruff formatting still flags pre-existing
  drift in untouched files.
- 2026-11-25: The web server now binds all IPv4 interfaces by default so other
  machines on the LAN can access it, and startup reports both loopback and
  detected network URLs. `--host 127.0.0.1` restores loopback-only binding;
  documentation notes that the web interface has no authentication.

