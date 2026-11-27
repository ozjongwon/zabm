# Issue tracker: GitHub Issues

Issues and specs for this repo live in GitHub Issues at https://github.com/ozjongwon/zabm/issues.

## Conventions

- **Primary tracking**: GitHub Issues with triage labels (see `triage-labels.md`)
- **Local specs**: Detailed specifications live in [GitHub Issues](https://github.com/ozjongwon/zabm/issues) for reference
- **Dependencies**: Use GitHub's "Blocked by" feature to manage ticket dependencies
- **Priority**: Labels indicate priority levels (`priority-high`, `priority-medium`, `priority-low`)
- **Status**: `ready-for-agent` indicates tickets ready for implementation work

## When a skill says "publish to the issue tracker"

Create a new GitHub issue using the GitHub CLI or web interface with appropriate labels and dependencies.

## When a skill says "fetch the relevant ticket"

Use `gh issue view <number>` to fetch GitHub issue details, or read the referenced issue in [GitHub Issues](https://github.com/ozjongwon/zabm/issues) for local specifications.

## Wayfinding operations

Used by `/wayfinder`. **Map** is conceptual, with GitHub Issues as the primary tracking system.

- **GitHub Issues**: Numbered tickets with labels, dependencies, and status tracking
- **Blocking**: Use GitHub's "Blocked by" feature to manage dependencies
- **Frontier**: Scan GitHub Issues for `ready-for-agent` tickets with no active blockers
- **Claim**: Assign yourself to the GitHub issue before starting work
- **Resolve**: Close the GitHub issue when work is complete, with links to relevant outputs

## GitHub CLI Commands

- `gh issue list` - List all issues
- `gh issue view <number>` - View specific issue details
- `gh issue create` - Create new issue
- `gh issue edit <number>` - Edit existing issue

## Pre-commit workflow

Before committing any change:

1. Install hooks once:
   ```bash
   ./.venv/bin/pre-commit install
   ```
2. Run all hooks on all files:
   ```bash
   ./.venv/bin/pre-commit run --all-files
   ```
3. Commit when all three hooks pass (ruff check, ruff format, pyright).

Hooks run automatically on every commit via `.git/hooks/pre-commit`.
