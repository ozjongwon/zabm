## Agent skills

### Issue tracker

**Primary tracking**: GitHub issues at https://github.com/ozjongwon/zabm/issues
**Local specs**: Detailed specifications and planning documents live under `.scratch/`. See `docs/agents/issue-tracker.md`.

### GitHub Issue Workflow

High-priority tasks are tracked as GitHub issues for collaboration and visibility:
- **Code quality**: Pre-commit hooks, CI pipeline setup
- **Testing**: Test infrastructure investigation, integration tests
- **Documentation**: AGENTS.md enhancements, migration planning

### Triage labels

Use the five canonical triage labels. See `docs/agents/triage-labels.md`.

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
**GitHub Import Guide**: `docs/github-import-guide.md` - Batch import local tickets to GitHub Issues
**Implementation Order**: GitHub Issues #1-13 - Authoritative work backlog with dependencies