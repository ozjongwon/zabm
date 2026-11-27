# 01: Pre-commit hooks setup

**What to build:** Set up pre-commit hooks to automatically run linting and type checking before commits, preventing regressions from reaching the repository.

**Blocked by:** None.

**Status:** ready-for-agent

- [ ] Install pre-commit package and configuration
- [ ] Create `.pre-commit-config.yaml` with ruff lint, ruff format, and pyright hooks
- [ ] Install pre-commit hooks in the repository
- [ ] Test that hooks prevent committing code with lint/type issues
- [ ] Document the pre-commit setup in AGENTS.md
- [ ] Ensure hooks work with the existing development environment

**Type:** task

**Priority:** high

## Comments

- 2026-11-27: Identified as high-priority improvement to prevent regressions before commits
- Leverages existing excellent ruff and pyright configuration
- Low effort, high impact for code quality