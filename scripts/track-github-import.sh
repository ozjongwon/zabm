#!/bin/bash

# GitHub Issues Import Tracker
# This script helps track which issues have been created and updates local tickets
# Run this after creating GitHub issues manually

set -e

BASE_DIR=".scratch"
TRACKER_FILE=".github-import-tracker.txt"

echo "🚀 GitHub Issues Import Tracker"
echo "==============================="
echo ""

# Initialize tracker file if it doesn't exist
if [[ ! -f "$TRACKER_FILE" ]]; then
    echo "# GitHub Issues Import Tracker" > "$TRACKER_FILE"
    echo "# Format: LocalTicket:GitHubIssueNumber" >> "$TRACKER_FILE"
    echo "" >> "$TRACKER_FILE"
    echo "📝 Tracker file created. Please add GitHub issue numbers as you create them."
    echo ""
    echo "Example format:"
    echo "01-pre-commit-hooks-setup:1"
    echo "02-agents-md-navigation-enhancement:2"
    echo ""
    exit 0
fi

# Show current tracker status
echo "📋 Current Import Status:"
echo ""
echo "Local Ticket | GitHub Issue | Status"
echo "-------------|--------------|--------"

while IFS=':' read -r local_ticket github_issue; do
    if [[ -n "$local_ticket" && -n "$github_issue" ]]; then
        local_file="$BASE_DIR/coding-environment-improvements/issues/$local_ticket.md"
        if [[ -f "$local_file" ]]; then
            echo "$local_ticket | #$github_issue | ✅ Created"
        else
            echo "$local_ticket | #$github_issue | ❌ File not found"
        fi
    fi
done < <(grep -v "^#" "$TRACKER_FILE" | grep -v "^$" | head -10)

echo ""
echo "📝 Tickets Still Needing GitHub Issues:"
echo ""

# Find tickets not yet in tracker
for ticket_file in $(find "$BASE_DIR" -name "*.md" -path "*/issues/*" -exec grep -l "\*\*Status:\*\* ready-for-agent" {} \;); do
    local_ticket=$(basename "$ticket_file" .md)
    
    # Check if ticket is already in tracker
    if ! grep -q "^$local_ticket:" "$TRACKER_FILE"; then
        feature_dir=$(dirname "$ticket_file")
        feature_name=$(basename "$feature_dir")
        
        echo "🔍 $feature_name/$local_ticket"
        echo "   File: $ticket_file"
        
        # Extract title
        title=$(head -10 "$ticket_file" | grep -E "^# [0-9]+:" | sed 's/^# \([0-9]\+\): /# /' | head -1)
        if [[ -z "$title" ]]; then
            title=$(head -5 "$ticket_file" | grep -E "^# " | head -1 | sed 's/^# //')
        fi
        
        echo "   Title: $title"
        echo ""
    fi
done

echo "🎯 Next Steps:"
echo "1. Create GitHub issues for the tickets listed above"
echo "2. Add entries to $TRACKER_FILE in format: LocalTicket:GitHubIssueNumber"
echo "3. Run this script again to see updated status"
echo "4. Update local tickets with GitHub issue references"
echo ""
echo "📝 Example GitHub Issue Creation:"
echo "1. Go to: https://github.com/ozjongwon/zabm/issues"
echo "2. Click 'New issue'"
echo "3. Use the content from generate-github-issue-content.sh"
echo "4. Add appropriate labels"
echo "5. Create issue"
echo "6. Add to tracker: echo '01-pre-commit-hooks-setup:1' >> $TRACKER_FILE"