# Troubleshooting: GitHub Agentic Workflows

Solutions for common issues and problems.

---

## 🆘 Installation Issues

### "gh: command not found"

**Problem:** GitHub CLI not installed

**Solution:**
```bash
# Install GitHub CLI
brew install gh              # macOS
sudo apt-get install gh      # Ubuntu/Debian

# Verify
gh version
```

### "gh aw: command not found"

**Problem:** GitHub Agentic Workflows CLI not installed

**Solution:**
```bash
# Install gh-aw
curl -sL https://raw.githubusercontent.com/github/gh-aw/main/install-gh-aw.sh | bash

# Verify
gh aw version
```

### "Permission denied" when installing

**Problem:** No write permissions to installation directory

**Solution:**
```bash
# Check installation directory permissions
ls -la ~/.local/share/gh/extensions/

# Reinstall with correct permissions
curl -sL https://raw.githubusercontent.com/github/gh-aw/main/install-gh-aw.sh | bash
```

---

## 🚀 Workflow Execution Issues

### Workflow doesn't appear in GitHub Actions

**Problem:** Workflow file exists but doesn't show in Actions UI

**Possible causes & solutions:**

```bash
# 1. Check file is on default branch
git status
git log --oneline -1

# 2. Verify file is in correct location
ls -la .github/workflows/

# 3. Check file permissions
ls -la .github/workflows/*.lock.yml

# 4. Verify lock file exists (not just .md)
if [ ! -f .github/workflows/daily-repo-activity.lock.yml ]; then
    echo "Lock file missing"
    gh aw compile .github/workflows/daily-repo-activity.md
fi

# 5. Push changes
git push
```

**Action:** Wait 1-2 minutes after push for GitHub UI to update.

### Scheduled workflow never triggers

**Problem:** Workflow set to run on schedule but doesn't execute

**Possible causes & solutions:**

1. **Cron syntax is invalid**
```bash
# Validate workflow
gh aw compile --validate .github/workflows/daily-repo-activity.md

# Fix syntax error and recompile
gh aw compile .github/workflows/daily-repo-activity.md
```

2. **Schedule is wrong timezone**
```bash
# Check current schedule
grep -A2 "schedule:" .github/workflows/daily-repo-activity.md

# Remember: All cron times are UTC!
# 9 AM UTC = 5 AM EST / 2 AM PST
```

3. **Workflow disabled**
```bash
# Enable workflow
gh workflow enable daily-repo-activity.lock.yml
```

4. **Repository owner hasn't enabled Actions**
```bash
# Check Actions settings in GitHub repository -> Settings -> Actions
```

### Manual trigger doesn't work

**Problem:** Can't manually trigger workflow from GitHub UI or CLI

**Solution:**
```bash
# Try via CLI
gh workflow run daily-repo-activity.lock.yml

# If it fails, check workflow status
gh workflow list

# Enable if disabled
gh workflow enable daily-repo-activity.lock.yml

# Check recent runs
gh run list
```

---

## 🔧 Compilation Issues

### "Compiled X workflow(s): X error(s)"

**Problem:** Compilation fails with validation errors

**Solution:**
```bash
# See detailed errors
gh aw compile .github/workflows/daily-repo-activity.md

# Common issues:
# 1. Incorrect YAML syntax
# 2. Invalid field names
# 3. File encoding issues

# Fix and retry
gh aw compile --validate
```

### "Unknown property: X"

**Problem:** `.md` file contains invalid fields

**Example error:**
```
Unknown property: temporary_id.
Valid fields are: bots, cache, command, ...
```

**Solution:**
```bash
# This is likely a field that belongs in safe-outputs
# Check syntax:

# Wrong:
temporary_id: aw_abc123

# Right (inside safe-outputs):
safe-outputs:
  create-issue:
    temporary_id: aw_abc123
```

### "Write permission not allowed for security reasons"

**Problem:** Workflow tries to write without safe-outputs

**Solution:**
```bash
# Change from direct permission:
permissions:
  issues: write

# To safe-outputs:
safe-outputs:
  create-issue:
    title-prefix: "[Report] "
    labels: [report]
```

### Lock file generation fails

**Problem:** `gh aw compile` command fails

**Solution:**
```bash
# 1. Check gh-aw version
gh aw version
# Ensure v0.44.0 or later

# 2. Upgrade if needed
gh extension upgrade gh-aw

# 3. Remove cache and retry
rm -rf ~/.cache/gh-aw/*
gh aw compile .github/workflows/daily-repo-activity.md

# 4. Check for unsupported syntax
cat .github/workflows/daily-repo-activity.md | head -20
```

---

## 📊 Execution & Results Issues

### Workflow runs but produces no output

**Problem:** Workflow completes but generates no report/issue

**Debugging steps:**
```bash
# 1. Check recent runs
gh run list --workflow daily-repo-activity.lock.yml -L 5

# 2. View most recent run
gh run view <recent-run-id> --log

# 3. Check for errors
gh run view <run-id> --json conclusion
# Should show "success"

# 4. Verify safe-outputs configuration
cat .github/workflows/daily-repo-activity.md | grep -A5 "safe-outputs:"

# 5. Check if issues were created
gh issue list --label report,daily --limit 5
```

### Workflow runs but fails silently

**Problem:** Run appears to complete but nothing happened

**Solution:**
```bash
# View full run output
gh run view <run-id> --log | head -100

# Check step failures
gh run view <run-id> --json steps --jq '.steps[] | select(.conclusion=="failure")'

# Common cause: Agent can't generate output
# Try manual trigger to see error output
gh workflow run daily-repo-activity.lock.yml --debug
```

---

## 🐛 Common Runtime Errors

### "Timeout" or "Step timed out"

**Problem:** Workflow step exceeds timeout

**Solution:**
```bash
# Check current timeout settings
grep "timeout-minutes" .github/workflows/daily-repo-activity.lock.yml

# Increase timeout in .md file
vim .github/workflows/daily-repo-activity.md

# Add to workflow:
timeout-minutes: 20

# Recompile
gh aw compile .github/workflows/daily-repo-activity.md

# Push changes
git push
```

### "Tool not found" or "Command failed"

**Problem:** Step references unavailable tool or command

**Solution:**
```bash
# Check available tools in workflow
grep -i "tools:" .github/workflows/daily-repo-activity.md

# Verify tool configuration
grep -A10 "tools:" .github/workflows/daily-repo-activity.md
```

### "API rate limit exceeded"

**Problem:** Workflow hits GitHub API rate limits

**Solution:**
```bash
# Check current rate limit
gh api rate_limit

# Options:
# 1. Use fewer API calls in workflow
# 2. Add delays between API calls
# 3. Use authenticated requests (higher limits)
# 4. Use GitHub token with higher permissions
```

---

## 📁 File & Git Issues

### Lock file conflicts during merge

**Problem:** Merge conflict on `.lock.yml` file

**Solution:**
```bash
# See merge status
git status

# Regenerate lock file (this resolves conflicts)
gh aw compile

# Stage the resolved file
git add .github/workflows/daily-repo-activity.lock.yml

# Continue merge
git merge --continue

# Push
git push
```

**See also:** [Merge Strategy Guide](./merge-strategy.md)

### ".lock.yml file is out of sync with .md file"

**Problem:** Lock file doesn't match markdown source

**Solution:**
```bash
# Regenerate lock file
gh aw compile

# Verify sync
gh aw compile --validate

# Commit changes
git add .github/workflows/daily-repo-activity.lock.yml
git commit -m "Regenerate lock file to match .md"
git push
```

### Cannot edit files due to permissions

**Problem:** "Permission denied" when editing workflow files

**Solution:**
```bash
# Check file permissions
ls -la .github/workflows/

# Fix permissions if needed
chmod 644 .github/workflows/daily-repo-activity.md
chmod 644 .github/workflows/daily-repo-activity.lock.yml

# Try editing again
vim .github/workflows/daily-repo-activity.md
```

---

## 🔐 Authentication Issues

### "Not authorized" or "Permission denied"

**Problem:** gh CLI can't authenticate with GitHub

**Solution:**
```bash
# Check authentication status
gh auth status

# Re-authenticate
gh auth login

# Choose:
# HTTPS or SSH
# Browser or token auth
# GitHub or GitHub Enterprise

# Verify working
gh api user --jq .login
```

### "Token expired"

**Problem:** GitHub token/authentication expired

**Solution:**
```bash
# Refresh authentication
gh auth refresh

# If that fails, re-authenticate
gh auth login --web

# Verify
gh auth status
```

---

## 📞 Getting Help

### Check Logs for Errors

```bash
# View workflow logs
gh aw logs daily-repo-activity

# View run logs
gh run view <run-id> --log | tail -50

# Save logs for inspection
gh run view <run-id> --log > workflow.log
```

### Validate Configuration

```bash
# Validate workflow syntax
gh aw compile --validate

# Check all workflows
gh aw compile --validate .github/workflows/*.md

# Auto-fix issues where possible
gh aw fix --write
```

### Gather Diagnostic Information

```bash
# Create diagnostic report
echo "=== Versions ===" > diagnostic.txt
gh version >> diagnostic.txt
gh aw version >> diagnostic.txt

echo "=== Workflows ===" >> diagnostic.txt
ls -la .github/workflows/ >> diagnostic.txt

echo "=== Git Info ===" >> diagnostic.txt
git status >> diagnostic.txt
git log --oneline -5 >> diagnostic.txt

echo "=== Recent Runs ===" >> diagnostic.txt
gh run list --limit 5 >> diagnostic.txt

cat diagnostic.txt
```

---

## 🔗 Resources

- [Quick Start Guide](./quick-start.md)
- [Setup Guide](./setup.md)
- [Command Reference](./reference.md)
- [Merge Strategy Guide](./merge-strategy.md)
- [Official Docs](https://github.github.io/gh-aw/)

---

## 📧 Still Having Issues?

1. **Check the [official documentation](https://github.github.io/gh-aw/)**
2. **Review [workflow examples](https://github.github.io/gh-aw/blog/)**
3. **Join GitHub Next Discord**: #agentic-workflows channel
4. **File feedback**: https://gh.io/aw-tp-community-feedback

---

**Last Updated**: February 16, 2026
**gh-aw Version**: v0.44.0
