#!/bin/bash

# GitHub Labels Setup Script
# This script helps create the required labels for the zabm repository
# Run this after setting up GitHub CLI authentication

set -e

REPO="ozjongwon/zabm"
LABELS=(
    "needs-triage;New issues that need assessment"
    "needs-info;Issues missing required information"
    "ready-for-agent;Issues ready for implementation"
    "ready-for-human;Issues needing human decision/input"
    "wontfix;Issues that won't be addressed"
)

echo "Setting up GitHub labels for repository: $REPO"
echo "Make sure you have GitHub CLI installed and authenticated: gh auth login"
echo ""

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) not found. Please install it first:"
    echo "   curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg"
    echo "   echo \"deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main\" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null"
    echo "   sudo apt update"
    echo "   sudo apt install gh"
    echo ""
    echo "Or create labels manually via GitHub web interface:"
    echo "1. Go to https://github.com/ozjongwon/zabm/issues/labels"
    echo "2. Create the following labels:"
    for label in "${LABELS[@]}"; do
        IFS=';' read -r name description <<< "$label"
        echo "   - $name (description: $description)"
    done
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub CLI. Please authenticate first:"
    echo "   gh auth login"
    exit 1
fi

# Create labels
for label in "${LABELS[@]}"; do
    IFS=';' read -r name description <<< "$label"
    echo "Creating label: $name"
    gh label create "$name" --description "$description" --force || echo "Label '$name' already exists or failed to create"
done

echo ""
echo "✅ GitHub labels setup complete!"
echo ""
echo "Next steps:"
echo "1. Create high-priority GitHub issues for coding environment improvements"
echo "2. Use the triage skill to manage issue lifecycle"
echo "3. Use to-tickets skill to break down plans into GitHub issues"