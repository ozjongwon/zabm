#!/bin/bash

# Complete GitHub Issues Import Workflow
# This script demonstrates the complete import workflow from start to finish

set -e

echo "🚀 Complete GitHub Issues Import Workflow"
echo "========================================="
echo ""

echo "📋 Current Status:"
echo "=================="
echo ""

# Check if tracker file exists
if [[ -f ".github-import-tracker.txt" ]]; then
    echo "✅ Tracker file exists"
    echo "📋 Created issues:"
    echo ""
    while IFS=':' read -r local_ticket github_issue; do
        if [[ -n "$local_ticket" && -n "$github_issue" ]]; then
            echo "   🔗 $local_ticket → #$github_issue"
        fi
    done < <(grep -v "^#" ".github-import-tracker.txt" | grep -v "^$")
    echo ""
else
    echo "❌ Tracker file not found - starting fresh import"
    echo ""
fi

echo "🎯 Workflow Steps:"
echo "=================="
echo ""

echo "Step 1: View Ready Tickets"
echo "========================="
echo "./scripts/import-github-issues-simple.sh"
echo ""

echo "Step 2: Generate Issue Content"
echo "============================="
echo "./scripts/generate-github-issue-content.sh"
echo ""

echo "Step 3: Create GitHub Issues (Manual)"
echo "===================================="
echo "1. Open: https://github.com/ozjongwon/zabm/issues"
echo "2. Click 'New issue' for each ticket"
echo "3. Use content from Step 2"
echo "4. Add appropriate labels"
echo "5. Record issue numbers in .github-import-tracker.txt"
echo ""

echo "Step 4: Track Progress"
echo "======================"
echo "./scripts/track-github-import.sh"
echo ""

echo "Step 5: Update Local Tickets"
echo "==========================="
echo "After creating issues, update local ticket files with GitHub issue numbers"
echo "Example: echo 'GitHub Issue: #1' >> .scratch/coding-environment-improvements/issues/01-pre-commit-hooks-setup.md"
echo ""

echo "Step 6: Set Dependencies"
echo "======================="
echo "Use GitHub's 'Blocked by' feature for dependent tickets"
echo "Update implementation order document with GitHub issue numbers"
echo ""

echo "📋 High Priority Tickets (Create First):"
echo "======================================="
echo ""

# High priority tickets
echo "1. Pre-commit hooks setup (high)"
echo "   Dependencies: None"
echo ""

echo "2. Test infrastructure investigation (high)"
echo "   Dependencies: None"
echo ""

echo "3. AGENTS.md navigation enhancement (high)"
echo "   Dependencies: None"
echo ""

echo "4. Language profile contract and Korean migration (high)"
echo "   Dependencies: None"
echo ""

echo "📋 Medium Priority Tickets:"
echo "==========================="
echo ""

# Medium priority tickets
echo "5. Test file organization analysis (medium)"
echo "   Dependencies: 03-test-infrastructure-investigation"
echo ""

echo "6. Integration test scenarios definition (medium)"
echo "   Dependencies: 03-test-infrastructure-investigation, 04-test-file-organization-analysis"
echo ""

echo "7. CI pipeline setup (medium)"
echo "   Dependencies: 01-pre-commit-hooks-setup, 03-test-infrastructure-investigation"
echo ""

echo "8. Dynamic question-language routing (medium)"
echo "   Dependencies: 01-language-profile-contract-and-korean-migration"
echo ""

echo "📋 Low Priority Tickets:"
echo "========================"
echo ""

# Low priority tickets
echo "9. Enhanced acceptance testing (low)"
echo "   Dependencies: 05-integration-test-scenarios-definition"
echo ""

echo "📋 Blocked Tickets (Create After Dependencies):"
echo "=============================================="
echo ""

# Blocked tickets
echo "10-13. Multilingual tickets (various dependencies)"
echo ""

echo "🎯 Next Actions:"
echo "================="
echo ""

echo "1. Run './scripts/github-creation-helper.sh' for detailed instructions"
echo "2. Start with high-priority tickets (1-4)"
echo "3. Use './scripts/track-github-import.sh' to track progress"
echo "4. Update local tickets as issues are created"
echo "5. Set up dependencies in GitHub"
echo ""

echo "📚 Documentation:"
echo "================="
echo "- docs/github-import-guide.md - Comprehensive guide"
echo "- AGENTS.md - Navigation pointers"
echo "- scripts/ - All import and tracking scripts"
echo ""

echo "✅ Workflow Complete! Ready to start importing GitHub issues."