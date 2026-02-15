# Setup Guide: GitHub Agentic Workflows

Complete guide to installing and configuring GitHub Agentic Workflows for your repository.

---

## Prerequisites

- GitHub CLI (`gh`) installed
- Git installed and configured
- GitHub repository with write access
- (Optional) VS Code for workflow editing

---

## ✅ Installation Steps

### Step 1: Install GitHub CLI

If you don't already have GitHub CLI installed:

```bash
# macOS
brew install gh

# Linux (Ubuntu/Debian)
sudo apt-get install gh

# Or download directly from https://cli.github.com/
```

Verify installation:
```bash
gh version
```

### Step 2: Authenticate with GitHub

```bash
gh auth login
```

Follow the prompts to authenticate your GitHub account.

### Step 3: Install GitHub Agentic Workflows CLI

Run the installation script:

```bash
curl -sL https://raw.githubusercontent.com/github/gh-aw/main/install-gh-aw.sh | bash
```

Verify installation:
```bash
gh aw version
# Example output: gh aw version v0.44.0
```

### Step 4: (Optional) Set Up VS Code

Install these extensions for better workflow editing:

1. **GitHub Copilot Chat** - AI assistance
2. **GitHub Actions** - Workflow validation
3. **YAML** (Red Hat) - Syntax highlighting

---

## 📁 Repository Setup

### Current Installation Status

| Component | Version | Status |
|-----------|---------|--------|
| GitHub CLI | v2.86.0 | ✅ |
| gh-aw | v0.44.0 | ✅ |

### Files Created

```
✅ .github/workflows/daily-repo-activity.md
✅ .github/workflows/daily-repo-activity.lock.yml
✅ .gitattributes (updated)
```

---

## 🔧 Configuration

### Daily Repository Activity Workflow

**Location**: `.github/workflows/daily-repo-activity.md`

**Schedule**: Daily at 09:00 UTC

**Permissions**:
- `contents: read` - Read repository content
- `issues: read` - Read issues
- `pull-requests: read` - Read PR information

**Features**:
- Generates daily repository activity reports
- Creates issues with label: `report`, `daily`
- Title prefix: `[Daily Report]`
- Includes recent activity, metrics, and actionable insights

---

## 🚀 First Run

### Manual Trigger (Recommended for Testing)

1. Navigate to your repository on GitHub
2. Go to **Actions** tab
3. Select **Daily Repository Activity** workflow
4. Click **Run workflow**
5. Check the **Issues** tab for the generated report

### Automatic Execution

The workflow automatically runs every day at 09:00 UTC. After the first run, you'll see:
- New issue created in your repository
- Labels: `report`, `daily`
- Title: `[Daily Report] Daily Repository Activity - [DATE]`

### Accessing Reports

View all generated reports:
```bash
# Filter by labels
gh issue list --label report,daily

# View specific report
gh issue view <issue-number>
```

---

## ✨ Workflow Features

### Daily Report Includes:

1. **Recent Activity Summary** (Last 24 hours)
   - Issue statistics (opened, closed, in-progress)
   - Pull request status and CI checks
   - Commit summaries and contributors
   - Active branches

2. **Repository Status**
   - Architecture health indicators
   - Test coverage information
   - Build status summary
   - Deployment status

3. **Key Highlights**
   - Notable merged features
   - Critical issues/blockers
   - Performance improvements
   - Documentation updates

4. **Metrics Overview**
   - Open issues count
   - Open PRs count
   - Repository statistics
   - Commit frequency

5. **Actionable Next Steps**
   - High-priority items
   - PRs pending review
   - Upcoming milestones
   - Maintenance tasks

---

## 🔒 Security Features

GitHub Agentic Workflows include built-in safeguards:

✅ **Read-only by default** - No write access without explicit approval
✅ **Safe outputs** - Controlled GitHub operations only
✅ **Sandboxing** - Isolated execution environment
✅ **Tool allowlisting** - Only approved tools available
✅ **Network isolation** - Restricted network access

---

## 📖 Additional Resources

- [Quick Start Guide](./quick-start.md)
- [Workflow Details](./workflows.md)
- [Command Reference](./reference.md)
- [Troubleshooting Guide](./troubleshooting.md)
- [Official Documentation](https://github.github.io/gh-aw/)

---

## ❓ Common Questions

**Q: How do I change the schedule?**
A: Edit `.github/workflows/daily-repo-activity.md` and modify the cron expression. See [Cron Schedule Reference](./reference.md#cron-schedule-reference).

**Q: Can I create custom workflows?**
A: Yes! See [Creating New Workflows](./creating-workflows.md).

**Q: How often does it run?**
A: Daily at 09:00 UTC by default. You can customize this.

**Q: Can I manually trigger it?**
A: Yes, via GitHub Actions UI or CLI: `gh workflow run daily-repo-activity.lock.yml`

---

**Last Updated**: February 16, 2026
**Installation Status**: ✅ Complete
