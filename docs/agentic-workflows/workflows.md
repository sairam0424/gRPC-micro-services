# Workflows Overview

Guide to all active agentic workflows in this repository.

---

## 📊 Currently Active Workflows

### 1. Daily Repository Activity Report

**File**: `.github/workflows/daily-repo-activity.md`

**Schedule**: Daily at 09:00 UTC

**Purpose**: Generate comprehensive daily reports on repository activity

#### What It Does:

Creates a GitHub issue daily with:
- Recent activity summary (last 24 hours)
- Repository health status
- Key highlights and achievements
- Metrics and statistics
- Actionable next steps

#### Report Contents:

1. **Recent Activity Summary**
   - Issue statistics (opened, closed, in-progress)
   - PR status and CI checks
   - Commit summaries
   - Active branches

2. **Repository Status**
   - Microservices architecture health
   - Test coverage indicators
   - Build status
   - Deployment status

3. **Key Highlights**
   - Notable features/fixes merged
   - Critical issues/blockers
   - Performance improvements
   - Documentation updates

4. **Metrics Overview**
   - Open issues count
   - Open PRs count
   - Repository statistics
   - Commit frequency trends

5. **Actionable Next Steps**
   - High-priority items
   - PRs pending review
   - Upcoming milestones
   - Maintenance tasks

#### How to Access Reports:

```bash
# List all reports
gh issue list --label report,daily

# View specific report
gh issue view <number>

# View report body
gh issue view <number> --json body --jq .body

# Monitor via web
# GitHub repo → Issues → Filter by tag: report, daily
```

#### Configuration:

**Schedule** (cron format):
```yaml
- cron: '0 9 * * *'  # 9:00 AM UTC every day
```

**Permissions**:
- `contents: read` - Read repository content
- `issues: read` - Read issues
- `pull-requests: read` - Read PR information

**Safe Outputs**:
- Automatically creates issues
- Uses labels: `report`, `daily`
- Issue title prefix: `[Daily Report]`

#### Customize:

Edit `.github/workflows/daily-repo-activity.md`:

```bash
# Change schedule
vim .github/workflows/daily-repo-activity.md

# Line 4: modify cron expression
- cron: '0 12 * * *'  # Change to 12:00 PM UTC

# Compile changes
gh aw compile .github/workflows/daily-repo-activity.md

# Push
git add .github/workflows/daily-repo-activity.lock.yml
git commit -m "Update daily report schedule"
git push
```

#### Troubleshooting:

```bash
# Check if workflow is scheduled
gh workflow list | grep -i activity

# Manually trigger
gh workflow run daily-repo-activity.lock.yml

# View recent runs
gh run list --workflow daily-repo-activity.lock.yml -L 5

# Check logs
gh run view <run-id> --log
```

---

## 🎯 Workflow Fields Reference

### Common Workflow Configuration

All workflows have this structure (in `.md` file):

```markdown
---
on:
  schedule:
    - cron: '0 9 * * *'

permissions:
  contents: read
  issues: read
  pull-requests: read

safe-outputs:
  create-issue:
    title-prefix: "[Report] "
    labels: [report, daily]

tools:
  github: null
---

# Your Workflow Title

Workflow description and instructions in Markdown...
```

### Field Definitions

| Field | Purpose |
|-------|---------|
| `on` | Trigger configuration (schedule, events) |
| `schedule` | Cron-based triggers |
| `cron` | Cron expression (UTC timezone) |
| `permissions` | GitHub API access levels |
| `safe-outputs` | Allowed GitHub operations |
| `tools` | Available tools (GitHub API, REST, etc.) |
| `title-prefix` | Prefix for created issues |
| `labels` | Labels to apply to created items |

---

## 📅 Schedule Reference

### Common Cron Expressions

```yaml
# Daily at 9:00 AM UTC
'0 9 * * *'

# Every Monday at 9:00 AM UTC
'0 9 * * 1'

# 1st of month at 9:00 AM UTC
'0 9 1 * *'

# Every 6 hours
'0 */6 * * *'

# Weekdays only (Mon-Fri) at 9:00 AM
'0 9 * * 1-5'

# 9 AM and 6 PM (UTC)
'0 9,18 * * *'

# Midnight UTC
'0 0 * * *'
```

**Note:** All times are in UTC. Adjust for your timezone:
- **EST**: Subtract 5 hours
- **PST**: Subtract 8 hours
- **UTC+1**: Add 1 hour

---

## Future Workflows (Planned)

These workflows could be implemented to automate additional tasks:

### Issue Auto-Triaging
```markdown
Automatically label and categorize new issues based on content
```

### Code Quality Analysis
```markdown
Analyze code changes and suggest improvements
```

### Documentation Sync
```markdown
Keep README and docs in sync with code changes
```

### Test Coverage Reports
```markdown
Generate weekly test coverage analysis
```

### Release Notes Generation
```markdown
Auto-generate release notes from PRs and commits
```

---

## 🔄 Workflow Management

### View All Workflows

```bash
# List workflows
gh workflow list

# Check status
gh workflow list --json name,state

# View disabled workflows
gh workflow list --json name,state | grep -i disabled
```

### Enable/Disable Workflows

```bash
# Disable workflow
gh workflow disable daily-repo-activity.lock.yml

# Enable workflow
gh workflow enable daily-repo-activity.lock.yml
```

### Manual Trigger

```bash
# Trigger workflow
gh workflow run daily-repo-activity.lock.yml

# With custom parameters (if supported)
gh workflow run daily-repo-activity.lock.yml -f message="Custom message"
```

---

## 📊 View Workflow Results

### Recent Runs

```bash
# List all recent runs
gh run list

# Specific workflow
gh run list --workflow daily-repo-activity.lock.yml

# With details
gh run list --json status,name,createdAt --workflow daily-repo-activity.lock.yml
```

### Run Details

```bash
# View specific run
gh run view <run-id>

# View with JSON
gh run view <run-id> --json status,conclusion,startedAt,updatedAt

# View logs
gh run view <run-id> --log

# Stream logs
gh run watch <run-id>
```

### Artifacts & Results

```bash
# List issues created by workflows
gh issue list --label report,daily

# View specific issue
gh issue view <number>

# Get report content
gh issue view <number> --json body --jq .body
```

---

## 🔐 Security & Permissions

All workflows operate with:

✅ **Read-only permissions** by default
✅ **Safe outputs** for any write operations
✅ **Sandboxed execution** environment
✅ **Tool allowlisting** for available resources
✅ **Network isolation** where applicable

**Write operations** are explicitly approved through `safe-outputs`:
- `create-issue` ✅ Allowed
- `create-pull-request` ✅ Allowed
- `add-comment` ✅ Allowed
- Direct code modifications ❌ Not allowed

---

## 🛠️ Managing Workflows

### Check Workflow Status

```bash
# Overall status
gh workflow list --json name,state

# Specific workflow
gh workflow view daily-repo-activity.lock.yml
```

### Test Workflow

```bash
# Manual run to test
gh workflow run daily-repo-activity.lock.yml

# Check results
gh issue list --label report,daily --limit 1
```

### Update Workflow

```bash
# 1. Edit .md file
vim .github/workflows/daily-repo-activity.md

# 2. Compile
gh aw compile .github/workflows/daily-repo-activity.md

# 3. Validate
gh aw compile --validate

# 4. Commit & push
git add .github/workflows/daily-repo-activity.md
git add .github/workflows/daily-repo-activity.lock.yml
git commit -m "Update daily-repo-activity workflow"
git push
```

---

## 📚 Related Documentation

- [Setup Guide](./setup.md) - Installation and configuration
- [Quick Start](./quick-start.md) - Get started in 5 minutes
- [Command Reference](./reference.md) - All available commands
- [Troubleshooting](./troubleshooting.md) - Common issues and solutions
- [Merge Strategy](./merge-strategy.md) - Managing lock files

---

## 🔗 Resources

- [GitHub Agentic Workflows](https://github.github.io/gh-aw/)
- [Workflow Gallery & Examples](https://github.github.io/gh-aw/blog/)
- [Safe Outputs Reference](https://github.github.io/gh-aw/reference/safe-outputs/)

---

**Last Updated**: February 16, 2026
**Active Workflows**: 1 (Daily Repository Activity Report)
**Status**: ✅ Running successfully
