# 15: Web chat adapter

**What to build:** A minimal local web chat where a portfolio viewer can ask bicycle maintenance questions and inspect the same canonical responses produced by the CLI, including supported claims, citations, clarification, conflicts, and terminal refusals.

**Blocked by:** 05, 06, 09.

**Status:** ready-for-agent

- [ ] The web chat accepts a maintenance question and renders the canonical application-service response.
- [ ] The web UI has no separate answer path, retrieval path, evidence gate, compatibility decision, or numerical verification logic.
- [ ] Supported answers display document, printed page, section, retrieval date, claims, and compatibility outcome where applicable.
- [ ] Clarification, conflict, not-found, and out-of-scope outcomes render without substantive answer text or substituted components.
- [ ] Conflict responses display all applicable sources and any cited precedence explanation.
- [ ] Internal structured output retains physical page information and the complete response envelope.
- [ ] The local application can be started through a documented command and demonstrates the same answer, citation, and refusal behavior as the CLI.
- [ ] The acceptance procedure exercises representative supported and refused questions through both CLI and web without introducing a second automated test seam.

