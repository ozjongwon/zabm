# Policy Documentation Updates Summary

## 📋 Updated Documents

### 1. `docs/agents/issue-tracker.md` - COMPLETE UPDATE
**Changes Made:**
- **Title**: Changed from "Issue tracker: Local Markdown" to "Issue tracker: GitHub Issues"
- **Primary tracking**: Updated to reference GitHub Issues instead of `.scratch/` files
- **Conventions**: Updated to reflect GitHub labels, dependencies, and workflow
- **Publishing**: Changed from creating local files to creating GitHub issues
- **Fetching**: Updated to use `gh issue view` command
- **Wayfinding**: Completely rewritten for GitHub Issues workflow
- **Added GitHub CLI commands section** with essential commands

### 2. `AGENTS.md` - MINOR UPDATE
**Changes Made:**
- **Removed references** to non-existent `.scratch/github-migration-plan.md`
- **Updated implementation order** to reference GitHub Issues #1-13
- **Maintained** GitHub Issue workflow section

### 3. Unchanged Documents
- `docs/agents/triage-labels.md` - Already correct and up to date
- `docs/agents/domain.md` - No changes needed for issue tracking migration
- `docs/github-import-guide.md` - Still relevant as it documents the completed import process

## 🎯 Key Policy Changes

### Old System (Local Files)
- Issues lived in `.scratch/<feature>/issues/` directories
- Manual file-based dependency tracking
- Local status tracking with `Status:` lines
- Comments appended to files

### New System (GitHub Issues)
- Issues live in GitHub Issues at https://github.com/ozjongwon/zabm/issues
- GitHub's "Blocked by" feature for dependencies
- Label-based priority and status tracking
- Native GitHub collaboration features

## 🚀 Benefits of New System

1. **Centralized Tracking**: All issues in one place
2. **Better Collaboration**: Team can comment and track progress
3. **Dependency Management**: Native GitHub dependency features
4. **Automation Ready**: Can integrate with CI/CD workflows
5. **Visual Tracking**: GitHub Projects for visual management

## 📝 Next Steps for Team

1. **Familiarize**: Read updated `docs/agents/issue-tracker.md`
2. **Practice**: Use GitHub CLI commands listed in the documentation
3. **Adapt**: Update any internal documentation that references the old system
4. **Train**: Team training on GitHub Issues workflow and dependencies