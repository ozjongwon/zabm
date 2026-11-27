# GitHub Issues Batch Import Guide

This guide documents the completed batch-import of active tickets into GitHub Issues.

## 📋 Overview

All tickets have been migrated from `.scratch/` into GitHub Issues at https://github.com/ozjongwon/zabm/issues for:

- Better collaboration with team members
- Proper issue tracking and management
- Integration with GitHub workflows and automation
- Clear dependency management between tickets

## 🎯 Imported tickets

All 13 tickets (issues #1-13) have been imported to GitHub Issues with triage labels and dependencies:

### High Priority (ready-for-agent)
1. **Pre-commit hooks setup** - Set up pre-commit hooks for linting and type checking
2. **AGENTS.md navigation enhancement** - Improve documentation navigation
3. **Test infrastructure investigation** - Investigate and resolve test timeout issues
4. **Language profile contract and Korean migration** - Replace Korean-only profile with language-neutral contract

### Medium Priority (ready-for-agent)
5. **Test file organization analysis** - Analyze test file structure
6. **Integration test scenarios definition** - Define integration test scenarios
7. **CI pipeline setup** - Set up continuous integration
8. **Dynamic question-language routing** - Detect and select target languages

### Blocked Tickets
- Several multilingual tickets are blocked by the language profile contract work
- Integration tests are blocked by test infrastructure investigation

## 🏷️ Label Strategy

Use the following labels for imported issues:

### Priority Labels
- `priority-high` - Critical issues that block other work
- `priority-medium` - Important but not blocking
- `priority-low` - Nice to have

### Status Labels
- `needs-triage` - New issues that need assessment
- `needs-info` - Issues missing required information
- `ready-for-agent` - Issues ready for implementation
- `ready-for-human` - Issues needing human decision/input
- `wontfix` - Issues that won't be addressed

### Feature Labels
- Add feature-specific labels as needed (e.g., `multilingual`, `testing`, `ci`)

## 🔄 Post-Import Workflow

### Issue Management
- Use GitHub Projects for visual tracking
- Apply triage labels as work progresses
- Use GitHub Discussions for design decisions

### Dependency Management
- Use GitHub's dependency tracking
- Update blocked relationships as issues progress

## 📚 Related Files

- [GitHub Issues](https://github.com/ozjongwon/zabm/issues) - Authoritative work backlog
- `docs/agents/issue-tracker.md` - GitHub issue tracking workflow
- `scripts/` - Import and setup scripts
- `AGENTS.md` - Agent configuration and navigation
