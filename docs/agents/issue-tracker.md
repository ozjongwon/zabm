# GitHub Issue Tracker

Issues for this repo live in GitHub Issues at https://github.com/ozjongwon/zabm/issues.

## Workflow

### For Skills
- `to-tickets`: Creates GitHub issues for planning tasks
- `triage`: Moves issues through state machine using labels
- `to-spec`: Publishes specs to GitHub issues
- `wayfinder`: Creates decision tickets on GitHub with blocking links

### For Humans
- Create issues via GitHub web interface or `gh issue create` (once CLI is installed)
- Use the five canonical triage labels for issue lifecycle management
- Link issues to commits and pull requests

## GitHub Labels Required

Create these labels in the GitHub repository:

- `needs-triage`: New issues that need assessment
- `needs-info`: Issues missing required information
- `ready-for-agent`: Issues ready for implementation
- `ready-for-human`: Issues needing human decision/input
- `wontfix`: Issues that won't be addressed

## PRs as Request Surface

**PRs are NOT included in the triage queue** by default. External contributions should be handled through GitHub's standard PR workflow.

## Local Specs Backup

Detailed specifications and planning documents are kept in `.scratch/` as backup and for complex planning tasks that don't fit well in GitHub's issue format.