#!/usr/bin/env python3
"""
GitHub Issues CLI Creator
This script creates GitHub issues using the GitHub CLI
"""

import subprocess
import sys
from pathlib import Path

def create_github_issue(title, body, labels):
    """Create a GitHub issue using gh CLI"""
    # Format labels
    label_str = ",".join(labels)
    
    # Create issue using gh CLI
    cmd = [
        "gh", "issue", "create",
        "--title", title,
        "--body", body,
        "--label", label_str
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error creating issue: {e}")
        print(f"Error output: {e.stderr}")
        return None

def get_ticket_content(ticket_file):
    """Extract ticket content from markdown file"""
    try:
        with open(ticket_file, encoding='utf-8') as f:
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
    print("🚀 GitHub Issues CLI Creator")
    print("============================")
    
    # Configuration
    repo = "ozjongwon/zabm"
    base_dir = Path(".scratch")
    
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
        elif content['priority'] == 'low':
            labels.append('priority-low')
        
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
        result = create_github_issue(content['title'], body, labels)
        if result:
            # Extract issue number from result
            issue_number = result.split('#')[1] if '#' in result else "unknown"
            created_issues.append({
                'local_ticket': ticket_name,
                'github_issue': issue_number,
                'result': result
            })
            print(f"✅ Created issue #{issue_number}: {result}")
        else:
            print(f"❌ Failed to create issue for {ticket_name}")
        
        print("")
    
    # Update local tickets with GitHub issue references
    if created_issues:
        print("📝 Updating local tickets with GitHub issue references:")
        print("")
        
        for issue_info in created_issues:
            ticket_file = (
                base_dir / "coding-environment-improvements" / 
                "issues" / f"{issue_info['local_ticket']}.md"
            )
            if ticket_file.exists():
                with open(ticket_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n\nGitHub Issue: #{issue_info['github_issue']}\n")
                    f.write(f"GitHub URL: https://github.com/ozjongwon/zabm/issues/{issue_info['github_issue']}\n")
                print(f"✅ Updated: {ticket_file}")
        
        # Create tracker file
        with open('.github-import-tracker.txt', 'w', encoding='utf-8') as f:
            f.write("# GitHub Issues Import Tracker\n")
            f.write("# Format: LocalTicket:GitHubIssueNumber\n")
            f.write("\n")
            for issue_info in created_issues:
                f.write(f"{issue_info['local_ticket']}:{issue_info['github_issue']}\n")
        
        print("✅ Created tracker file: .github-import-tracker.txt")
        
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