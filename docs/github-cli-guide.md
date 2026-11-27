# How to Use GitHub CLI with Existing SSH Key

## 📋 Overview

This guide explains how to use GitHub CLI with your existing SSH key (`~/.ssh/github_zabm`) for GitHub Issues batch import.

## 🔧 GitHub CLI Installation

Since GitHub CLI requires sudo access, you have several options:

### Option 1: Install GitHub CLI (Recommended)
```bash
# Install GitHub CLI using apt (requires sudo)
sudo apt update
sudo apt install gh

# Or use snap (requires sudo)
sudo snap install gh --classic
```

### Option 2: Use Manual Import with Existing SSH Key
If you cannot install GitHub CLI, use the manual import method with the existing SSH key.

## 🔑 Authentication Methods

### Method 1: SSH Authentication (for GitHub CLI)

Your existing SSH key is already set up and working:

```bash
# Test SSH authentication
ssh -T git@github.com
# Output: Hi ozjongwon! You've successfully authenticated, but GitHub does not provide shell access.
```

### Method 2: Personal Access Token (for API calls)

Create a personal access token:
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Select scopes: `repo` and `issues`
4. Copy the token

## 🚀 GitHub CLI Setup with SSH

Once GitHub CLI is installed, authenticate with your existing SSH key:

```bash
# Authenticate with GitHub CLI using SSH
gh auth login --web

# Or use the existing SSH key directly
gh auth status
```

## 📋 GitHub Issues Import Workflow

### Step 1: Install GitHub CLI (if using automated method)
```bash
sudo apt install gh
```

### Step 2: Authenticate with GitHub
```bash
# Using SSH (recommended)
gh auth login --web

# Or using personal access token
gh auth login --with-token <<< $GITHUB_TOKEN
```

### Step 3: Run the import script
```bash
# Using GitHub CLI (automated)
./scripts/import-github-issues.sh

# Using manual import with SSH
python3 scripts/github-import-ssh.py

# Using manual import with token
export GITHUB_TOKEN=your_token_here
python3 scripts/manual-github-import.py
```

## 🔧 Alternative: Manual Import Without GitHub CLI

If you cannot install GitHub CLI, use the manual import workflow:

### Method A: Web Interface
1. Run `./scripts/github-creation-helper.sh` to get issue content
2. Go to https://github.com/ozjongwon/zabm/issues
3. Create issues manually using the generated content

### Method B: API-based Import
```bash
# Set your GitHub token
export GITHUB_TOKEN=your_token_here

# Run the import script
python3 scripts/manual-github-import.py
```

## 🎯 Recommended Workflow

### For Development Environments (with sudo access):
1. Install GitHub CLI: `sudo apt install gh`
2. Authenticate with SSH: `gh auth login --web`
3. Run automated import: `./scripts/import-github-issues.sh`

### For Production Environments (without sudo):
1. Use manual import with token: `python3 scripts/manual-github-import.py`
2. Or use web interface with `./scripts/github-creation-helper.sh`

### For CI/CD Pipelines:
1. Use GitHub Actions with GitHub CLI
2. Or use API-based import with personal access token

## 📝 Scripts Available

| Script | Purpose | Authentication |
|--------|---------|----------------|
| `import-github-issues.sh` | Automated import | GitHub CLI |
| `github-import-ssh.py` | API-based import | SSH + Token |
| `manual-github-import.py` | API-based import | Personal Token |
| `github-creation-helper.sh` | Web interface helper | None |
| `setup-github-token.sh` | Token setup guide | None |

## 🔐 Security Best Practices

1. **SSH Key**: Already set up and working
2. **Personal Access Token**: Store in environment variables, never commit
3. **GitHub CLI**: Use SSH authentication when possible
4. **Scope**: Use minimal required permissions

## 🚀 Quick Start

### Option 1: GitHub CLI (Recommended)
```bash
sudo apt install gh
gh auth login --web
./scripts/import-github-issues.sh
```

### Option 2: Manual Import with SSH
```bash
python3 scripts/github-import-ssh.py
```

### Option 3: Manual Import with Web Interface
```bash
./scripts/github-creation-helper.sh
# Then manually create issues at https://github.com/ozjongwon/zabm/issues
```

Choose the method that best fits your environment and requirements!