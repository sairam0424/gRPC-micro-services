# Command Reference: gh aw

Complete reference for `gh aw` commands and common operations.

---

## 📋 Installation & Verification

### Check Installation Status

```bash
# Check gh CLI version
gh version

# Check gh-aw version
gh aw version

# Get help
gh aw --help
gh aw <command> --help
```

---

## 🔨 Workflow Management

### Create New Workflow

```bash
# Interactive workflow creation
gh aw new <workflow-name>

# Example:
gh aw new auto-triage
```

After creation, you'll have:
- `.github/workflows/<workflow-name>.md` - Workflow definition
- `.github/workflows/<workflow-name>.lock.yml` - Compiled workflow

### Compile Workflows

```bash
# Compile specific workflow
gh aw compile .github/workflows/<workflow-name>.md

# Compile all workflows
gh aw compile

# Example
gh aw compile .github/workflows/daily-repo-activity.md
```

**When to use:**
- After editing a `.md` workflow file
- After merging branches with workflow changes
- Before pushing changes to ensure validity

### Validate Workflows

```bash
# Validate specific workflow
gh aw compile .github/workflows/<workflow-name>.md --validate

# Validate all workflows
gh aw compile --validate

# Example
gh aw compile --validate .github/workflows/daily-repo-activity.md
```

**Output:**
- ✓ Workflow is valid
- ✗ Errors found (with details)

---

## 📊 View Workflow Information

### List Workflows

```bash
# List GitHub Actions workflows
gh workflow list

# List GitHub Actions workflow files
ls -la .github/workflows/
```

### View Workflow Details

```bash
# Read workflow definition
cat .github/workflows/<workflow-name>.md

# View compiled workflow (first 50 lines)
head -50 .github/workflows/<workflow-name>.lock.yml
```

---

## 🚀 Execute Workflows

### Manual Trigger

```bash
# Manually trigger compiled workflow
gh workflow run <workflow-lock-file> 

# Example
gh workflow run daily-repo-activity.lock.yml

# Trigger and wait for completion
gh run watch [<number>]
```

**Via GitHub UI:**
1. Go to repository **Actions** tab
2. Select workflow
3. Click **Run workflow**

---

## 📈 View Run History

### List Workflow Runs

```bash
# List all recent runs
gh run list

# List runs for specific workflow
gh run list --workflow <workflow-lock-file>

# Show more details
gh run list --workflow <workflow-lock-file> --json status,name,createdAt --limit 10

# Example
gh run list --workflow daily-repo-activity.lock.yml --limit 5
```

### View Run Details

```bash
# View specific run
gh run view <run-id>

# View run with JSON output
gh run view <run-id> --json status,conclusion,startedAt,updatedAt

# Get last run number
gh run list --limit 1 --json number --jq .[0].number
```

---

## 📝 View Logs

### View Workflow Logs

```bash
# View logs for workflow (interactive mode)
gh aw logs <workflow-name>

# Example
gh aw logs daily-repo-activity
```

### View Run Logs

```bash
# View logs for specific run
gh run view <run-id> --log

# View and follow logs (stream)
gh run watch <run-id>
```

---

## 🔍 Debug & Audit

### Audit Workflows

```bash
# Audit specific run
gh aw audit <run-id>

# Example
gh aw audit 12345
```

**Shows:**
- Tool calls made
- Outputs generated
- Safe output operations
- Any errors

### Debug Compilation Issues

```bash
# Compile with verbose output
gh aw compile .github/workflows/<workflow-name>.md --validate 2>&1

# Check specific line errors
gh aw compile .github/workflows/<workflow-name>.md | grep -i error
```

---

## 🛠️ Fix & Update

### Fix Deprecations

```bash
# Automatically fix deprecated syntax
gh aw fix --write

# Then recompile
gh aw compile
```

### Regenerate Lock Files

After merging or resolving conflicts:

```bash
# Regenerate specific workflow lock
gh aw compile .github/workflows/<workflow-name>.md

# Regenerate all workflows
gh aw compile

# Verify compilation
gh aw compile --validate
```

---

## 📍 Git Integration

### Commit Workflow Changes

```bash
# Stage workflow files
git add .github/workflows/<workflow-name>.md
git add .github/workflows/<workflow-name>.lock.yml

# Commit
git commit -m "Update <workflow-name> workflow"

# Push
git push
```

### Merge Workflows with Conflict Resolution

```bash
# Start merge
git merge <branch>

# If conflicts on lock files
gh aw compile

# Stage and commit
git add .github/workflows/*.lock.yml
git commit -m "Regenerate workflow lock files after merge"
git push
```

---

## 🔐 Permissions & Security

### View Workflow Permissions

```bash
# Check permissions for workflow
grep -A3 "^permissions:" .github/workflows/<workflow-name>.md
```

### Common Permissions

```yaml
permissions:
  contents: read           # Read-only access to code
  issues: read            # Read-only access to issues
  pull-requests: read     # Read-only access to PRs
  actions: read           # Read-only actions metadata
```

**Note:** Write operations are handled through `safe-outputs`, not direct permissions.

---

## 📅 Scheduling Reference

### Cron Syntax

```bash
# Minute Hour Day Month DayOfWeek
  0     9    *   *      *          # 9:00 AM every day (UTC)
```

### Common Schedules

```yaml
# Daily at 9:00 AM UTC
- cron: '0 9 * * *'

# Every Monday at 9:00 AM UTC
- cron: '0 9 * * 1'

# 1st of each month at 9:00 AM UTC
- cron: '0 9 1 * *'

# Every 6 hours
- cron: '0 */6 * * *'

# Weekdays (Mon-Fri) at 9:00 AM UTC
- cron: '0 9 * * 1-5'

# Twice daily (9 AM and 6 PM UTC)
- cron: '0 9,18 * * *'
```

**Time Zone:** All cron schedules use UTC

**Fuzzy schedules (GitHub recommendation):**
```yaml
on:
  schedule:
    - cron: 'daily'        # Random time each day
    - cron: 'weekly'       # Random time each week
    - cron: 'monthly'      # Random time each month
```

---

## 🚨 Common Troubleshooting Commands

```bash
# Validate all workflows
gh aw compile --validate

# Check specific workflow status
gh workflow list | grep -i daily

# View last run
gh run list --limit 1

# See run output
gh run view <id> --log

# Check workflow syntax
gh aw compile .github/workflows/<name>.md 2>&1

# Audit a run
gh aw audit <run-id>

# Regenerate after conflicts
gh aw compile

# Force refresh after merge
git stash
git pull
gh aw compile
```

---

## 📚 Help & Documentation

```bash
# Main help
gh aw --help

# Command-specific help
gh aw compile --help
gh aw new --help
gh aw logs --help
gh aw audit --help

# GitHub Agentic Workflows docs
# https://github.github.io/gh-aw/

# GitHub CLI help
# https://cli.github.com/manual/
```

---

## 💾 Environment Variables

Common environment variables for gh-aw:

```bash
# Set default editor for creating workflows
export GH_EDITOR=vim

# Set GitHub API endpoint (if using GitHub Enterprise)
export GH_HOST=github.example.com

# Enable debug mode (verbose output)
export GH_DEBUG=api

# View all GitHub environment variables
env | grep GH_
```

---

## 📦 Version Management

```bash
# Check current version
gh aw version

# Upgrade to latest version
gh extension upgrade gh-aw

# Check for available updates
gh extension upgrade --all
```

---

## 🔗 See Also

- [Setup Guide](./setup.md)
- [Quick Start](./quick-start.md)
- [Merge Strategy](./merge-strategy.md)
- [Troubleshooting](./troubleshooting.md)
- [Official Reference](https://github.github.io/gh-aw/reference/)

---

**Last Updated**: February 16, 2026
**gh-aw Version**: v0.44.0
