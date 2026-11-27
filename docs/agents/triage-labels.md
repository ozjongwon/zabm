# Triage Label Vocabulary

This repo uses the five canonical triage labels, each label string equal to its name:

## Label Mapping

| Role | Label String |
|------|--------------|
| needs-triage | `needs-triage` |
| needs-info | `needs-info` |
| ready-for-agent | `ready-for-agent` |
| ready-for-human | `ready-for-human` |
| wontfix | `wontfix` |

## Usage

- **`needs-triage`**: New issues that haven't been assessed yet
- **`needs-info`**: Issues missing required information from the user
- **`ready-for-agent`**: Issues ready for implementation by an AI agent
- **`ready-for-human`**: Issues requiring human decision or input
- **`wontfix`**: Issues that have been decided not to be addressed

## Label Creation

When using GitHub Issues, create these labels in the repository if they don't exist:
```bash
gh label create needs-triage --description "New issues that need assessment"
gh label create needs-info --description "Issues missing required information" 
gh label create ready-for-agent --description "Issues ready for implementation"
gh label create ready-for-human --description "Issues needing human decision/input"
gh label create wontfix --description "Issues that won't be addressed"
```