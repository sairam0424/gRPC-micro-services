# 🤖 GitHub Agentic Workflows Setup Guide

This guide provides step-by-step instructions for managing and creating new GitHub Actions workflows using the **GitHub Agentic Workflows** (`gh-aw`) tool.

---

## 📋 Overview

Unlike traditional GitHub Actions which use YAML, this repository uses **Agentic Workflows**. These allow you to define complex automation logic in plain **Markdown** (`.md` files) which are then compiled into standardized Action YAMLs.

**Key Files:**
- `.github/workflows/*.md`: Source workflow definition (Edit this!)

- `.github/workflows/*.lock.yml`: Compiled workflow (Auto-generated, do not edit!)

---

## 🚀 Setting Up a New Workflow

Follow these steps to create a new automated task:

### 1. Initialize the Workflow

Use the `gh aw` CLI to scaffold a new workflow:

```bash
gh aw new my-awesome-workflow
```

This creates:
- `.github/workflows/my-awesome-workflow.md`

### 2. Edit the Workflow Definition
Open the `.md` file. The structure includes:
- **Frontmatter (YAML)**: Configuration for triggers (`on: schedule`), permissions, and `safe-outputs`.
- **Markdown Body**: Instructions for the agent on what to do.

**Best Practice - Schedules:**
Always use fuzzy schedules to avoid hitting GitHub API load spikes:

```yaml
on:
  schedule:
    - cron: 'daily'  # Use 'daily', 'weekly', or 'monthly' instead of fixed UTC times
```

### 3. Compile the Workflow

Whenever you modify the `.md` file, you **must** recompile it into a lock file:

```bash
gh aw compile .github/workflows/my-awesome-workflow.md
```

This generates `.github/workflows/my-awesome-workflow.lock.yml`.

### 4. Validate (Optional but Recommended)

Ensure your workflow is syntactically correct and respects security boundaries:

```bash
gh aw compile --validate .github/workflows/my-awesome-workflow.md
```

### 5. Commit and Push

Both the `.md` and `.lock.yml` files must be committed:

```bash
git add .github/workflows/my-awesome-workflow.md .github/workflows/my-awesome-workflow.lock.yml
git commit -m "feat: add new agentic workflow for [purpose]"
git push
```

---

## 🛠️ Common Operations

### Manual Trigger

If you want to run a workflow immediately without waiting for the schedule:

```bash
gh workflow run my-awesome-workflow.lock.yml
```

### Viewing Logs

To see what the agent actually did during a run:

```bash
gh aw logs my-awesome-workflow
```

### Resolving Merge Conflicts

If multiple people edit the same workflow, conflicts often occur in the `.lock.yml` file.

1. Resolve conflicts in the `.md` file manually.
2. Run `gh aw compile` to regenerate the `.lock.yml` and resolve its conflicts automatically.
3. Commit both files.

### Secret Mapping Reference

If you are using a custom PAT name like `GH_PAT`, you can map it in the workflow frontmatter as a fallback:

```yaml
env:
  GH_AW_GITHUB_TOKEN: ${{ secrets.GH_PAT }}
  COPILOT_GITHUB_TOKEN: ${{ secrets.GH_PAT }}
```

However, the compiled workflow code is optimized to look for `GH_AW_GITHUB_TOKEN` and `COPILOT_GITHUB_TOKEN` directly in your repository secrets. It is **highly recommended** to set those exact names in GitHub to avoid authentication issues.

---

## 🆘 Troubleshooting

### "Unable to pin action" Warning
**Issue:** `⚠ Unable to pin action github/gh-aw/actions/setup@v0.44.0: resolution failed`

**Explanation:** This warning occurs during compilation if the tool cannot resolve a version tag (like `@v0.44.0`) to a specific Git SHA. 

**Fix:** As long as the compilation finishes (✓), the workflow will still work. If you are on a restricted network, this warning is expected.

### "Fixed daily time" Warning

**Issue:** `⚠ Schedule uses fixed daily time...`

**Fix:** In your `.md` file, change your cron trigger to use a descriptive frequency:

- Instead of `- cron: '0 9 * * *'`

- Use `- cron: 'daily'`

---

## 📚 Related Resources
- [Detailed Reference](./agentic-workflows/reference.md)
- [Troubleshooting Guide](./agentic-workflows/troubleshooting.md)
- [Official Documentation](https://github.github.io/gh-aw/)

## 🔑 Required Secrets

For workflows to run successfully, you **must** configure the following secrets in your GitHub repository (**Settings > Secrets and variables > Actions**):

1. **`COPILOT_GITHUB_TOKEN`**: A token authorized to use the GitHub Copilot API.
2. **`GH_AW_GITHUB_TOKEN`**: A Personal Access Token (PAT) with `repo` and `workflow` scopes.

> [!TIP]
> You can create a single PAT with the necessary scopes and use its value for **both** secrets above. 
