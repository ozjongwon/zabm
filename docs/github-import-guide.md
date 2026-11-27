# GitHub Issues Batch Import Guide

This guide explains how to batch-import active tickets from `.scratch/` into GitHub Issues for better collaboration and tracking.

## 📋 Overview

The repository currently has active tickets in `.scratch/` that need to be migrated to GitHub Issues for:
- Better collaboration with team members
- Proper issue tracking and management
- Integration with GitHub workflows and automation
- Clear dependency management between tickets

## 🎯 Tickets Ready for Import

Based on the implementation order, the following tickets are ready for import:

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

## 🚀 Import Methods

### Method 1: Automated with GitHub CLI (Recommended)

```bash
# Install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install gh

# Authenticate with GitHub
gh auth login

# Run the import script
./scripts/import-github-issues.sh
```

### Method 2: Manual Web Import

```bash
# Generate issue content
./scripts/generate-github-issue-content.sh

# Copy the content and create issues manually
# 1. Go to https://github.com/ozjongwon/zabm/issues
# 2. Click 'New issue'
# 3. Paste title and body content
# 4. Add appropriate labels
# 5. Create issue
```

### Method 3: Simple Listing

```bash
# List all ready tickets
./scripts/import-github-issues-simple.sh
```

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

## 📝 Import Process

### Step 1: Prepare
1. Install GitHub CLI (if using automated method)
2. Authenticate with GitHub
3. Review the ticket list

### Step 2: Create Issues
1. Run the import script or use manual method
2. Create GitHub issues for each ready ticket
3. Add appropriate labels

### Step 3: Update Local Tickets
1. After creating each GitHub issue, update the local ticket file
2. Add `GitHub Issue: #<number>` to the ticket
3. Update status if needed

### Step 4: Set Dependencies
1. For blocked tickets, use GitHub's "Blocked by" feature
2. Link to the blocking issues
3. Update implementation order accordingly

## 🔄 Post-Import Workflow

### Issue Management
- Use GitHub Projects for visual tracking
- Apply triage labels as work progresses
- Use GitHub Discussions for design decisions

### Local Ticket Updates
- Keep local tickets as detailed specifications
- Reference GitHub issues for collaboration
- Update local tickets when work is completed

### Dependency Management
- Use GitHub's dependency tracking
- Update blocked relationships as issues progress
- Maintain the implementation order document

## 📊 Import Summary

| Feature | Tickets Ready | Priority | Dependencies |
|---------|---------------|----------|--------------|
| Coding Environment | 7 | High/Medium/Low | Test infrastructure |
| Multilingual Output | 6 | Medium | Language profile contract |
| Total | 13 | Various | Various |

## 🎯 Next Steps

1. **Immediate**: Import high-priority coding environment tickets
2. **Short-term**: Import multilingual tickets after language profile is done
3. **Ongoing**: Maintain both local specs and GitHub issues
4. **Future**: Automate import process with GitHub CLI when available

## 📚 Related Files

- `.scratch/implementation-order.md` - Authoritative work backlog
- `docs/agents/issue-tracker.md` - GitHub issue tracking workflow
- `scripts/` - Import and setup scripts
- `AGENTS.md` - Agent configuration and navigation