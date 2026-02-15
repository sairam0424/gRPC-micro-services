# Merge Strategy: Lock File Management

Guide to handling GitHub Agentic Workflows lock files during merges.

---

## 🔍 Overview

GitHub Agentic Workflows use two complementary files:

- **`.md` files** - Workflow definitions (human-readable, edit these)
- **`.lock.yml` files** - Compiled workflows (auto-generated, don't edit)

The `.lock.yml` files are generated from `.md` files and executed by GitHub Actions.

---

## ⚠️ Why Merge Strategy Matters

### The Problem with `merge=ours`

The old `merge=ours` strategy **silently discards incoming changes**:
- A team member updates a workflow on branch A
- You merge branch B into main (which also touched the same workflow)
- Their changes are lost without warning ❌

### The Solution: `merge=binary`

The new `merge=binary` strategy **requires explicit conflict resolution**:
- Git treats `.lock.yml` files as binary
- Conflicts must be intentionally resolved
- No silent loss of changes ✅

---

## 📋 Git Configuration

### Current `.gitattributes`:

```properties
# GitHub Agentic Workflows lock files
# Use merge=binary to prevent silent loss of changes during merges
# After resolving conflicts on .lock.yml files, regenerate them by running:
#   gh aw compile [workflow-name].md
# to ensure consistency with the .md source and avoid dependency update loss
.github/workflows/*.lock.yml linguist-generated=true merge=binary
```

**What this does:**
- `linguist-generated=true` - Don't count in language statistics
- `merge=binary` - Require explicit conflict resolution

---

## 📖 Merge Workflow

### Scenario 1: Merging branches with workflow changes

```bash
# 1. Start the merge
git merge feature/my-new-workflow

# 2. If merge conflict occurs on .lock.yml files:
#    Git will mark them as conflicted

# 3. Resolve conflicts
#    - Review both versions
#    - Choose the appropriate version
#    - Or manually merge if needed
git add .github/workflows/<workflow-name>.lock.yml

# 4. Continue merge
git merge --continue

# 5. IMPORTANT: Regenerate all lock files
gh aw compile

# 6. Verify changes
git status
gh aw compile --validate

# 7. Commit the regenerated files
git add .github/workflows/*.lock.yml
git commit -m "Regenerate lock files after merge from feature/my-new-workflow"

# 8. Push
git push
```

### Scenario 2: Resolving a merge conflict

**When you see:**
```
CONFLICT (content): Merge conflict in .github/workflows/daily-repo-activity.lock.yml
```

**Actions:**

```bash
# 1. See the conflict
git status
# Output: both modified: .github/workflows/daily-repo-activity.lock.yml

# 2. Review the markdown source (not the lock file!)
cat .github/workflows/daily-repo-activity.md

# 3. Decide which version is correct or integrate both
# (The .md file is the source of truth)

# 4. Regenerate from the .md source
gh aw compile .github/workflows/daily-repo-activity.md

# 5. The lock file now reflects the merged state
git add .github/workflows/daily-repo-activity.lock.yml
git add .github/workflows/daily-repo-activity.md

# 6. Complete the merge
git merge --continue

# 7. Push
git push
```

---

## ✅ Post-Merge Checklist

After merging branches that touched agentic workflows:

- [ ] All merge conflicts resolved
- [ ] Lock files regenerated (`gh aw compile`)
- [ ] Workflows validated (`gh aw compile --validate`)
- [ ] Changes committed
- [ ] Everything pushed

---

## 🛡️ Best Practices

### Do:

✅ Always regenerate lock files after merges
```bash
gh aw compile
```

✅ Validate before committing
```bash
gh aw compile --validate
```

✅ Edit `.md` files, not `.lock.yml`
```bash
# Good: Edit the source
vim .github/workflows/my-workflow.md
gh aw compile

# Bad: Don't manually edit lock files
vim .github/workflows/my-workflow.lock.yml
```

✅ Commit lock file updates explicitly
```bash
git commit -m "Regenerate workflow lock files after merge"
```

### Don't:

❌ Revert to `merge=ours` strategy
- This silently loses changes

❌ Manually edit `.lock.yml` files
- Changes will be lost when regenerated

❌ Skip regeneration after merges
- Lock files will become stale and inconsistent

❌ Ignore validation warnings
- They indicate syntax errors or conflicts

---

## 🔧 Complete Merge Example

**Real-world scenario:** Merging a feature branch with workflow updates

```bash
# 1. Check current status
git status
# On branch feature/github-workflows

# 2. Merge main into current branch
git fetch origin
git merge origin/main

# 3. Conflict detected
# CONFLICT (content): Merge conflict in .github/workflows/daily-repo-activity.lock.yml

# 4. Check what changed in the .md source
git diff HEAD origin/main -- .github/workflows/daily-repo-activity.md

# 5. Regenerate lock files to resolve conflict
gh aw compile

# 6. Validate the merged workflows
gh aw compile --validate
# Output: ✓ daily-repo-activity.md

# 7. Verify git status
git status
# modified: .github/workflows/daily-repo-activity.lock.yml

# 8. Commit the resolved state
git add .github/workflows/daily-repo-activity.lock.yml
git commit -m "Resolve merge conflict: regenerate workflow lock files"

# 9. Continue with your merge/rebase
git merge --continue

# 10. Push the result
git push
```

---

## 📚 Reference

### Related Commands

```bash
# Regenerate specific workflow
gh aw compile .github/workflows/<name>.md

# Regenerate all workflows
gh aw compile

# Validate workflow syntax
gh aw compile --validate

# View git merge strategies
git help merge

# Check merge driver configuration
git config merge.binary.driver
```

### Useful Git Configuration

Check your current merge settings:
```bash
# View .gitattributes
cat .gitattributes

# View git config for merge drivers
git config --local --list | grep merge

# Show all attributes for lock files
git check-attr -a .github/workflows/daily-repo-activity.lock.yml
```

---

## 🆘 Troubleshooting Merges

### "Merge conflict cannot be resolved automatically"

```bash
# Regenerate lock files first
gh aw compile

# If still unresolved, check the .md source for conflicts
git diff --ours -- .github/workflows/*.md
git diff --theirs -- .github/workflows/*.md
```

### "Lock file is out of sync with .md file"

```bash
# Regenerate to sync
gh aw compile

# Validate consistency
gh aw compile --validate
```

### "Validation fails after merge"

```bash
# Check specific workflow
gh aw compile --validate .github/workflows/<name>.md

# See detailed errors
gh aw compile .github/workflows/<name>.md 2>&1 | head -50
```

---

## 📖 See Also

- [GitHub Agentic Workflows Docs](https://github.github.io/gh-aw/)
- [Setting up merge drivers](https://git-scm.com/book/en/v2/Customizing-Git-Git-Attributes#Merge-Strategies)
- [Setup Guide](./setup.md)
- [Command Reference](./reference.md)

---

**Last Updated**: February 16, 2026
**Strategy**: `merge=binary` for `.lock.yml` files
