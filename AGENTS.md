# AGENTS.md

How coding agents work in this repository. The linked documents are authoritative;
this page only routes you to them.

## Where to look

| When you are… | Read |
| --- | --- |
| picking, claiming, or closing a ticket | `docs/agents/issue-tracker.md` — tracker conventions and `gh` commands |
| labelling or triaging an issue | `docs/agents/triage-labels.md` — canonical label strings |
| naming a domain concept, or disagreeing with an earlier decision | `GLOSSARY.md`, then `docs/adr/` — flag conflicts instead of overriding them |
| changing implementation code | `docs/maintainability.md` — module map, extension recipes, change checklist |
| reproducing an install, ingest, evaluation, or acceptance run | `docs/operational-handoff.md` — entry point to every acceptance procedure |
| importing legacy local tickets | `docs/github-import-guide.md` |

Issue and spec conventions for this single-context repo are in `docs/agents/domain.md`.

## Ticket workflow

Issues live at https://github.com/ozjongwon/zabm/issues. Pick work from the
`ready-for-agent` label with no active blocker, high priority first, and state the
ticket title before starting. Close the issue with a comment linking the commit and
the verification you ran.

## Commands

`Makefile` holds the full target list.

- `make verify` — health, lint, typecheck, and test in one pass.
- `make lint`, `make typecheck`, `make test` — the individual gates.
- `make ingest`, `make evaluation`, `make acceptance` — artifact and acceptance runs.

## Verification

- Run tests as `./.venv/bin/pytest -q 2>&1 | tail -30`; re-run only failing tests with `--tb=short`.
- Before committing, run `./.venv/bin/pre-commit run --all-files` and confirm ruff
  check, ruff format, and pyright pass.

## Context discipline

- Locate with `rg -n` first; read only the needed range (`sed -n 'A,Bp'`). Keep any
  single file read under ~300 lines.
- Inspect changes with `git diff --stat`, then per-file diffs.
- Read JSON and fixtures through `head -c 2000` or `jq`, selecting only the keys you need.
- Spawn sub-agents with `fork_turns: "none"` and a self-contained brief.
