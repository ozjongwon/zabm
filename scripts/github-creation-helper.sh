#!/bin/bash

# GitHub Issues Manual Creation Helper
# This script provides step-by-step instructions for creating GitHub issues manually

set -e

echo "🚀 GitHub Issues Manual Creation Helper"
echo "====================================="
echo ""

echo "📋 High Priority Tickets (Create These First):"
echo ""

# High priority tickets
echo "1. Pre-commit hooks setup"
echo "   File: .scratch/coding-environment-improvements/issues/01-pre-commit-hooks-setup.md"
echo "   Priority: high"
echo "   Labels: needs-triage, priority-high, ready-for-agent"
echo "   Dependencies: None"
echo ""

echo "2. Test infrastructure investigation"
echo "   File: .scratch/coding-environment-improvements/issues/03-test-infrastructure-investigation.md"
echo "   Priority: high"
echo "   Labels: needs-triage, priority-high, ready-for-agent"
echo "   Dependencies: None"
echo ""

echo "3. AGENTS.md navigation enhancement"
echo "   File: .scratch/coding-environment-improvements/issues/02-agents-md-navigation-enhancement.md"
echo "   Priority: high"
echo "   Labels: needs-triage, priority-high, ready-for-agent"
echo "   Dependencies: None"
echo ""

echo "4. Language profile contract and Korean migration"
echo "   File: .scratch/multilingual-reviewed-output/issues/01-language-profile-contract-and-korean-migration.md"
echo "   Priority: high"
echo "   Labels: needs-triage, ready-for-agent"
echo "   Dependencies: None"
echo ""

echo "📋 Medium Priority Tickets:"
echo ""

# Medium priority tickets
echo "5. Test file organization analysis"
echo "   File: .scratch/coding-environment-improvements/issues/04-test-file-organization-analysis.md"
echo "   Priority: medium"
echo "   Labels: needs-triage, priority-medium, ready-for-agent"
echo "   Dependencies: 03-test-infrastructure-investigation"
echo ""

echo "6. Integration test scenarios definition"
echo "   File: .scratch/coding-environment-improvements/issues/05-integration-test-scenarios-definition.md"
echo "   Priority: medium"
echo "   Labels: needs-triage, priority-medium, ready-for-agent"
echo "   Dependencies: 03-test-infrastructure-investigation, 04-test-file-organization-analysis"
echo ""

echo "7. CI pipeline setup"
echo "   File: .scratch/coding-environment-improvements/issues/06-ci-pipeline-setup.md"
echo "   Priority: medium"
echo "   Labels: needs-triage, priority-medium, ready-for-agent"
echo "   Dependencies: 01-pre-commit-hooks-setup, 03-test-infrastructure-investigation"
echo ""

echo "8. Dynamic question-language routing"
echo "   File: .scratch/multilingual-reviewed-output/issues/02-dynamic-question-language-routing.md"
echo "   Priority: medium"
echo "   Labels: needs-triage, ready-for-agent"
echo "   Dependencies: 01-language-profile-contract-and-korean-migration"
echo ""

echo "📋 Low Priority Tickets:"
echo ""

# Low priority tickets
echo "9. Enhanced acceptance testing"
echo "   File: .scratch/coding-environment-improvements/issues/07-enhanced-acceptance-testing.md"
echo "   Priority: low"
echo "   Labels: needs-triage, ready-for-agent"
echo "   Dependencies: 05-integration-test-scenarios-definition"
echo ""

echo "📋 Blocked Tickets (Create After Dependencies):"
echo ""

# Blocked tickets
echo "10. Language-neutral translation and validation"
echo "    File: .scratch/multilingual-reviewed-output/issues/03-language-neutral-translation-validation.md"
echo "    Priority: medium"
echo "    Labels: needs-triage, ready-for-agent"
echo "    Dependencies: 01-language-profile-contract-and-korean-migration, 02-dynamic-question-language-routing"
echo ""

echo "11. Per-language review and activation"
echo "    File: .scratch/multilingual-reviewed-output/issues/04-per-language-review-and-activation.md"
echo "    Priority: medium"
echo "    Labels: needs-triage, ready-for-agent"
echo "    Dependencies: 01-language-profile-contract-and-korean-migration, 03-language-neutral-translation-validation"
echo ""

echo "12. Language-neutral CLI and web rendering"
echo "    File: .scratch/multilingual-reviewed-output/issues/05-language-neutral-cli-and-web-rendering.md"
echo "    Priority: medium"
echo "    Labels: needs-triage, ready-for-agent"
echo "    Dependencies: 01-language-profile-contract-and-korean-migration, 03-language-neutral-translation-validation, 04-per-language-review-and-activation"
echo ""

echo "13. Cross-language acceptance and review guide"
echo "    File: .scratch/multilingual-reviewed-output/issues/06-cross-language-acceptance-and-review-guide.md"
echo "    Priority: medium"
echo "    Labels: needs-triage, ready-for-agent"
echo "    Dependencies: 01-language-profile-contract-and-korean-migration, 02-dynamic-question-language-routing, 03-language-neutral-translation-validation, 04-per-language-review-and-activation, 05-language-neutral-cli-and-web-rendering"
echo ""

echo "🎯 Creation Instructions:"
echo "========================="
echo ""

echo "1. Open GitHub: https://github.com/ozjongwon/zabm/issues"
echo "2. Click 'New issue'"
echo "3. For each ticket above:"
echo "   a. Copy the title"
echo "   b. Click 'Write' tab and paste body content from generate-github-issue-content.sh"
echo "   c. Click 'Labels' tab and add the specified labels"
echo "   d. Click 'Create issue'"
echo "4. Record the issue number in .github-import-tracker.txt"
echo "   Format: LocalTicket:GitHubIssueNumber"
echo "   Example: echo '01-pre-commit-hooks-setup:1' >> .github-import-tracker.txt"
echo ""

echo "📝 Example for First Ticket:"
echo "==========================="
echo ""

echo "Ticket: Pre-commit hooks setup"
echo "Title: # Pre-commit hooks setup"
echo "Labels: needs-triage, priority-high, ready-for-agent"
echo "Body:"
echo "# Pre-commit hooks setup"
echo ""
echo "**Feature:** issues"
echo "**Original Ticket:** .scratch/coding-environment-improvements/issues/01-pre-commit-hooks-setup.md"
echo "**Type:** task"
echo "**Priority:** high"
echo "**Status:** ready-for-agent"
echo ""
echo "## Description"
echo ""
echo "- 2026-11-27: Identified as high-priority improvement to prevent regressions before commits"
echo "- Leverages existing excellent ruff and pyright configuration"
echo "- Low effort, high impact for code quality"
echo ""
echo "---"
echo "*Auto-generated from local ticket import. Please update status and labels as needed.*"
echo ""

echo "🔄 After Creating Issues:"
echo "========================="
echo ""

echo "1. Run ./scripts/track-github-import.sh to check status"
echo "2. Update local tickets with GitHub issue references"
echo "3. Set up dependencies in GitHub using 'Blocked by' feature"
echo "4. Update implementation order document with GitHub issue numbers"