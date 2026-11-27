#!/bin/bash

# GitHub Issues Content Generator
# This script generates the exact content for creating GitHub issues manually

set -e

BASE_DIR=".scratch"

echo "🚀 GitHub Issues Content Generator"
echo "=================================="
echo "Repository: ozjongwon/zabm"
echo "Base directory: $BASE_DIR"
echo ""

echo "📋 Generate GitHub Issue Content:"
echo ""

# Function to generate issue content
generate_issue_content() {
    local ticket_file="$1"
    local feature_dir="$2"
    
    echo "📝 Issue Content for: $(basename "$ticket_file" .md)"
    echo "=========================================="
    echo ""
    
    # Extract ticket metadata
    local ticket_name=$(basename "$ticket_file" .md)
    local feature_name=$(basename "$feature_dir")
    
    # Extract title
    local title=$(head -10 "$ticket_file" | grep -E "^# [0-9]+:" | sed 's/^# \([0-9]\+\): /# /' | head -1)
    if [[ -z "$title" ]]; then
        title=$(head -5 "$ticket_file" | grep -E "^# " | head -1 | sed 's/^# //')
    fi
    
    # Extract status
    local status=$(grep -E "\*\*Status:\*\*" "$ticket_file" | sed 's/\*\*Status:\*\* //' | tr -d ' ')
    
    # Extract priority
    local priority=$(grep -E "\*\*Priority:\*\*" "$ticket_file" | sed 's/\*\*Priority:\*\* //' | tr -d ' ')
    
    # Extract type
    local type=$(grep -E "\*\*Type:\*\*" "$ticket_file" | sed 's/\*\*Type:\*\* //' | tr -d ' ')
    
    # Extract blocked by information
    local blocked_by=$(grep -E "\*\*Blocked by:\*\*" "$ticket_file" | sed 's/\*\*Blocked by:\*\* //' | tr -d ' ')
    
    # Extract description (skip metadata lines)
    local description=""
    local in_description=0
    while IFS= read -r line; do
        if [[ "$line" =~ ^\#\#\  ]]; then
            in_description=1
            continue
        fi
        if [[ "$in_description" -eq 1 && ! "$line" =~ ^\-\s*\[ ]]; then
            description+="$line\n"
        fi
    done < "$ticket_file"
    
    # Generate issue body
    local issue_body="# $title\n\n"
    issue_body+="**Feature:** $feature_name\n"
    issue_body+="**Original Ticket:** $ticket_file\n"
    issue_body+="**Type:** $type\n"
    issue_body+="**Priority:** $priority\n"
    issue_body+="**Status:** $status\n\n"
    
    if [[ -n "$blocked_by" && "$blocked_by" != "None." ]]; then
        issue_body+="## Dependencies\n\nBlocked by: $blocked_by\n\n"
    fi
    
    issue_body+="## Description\n\n"
    issue_body+=$(echo -e "$description" | sed '/^$/d' | head -30)
    
    issue_body+="\n---\n"
    issue_body+="*Auto-generated from local ticket import. Please update status and labels as needed.*"
    
    # Print the issue content
    echo "📋 Title:"
    echo "$title"
    echo ""
    echo "🏷️  Labels:"
    if [[ "$priority" == "high" ]]; then
        echo "- needs-triage"
        echo "- priority-high"
    elif [[ "$priority" == "medium" ]]; then
        echo "- needs-triage"
        echo "- priority-medium"
    else
        echo "- needs-triage"
    fi
    
    if [[ "$status" == "ready-for-agent" ]]; then
        echo "- ready-for-agent"
    fi
    
    echo ""
    echo "📝 Body:"
    echo "$issue_body"
    echo ""
    echo "=========================================="
    echo ""
}

# Generate content for each ready ticket
for ticket_file in $(find "$BASE_DIR" -name "*.md" -path "*/issues/*" -exec grep -l "\*\*Status:\*\* ready-for-agent" {} \;); do
    feature_dir=$(dirname "$ticket_file")
    generate_issue_content "$ticket_file" "$feature_dir"
done

echo "🎯 Next Steps:"
echo "1. Copy the Title and Body content above for each ticket"
echo "2. Go to https://github.com/ozjongwon/zabm/issues"
echo "3. Click 'New issue' for each ticket"
echo "4. Paste the title and body content"
echo "5. Add the appropriate labels"
echo "6. Create the issue"
echo "7. Update the local ticket file with the GitHub issue number"
echo ""
echo "📝 Example GitHub Issue Creation:"
echo "1. Go to: https://github.com/ozjongwon/zabm/issues"
echo "2. Click 'New issue'"
echo "3. Fill in Title field with the title from above"
echo "4. Click 'Write' tab and paste body content"
echo "5. Click 'Labels' tab and add appropriate labels"
echo "6. Click 'Create issue'"