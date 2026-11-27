#!/bin/bash

# GitHub Token Setup Script
# This script helps users set up GitHub authentication for manual import

echo "🚀 GitHub Token Setup Script"
echo "============================="
echo ""

echo "📋 To create GitHub issues manually, you need a GitHub Personal Access Token"
echo ""

echo "🔑 Steps to create a GitHub token:"
echo "1. Go to: https://github.com/settings/tokens"
echo "2. Click 'Generate new token' → 'Generate new token (classic)'"
echo "3. Select scopes:"
echo "   ✅ repo (Full control of private repositories)"
echo "   ✅ issues (Read and write issues)"
echo "4. Click 'Generate token'"
echo "5. Copy the token (it will only be shown once!)"
echo ""

echo "🔧 Set up the token:"
echo "export GITHUB_TOKEN=your_token_here"
echo ""

echo "📝 Example:"
echo "export GITHUB_TOKEN=ghp_your_token_here"
echo ""

echo "🚀 After setting the token, run:"
echo "python3 scripts/manual-github-import.py"
echo ""

echo "💡 Tips:"
echo "- Store the token in your shell profile for future use"
echo "- Consider using a token with limited scope for security"
echo "- Never commit tokens to version control"
echo ""

echo "✅ Setup complete! Now you can run the import script."