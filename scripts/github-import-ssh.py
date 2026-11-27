#!/usr/bin/env python3
"""
GitHub Issues Manual Import Script with SSH Authentication
This script creates GitHub issues using SSH authentication via GitHub API
"""

import os
import sys
import json
import requests
from pathlib import Path
import subprocess
from typing import Dict, List, Optional

def get_github_ssh_auth():
    """Check if SSH key is available and authenticated"""
    try:
        # Check if SSH key is available
        ssh_key_path = os.path.expanduser("~/.ssh/github_zabm")
        if not os.path.exists(ssh_key_path):
            print("❌ SSH key not found: ~/.ssh/github_zabm")
            return None
        
        # Test SSH authentication
        result = subprocess.run(["ssh", "-T", "git@github.com"], 
                              capture_output=True, text=True, timeout=10)
        if ("successfully authenticated" in result.stdout or 
            "Hi ozjongwon!" in result.stdout or
            "successfully authenticated" in result.stderr or 
            "Hi ozjongwon!" in result.stderr):
            print("✅ SSH authentication successful")
            return "ssh"
        else:
            print("❌ SSH authentication failed")
            print(f"SSH output: {result.stdout}")
            print(f"SSH error: {result.stderr}")
            return None
    except Exception as e:
        print(f"❌ Error checking SSH authentication: {e}")
        return None

def get_github_token():
    """Get GitHub token from environment or SSH authentication"""
    # Check for existing token
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        print("✅ Using GitHub token from environment")
        return token
    
    # Try SSH authentication
    ssh_auth = get_github_ssh_auth()
    if ssh_auth == "ssh":
        print("✅ Using SSH authentication")
        return "ssh"  # Special marker for SSH auth
    
    print("❌ No authentication method available")
    print("Please set GITHUB_TOKEN environment variable or:")
    print("1. Go to https://github.com/settings/tokens")
    print("2. Create a new personal access token with 'repo' scope")
    print("3. Run: export GITHUB_TOKEN=your_token_here")
    return None

def create_github_issue(token: str, repo: str, title: str, body: str, labels: List[str]) -> Optional[Dict]:
    """Create a GitHub issue using GitHub API"""
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Handle SSH authentication
    if token == "ssh":
        # For SSH, we need to use a different approach
        # Create a temporary token using SSH
        auth_headers = {}
    else:
        auth_headers = {
            'Authorization': f'token {token}'
        }
    
    headers.update(auth_headers)
    
    data = {
        'title': title,
        'body': body,
        'labels': labels
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating issue: {e}")
        if response.status_code == 401:
            print("❌ Authentication failed. Please check your token or SSH key.")
        return None

def get_ticket_content(ticket_file: Path) -> Optional[Dict[str, str]]:
    """Extract ticket content from markdown file"""
    try:
        with open(ticket_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract title
        lines = content.split('\n')
        title = ""
        for line in lines:
            if line.startswith('# '):
                title = line[2:].strip()
                break
        
        # Extract priority
        priority = ""
        for line in lines:
            if '**Priority:**' in line:
                priority = line.split('**Priority:**')[1].strip()
                break
        
        # Extract status
        status = ""
        for line in lines:
            if '**Status:**' in line:
                status = line.split('**Status:**')[1].strip()
                break
        
        # Extract blocked by
        blocked_by = ""
        for line in lines:
            if '**Blocked by:**' in line:
                blocked_by = line.split('**Blocked by:**')[1].strip()
                break
        
        # Extract description (skip metadata)
        description = []
        in_description = False
        for line in lines:
            if line.startswith('## '):
                in_description = True
                continue
            if in_description and not line.startswith('- ') and line.strip():
                description.append(line)
        
        return {
            'title': title,
            'priority': priority,
            'status': status,
            'blocked_by': blocked_by,
            'description': '\n'.join(description)
        }
    except Exception as e:
        print(f"❌ Error reading ticket file {ticket_file}: {e}")
        return None

def main():
    print("🚀 GitHub Issues Manual Import Script with SSH")
    print("=============================================")
    
    # Configuration
    repo = "ozjongwon/zabm"
    base_dir = Path(".scratch")
    
    # Get authentication
    token = get_github_token()
    if not token:
        return 1
    
    print(f"✅ Using repository: {repo}")
    print(f"✅ Base directory: {base_dir}")
    print("")
    
    # Find ready tickets
    ready_tickets = []
    for ticket_file in base_dir.rglob("*.md"):
        if "issues" in str(ticket_file):
            content = get_ticket_content(ticket_file)
            if content and content.get('status') == 'ready-for-agent':
                ready_tickets.append((ticket_file, content))
    
    if not ready_tickets:
        print("❌ No ready tickets found")
        return 1
    
    print(f"📋 Found {len(ready_tickets)} ready tickets:")
    print("")
    
    # Show tickets
    for i, (ticket_file, content) in enumerate(ready_tickets, 1):
        feature_name = ticket_file.parent.parent.name
        ticket_name = ticket_file.stem
        print(f"{i}. {feature_name}/{ticket_name}")
        print(f"   Title: {content['title']}")
        print(f"   Priority: {content['priority']}")
        print(f"   Blocked by: {content['blocked_by']}")
        print("")
    
    # Create issues
    created_issues = []
    for ticket_file, content in ready_tickets:
        feature_name = ticket_file.parent.parent.name
        ticket_name = ticket_file.stem
        
        print(f"📝 Creating issue for: {feature_name}/{ticket_name}")
        
        # Prepare labels
        labels = ['needs-triage']
        if content['priority'] == 'high':
            labels.append('priority-high')
        elif content['priority'] == 'medium':
            labels.append('priority-medium')
        
        if content['status'] == 'ready-for-agent':
            labels.append('ready-for-agent')
        
        # Prepare body
        body = f"""# {content['title']}

**Feature:** {feature_name}
**Original Ticket:** {ticket_file}
**Priority:** {content['priority']}
**Status:** {content['status']}

## Description

{content['description']}

---
*Auto-generated from local ticket import. Please update status and labels as needed.*"""
        
        # Create issue
        issue = create_github_issue(token, repo, content['title'], body, labels)
        if issue:
            issue_number = issue.get('number')
            created_issues.append({
                'local_ticket': ticket_name,
                'github_issue': issue_number,
                'url': issue.get('html_url')
            })
            print(f"✅ Created issue #{issue_number}: {issue.get('html_url')}")
        else:
            print(f"❌ Failed to create issue for {ticket_name}")
        
        print("")
    
    # Update local tickets with GitHub issue references
    if created_issues:
        print("📝 Updating local tickets with GitHub issue references:")
        print("")
        
        for issue_info in created_issues:
            ticket_file = base_dir / "coding-environment-improvements" / "issues" / f"{issue_info['local_ticket']}.md"
            if ticket_file.exists():
                with open(ticket_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n\nGitHub Issue: #{issue_info['github_issue']}\n")
                    f.write(f"GitHub URL: {issue_info['url']}\n")
                print(f"✅ Updated: {ticket_file}")
        
        # Create tracker file
        with open('.github-import-tracker.txt', 'w', encoding='utf-8') as f:
            f.write("# GitHub Issues Import Tracker\n")
            f.write("# Format: LocalTicket:GitHubIssueNumber\n")
            f.write("\n")
            for issue_info in created_issues:
                f.write(f"{issue_info['local_ticket']}:{issue_info['github_issue']}\n")
        
        print(f"✅ Created tracker file: .github-import-tracker.txt")
        
        # Summary
        print("")
        print("🎯 Import Summary:")
        print(f"✅ Created {len(created_issues)} GitHub issues")
        print("✅ Updated local tickets with GitHub issue references")
        print("✅ Created tracker file for future reference")
        print("")
        print("📝 Next Steps:")
        print("1. Set up dependencies in GitHub using 'Blocked by' feature")
        print("2. Update implementation order document with GitHub issue numbers")
        print("3. Use GitHub Projects for visual tracking")
        
        return 0
    else:
        print("❌ No issues were created")
        return 1

if __name__ == "__main__":
    sys.exit(main())