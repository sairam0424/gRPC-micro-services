# Agentic Workflows

This repository uses **GitHub Agentic Workflows** to automate repository tasks.

## 📚 Documentation

All documentation is organized in [`docs/agentic-workflows/`](./docs/agentic-workflows/):

### Quick Navigation
- **[README](./docs/agentic-workflows/README.md)** - Overview and introduction
- **[Quick Start](./docs/agentic-workflows/quick-start.md)** - Get started in 5 minutes
- **[Setup Guide](./docs/agentic-workflows/setup.md)** - Installation and configuration

### Complete Guides
- **[Workflows](./docs/agentic-workflows/workflows.md)** - Available workflows and usage
- **[Command Reference](./docs/agentic-workflows/reference.md)** - All `gh aw` commands
- **[Merge Strategy](./docs/agentic-workflows/merge-strategy.md)** - Lock file management
- **[Troubleshooting](./docs/agentic-workflows/troubleshooting.md)** - Common issues and solutions

---

## 🚀 Currently Active

**Daily Repository Activity Report**
- Schedule: Every day at 09:00 UTC
- Creates: Daily issue with repository activity summary
- Labels: `report`, `daily`

---

## ⚡ Quick Commands

```bash
# Check installation
gh aw version

# Manually trigger daily report
gh workflow run daily-repo-activity.lock.yml

# View recent reports
gh issue list --label report,daily

# Compile/validate workflows
gh aw compile --validate
```

---

## 📖 Start Here

**New to Agentic Workflows?** → [Quick Start Guide](./docs/agentic-workflows/quick-start.md)

**Need help?** → [Troubleshooting Guide](./docs/agentic-workflows/troubleshooting.md)

**Want all commands?** → [Command Reference](./docs/agentic-workflows/reference.md)

---

## 🔗 External Resources

- [GitHub Agentic Workflows Official Docs](https://github.github.io/gh-aw/)
- [Workflow Gallery](https://github.github.io/gh-aw/blog/)
- [GitHub CLI Documentation](https://cli.github.com/manual/)

---

**Status**: ✅ Active and Running
**Last Updated**: February 16, 2026
