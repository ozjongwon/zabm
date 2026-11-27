1|## Agent skills
2|
3|### Issue tracker
4|
5|**Primary tracking**: GitHub issues at https://github.com/ozjongwon/zabm/issues
6|**Local specs**: Detailed specifications and planning documents live under `.scratch/`. See `docs/agents/issue-tracker.md`.
7|
8|### GitHub Issue Workflow
9|
10|High-priority tasks are tracked as GitHub issues for collaboration and visibility:
11|- **Code quality**: Pre-commit hooks, CI pipeline setup
12|- **Testing**: Test infrastructure investigation, integration tests
13|- **Documentation**: AGENTS.md enhancements, migration planning
14|
15|### Triage labels

Use the five canonical triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context domain docs use the root `GLOSSARY.md` and `docs/adr/`. See `docs/agents/domain.md`.

### Context discipline

- Locate with `rg -n` first; read only the needed range (`sed -n 'A,Bp'`). Never read a whole file over ~300 lines.
- Run tests as `pytest -q 2>&1 | tail -30`; re-run only failing tests with `--tb=short`.
- Inspect changes with `git diff --stat`, then per-file diffs. Never print the full diff.
- Do not `cat` JSON/fixtures; use `head -c 2000` or `jq` for the keys you need.
- Spawn sub-agents with `fork_turns: "none"` and a self-contained brief.
