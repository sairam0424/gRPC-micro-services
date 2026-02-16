# Quick Start: GitHub Agentic Workflows

Get started with GitHub Agentic Workflows in 5 minutes.

---

## 🚀 Quick Setup (5 minutes)

### 1. Verify Installation

```bash
# Check gh CLI
gh version

# Check gh-aw
gh aw version
```

If not installed, see [Setup Guide](./setup.md).

### 2. Check Existing Workflows

```bash
# List all workflows
ls -la .github/workflows/*.md

# See available workflows
gh workflow list
```

### 3. Manual Test Run

```bash
# Trigger the daily report workflow
gh workflow run daily-repo-activity.lock.yml

# Or via GitHub UI:
# 1. Go to repository Actions tab
# 2. Select "Daily Repository Activity"
# 3. Click "Run workflow"
```

### 4. View Generated Report

Check GitHub **Issues** tab for a new issue labeled `report` and `daily`.

```bash
# Or via CLI
gh issue list --label report,daily --limit 1
```

---

## 📚 Common Tasks

### See Workflow Details

```bash
# Read the workflow definition
cat .github/workflows/daily-repo-activity.md

# Check the compiled version
cat .github/workflows/daily-repo-activity.lock.yml | head -50
```

### Edit Schedule

Daily at 9:00 AM UTC? Change it:

```bash
# Edit the workflow
vim .github/workflows/daily-repo-activity.md
```

Change line 4 from:
```yaml
- cron: '0 9 * * *'
```

To one of these:
```yaml
- cron: '0 9 * * 1'       # Every Monday at 9 AM
- cron: '0 9 1 * *'       # 1st of each month at 9 AM
- cron: '0 */6 * * *'     # Every 6 hours
```

Then compile and push:
```bash
gh aw compile .github/workflows/daily-repo-activity.md
git add .github/workflows/daily-repo-activity.lock.yml
git commit -m "Update daily-repo-activity schedule"
git push
```

### View Recent Report Results

```bash
# List recent reports
gh issue list --label report,daily --limit 5

# View a specific report
gh issue view <number>

# View report body text
gh issue view <number> --json body --jq .body
```

### Validate Workflows

```bash
# Check if all workflows are valid
gh aw compile --validate

# Validate specific workflow
gh aw compile .github/workflows/daily-repo-activity.md --validate
```

---

## 🎯 Next Steps

- **[Setup Guide](./setup.md)** - Detailed installation instructions
- **[Workflows](./workflows.md)** - Overview of available workflows
- **[Creating Workflows](./creating-workflows.md)** - Build your own
- **[Troubleshooting](./troubleshooting.md)** - If something goes wrong

---

## 💡 Tips

### Monitor Workflow Runs

```bash
# See recent runs
gh run list

# Check specific workflow status
gh run list --workflow daily-repo-activity.lock.yml
```

### Manual Trigger with Parameters

```bash
# Run with custom message in body
gh workflow run daily-repo-activity.lock.yml \
  -f message="Custom message here"
```

### Debug a Failed Run

```bash
# See last run of a workflow
gh run list --workflow daily-repo-activity.lock.yml --limit 1 --json number --jq .[0].number

# View logs of specific run
gh run view <run-id> --log
```

---

## ⌚ Cron Time Zones

All cron times are in **UTC**.

**Common times in UTC:**

| Time | Cron |
|------|------|
| 9:00 AM UTC | `0 9 * * *` |
| 12:00 PM (noon) UTC | `0 12 * * *` |
| 6:00 PM UTC | `0 18 * * *` |
| Midnight UTC | `0 0 * * *` |
| Every 6 hours | `0 */6 * * *` |
| Weekdays at 9 AM | `0 9 * * 1-5` |
| Monday-Friday 9 AM | `0 9 * * MON-FRI` |

---

## 🎓 Understanding the Files

### `.github/workflows/daily-repo-activity.md`

Your workflow definition in plain Markdown:
- Human-readable intent
- Edit this file to change behavior
- Must run `gh aw compile` after editing

### `.github/workflows/daily-repo-activity.lock.yml`

Auto-generated compiled workflow:
- Executed by GitHub Actions
- Don't edit manually
- Regenerated when you compile

### `.gitattributes`

Git configuration:
- Tells Git how to handle lock files
- Uses `merge=binary` for safety

---

## 🔗 Resources

- **Official Docs**: https://github.github.io/gh-aw/
- **Quick Start Guide**: https://github.github.io/gh-aw/setup/quick-start/
- **Workflow Gallery**: https://github.github.io/gh-aw/blog/

---

**Ready to go!** Your repository has Agentic Workflows running.

Check back in a few days to see your first daily report! 📊
