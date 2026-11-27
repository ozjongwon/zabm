#!/bin/bash

# GitHub Issues Import Script - Simple Version
# This script shows tickets ready for import and creates GitHub issue commands

set -e

REPO="ozjongwon/zabm"
BASE_DIR=".scratch"

echo "🚀 GitHub Issues Import Script"
echo "================================="
echo "Repository: $REPO"
echo "Base directory: $BASE_DIR"
echo ""

echo "📋 Tickets Ready for Import:"
echo ""

# Find tickets with ready-for-agent status
for ticket_file in $(find "$BASE_DIR" -name "*.md" -path "*/issues/*" -exec grep -l "\*\*Status:\*\* ready-for-agent" {} \;); do
    feature_dir=$(dirname "$ticket_file")
    feature_name=$(basename "$feature_dir")
    ticket_name=$(basename "$ticket_file" .md)
    
    echo "🔍 Found: $feature_name/$ticket_name"
    echo "   File: $ticket_file"
    
    # Extract title
    title=$(head -10 "$ticket_file" | grep -E "^# [0-9]+:" | sed 's/^# \([0-9]\+\): /# /' | head -1)
    if [[ -z "$title" ]]; then
        title=$(head -5 "$ticket_file" | grep -E "^# " | head -1 | sed 's/^# //')
    fi
    
    echo "   Title: $title"
    
    # Extract priority
    priority=$(grep -E "\*\*Priority:\*\*" "$ticket_file" | sed 's/\*\*Priority:\*\* //' | tr -d ' ')
    echo "   Priority: $priority"
    
    # Extract blocked by
    blocked_by=$(grep -E "\*\*Blocked by:\*\*" "$ticket_file" | sed 's/\*\*Blocked by:\*\* //' | tr -d ' ')
    echo "   Blocked by: $blocked_by"
    
    echo ""
done

echo "================================="
echo "📝 Manual Import Instructions:"
echo ""
echo "1. Install GitHub CLI if not already installed:"
echo "   curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg"
echo "   echo \"deb [arch=\$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main\" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null"
echo "   sudo apt update && sudo apt install gh"
echo ""
echo "2. Authenticate with GitHub:"
echo "   gh auth login"
echo ""
echo "3. Create issues manually via web interface:"
echo "   - Go to: https://github.com/ozjongwon/zabm/issues"
echo "   - Click 'New issue'"
echo "   - Use the ticket information above"
echo "   - Add appropriate labels:"
echo "     - needs-triage"
echo "     - ready-for-agent (if status is ready)"
echo "     - priority-high (for high priority tickets)"
echo ""
echo "4. After creating issues, update local tickets with GitHub issue numbers"
echo ""