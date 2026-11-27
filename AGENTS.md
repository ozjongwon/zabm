## Agent skills

### Issue tracker

Issues live in GitHub Issues at https://github.com/ozjongwon/zabm/issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five canonical triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context domain docs use the root `GLOSSARY.md` and `docs/adr/`. See `docs/agents/domain.md`.

### Context discipline

- Locate with `rg -n` first; read only the needed range (`sed -n 'A,Bp'`). Never read a whole file over ~300 lines.
- Run tests as `pytest -q 2>&1 | tail -30`; re-run only failing tests with `--tb=short`.
- Inspect changes with `git diff --stat`, then per-file diffs. Never print the full diff.
- Do not `cat` JSON/fixtures; use `head -c 2000` or `jq` for the keys you need.
- Spawn sub-agents with `fork_turns: "none"` and a self-contained brief.

### Key Documentation

**Development Setup**: `docs/agents/issue-tracker.md` - GitHub issue tracking workflow
**Domain Knowledge**: `GLOSSARY.md` and `docs/adr/` - Single-context domain documentation
**Migration Plan**: `.scratch/github-migration-plan.md` - GitHub migration strategy
**Implementation Order**: `.scratch/implementation-order.md` - Authoritative work backlog
