#!/bin/bash

# GitHub Issues Batch Import Script
# This script reads local tickets from .scratch/ and generates GitHub issue creation commands
# Run this after setting up GitHub CLI authentication

set -e

REPO="ozjongwon/zabm"
BASE_DIR=".scratch"

echo "🚀 GitHub Issues Batch Import Script"
echo "====================================="
echo "Repository: $REPO"
echo "Base directory: $BASE_DIR"
echo ""

# Function to create GitHub issue from ticket file
create_github_issue() {
    local ticket_file="$1"
    local feature_dir="$2"
    
    echo "📋 Processing: $ticket_file"
    
    # Extract ticket metadata
    local ticket_name=$(basename "$ticket_file" .md)
    local feature_name=$(basename "$feature_dir")
    local title=$(head -10 "$ticket_file" | grep -E "^# [0-9]+:" | sed 's/^# \([0-9]\+\): /# /' | head -1)
    
    if [[ -z "$title" ]]; then
        title=$(head -5 "$ticket_file" | grep -E "^# " | head -1 | sed 's/^# //')
    fi
    
    # Extract status
    local status=$(grep -E "^Status:" "$ticket_file" | sed 's/Status: //' | tr -d ' ')
    
    # Extract priority
    local priority=$(grep -E "^Priority:" "$ticket_file" | sed 's/Priority: //' | tr -d ' ')
    
    # Extract blocked by information
    local blocked_by=$(grep -E "^Blocked by:" "$ticket_file" | sed 's/Blocked by: //' | tr -d ' ')
    
    # Extract description
    local description=$(tail -n +10 "$ticket_file" | head -20)
    
    # Create issue body
    local issue_body="# $title\n\n"
    issue_body+="**Feature:** $feature_name\n"
    issue_body+="**Original Ticket:** $ticket_file\n\n"
    issue_body+="## Description\n\n$description\n\n"
    
    if [[ -n "$blocked_by" && "$blocked_by" != "None." ]]; then
        issue_body+="## Dependencies\n\nBlocked by: $blocked_by\n\n"
    fi
    
    issue_body+="---\n"
    issue_body+="*Auto-generated from local ticket import. Please update status and labels as needed.*"
    
    # Add labels based on priority and status
    local labels=""
    if [[ "$priority" == "high" ]]; then
        labels="needs-triage,priority-high"
    elif [[ "$priority" == "medium" ]]; then
        labels="needs-triage,priority-medium"
    else
        labels="needs-triage"
    fi
    
    if [[ "$status" == "ready-for-agent" ]]; then
        labels+=",ready-for-agent"
    fi
    
    echo "📝 Title: $title"
    echo "🏷️  Labels: $labels"
    echo "🔗 Blocked by: $blocked_by"
    echo ""
    
    # Generate GitHub CLI command
    echo "🚀 To create this issue, run:"
    echo "gh issue create --title \"$title\" --label \"$labels\" --body <<'EOF'"
    echo "$issue_body"
    echo "EOF"
    echo ""
}

# Find and process all active tickets
echo "🔍 Finding active tickets in $BASE_DIR..."
echo ""

# High priority tickets ready for import
for feature_dir in "$BASE_DIR"/*/; do
    if [[ -d "$feature_dir" ]]; then
        feature_name=$(basename "$feature_dir")
        
        # Process coding-environment-improvements tickets (high priority)
        if [[ "$feature_name" == "coding-environment-improvements" ]]; then
            for ticket_file in "$feature_dir/issues/"*.md; do
                if [[ -f "$ticket_file" ]]; then
                    # Check if ticket is ready for agent
                    status=$(grep -E "^Status:" "$ticket_file" | sed 's/Status: //' | tr -d ' ')
                    if [[ "$status" == "ready-for-agent" ]]; then
                        create_github_issue "$ticket_file" "$feature_dir"
                    fi
                fi
            done
        fi
        
        # Process multilingual-reviewed-output tickets (next agent ticket)
        if [[ "$feature_name" == "multilingual-reviewed-output" ]]; then
            for ticket_file in "$feature_dir/issues/"*.md; do
                if [[ -f "$ticket_file" ]]; then
                    # Check if ticket is ready for agent
                    status=$(grep -E "^Status:" "$ticket_file" | sed 's/Status: //' | tr -d ' ')
                    if [[ "$status" == "ready-for-agent" ]]; then
                        create_github_issue "$ticket_file" "$feature_dir"
                    fi
                fi
            done
        fi
    fi
done

echo "====================================="
echo "📋 Summary:"
echo "- Found tickets ready for import"
echo "- Run the generated 'gh issue create' commands for each ticket"
echo "- After creating issues, update local ticket files with GitHub issue numbers"
echo "- Add 'GitHub Issue: #<number>' to local tickets for reference"
echo ""
echo "🔧 Manual Alternative:"
echo "1. Go to https://github.com/ozjongwon/zabm/issues"
echo "2. Click 'New issue'"
echo "3. Copy the title and body from above"
echo "4. Add appropriate labels"
echo "5. Create the issue"
echo ""
echo "📝 Next Steps After Import:"
echo "- Update local ticket files with GitHub issue references"
echo "- Use 'gh issue comment <number>' to add details"
echo "- Use 'gh issue edit <number>' to update labels and status"