# Agentic Workflows Lock File Management

## Overview

GitHub Agentic Workflows use `.lock.yml` files in `.github/workflows/` that are generated from `.md` workflow definitions. These lock files should be treated specially during merges to prevent loss of updates.

## Why Binary Merge Strategy?

The `.gitattributes` configuration uses `merge=binary` for `*.lock.yml` files to prevent silent conflicts that could lose important changes. Unlike the old `merge=ours` strategy that could silently discard incoming changes, `merge=binary` requires explicit conflict resolution.

## Post-Merge Lock File Regeneration

When merging branches that modify agentic workflows (.md files), the lock files may become stale or conflicted. Follow these steps:

### 1. During Merge Conflict

If you encounter a merge conflict on a `.lock.yml` file:

```bash
# Accept the version from your branch, or manually review both versions
git add .github/workflows/<workflow-name>.lock.yml
```

### 2. After Merge Completion

Regenerate the lock file from the source markdown to ensure consistency:

```bash
# Regenerate the specific workflow lock file
gh aw compile .github/workflows/<workflow-name>.md

# Or regenerate all workflows
gh aw compile
```

### 3. Commit the Regenerated Lock File

```bash
git add .github/workflows/<workflow-name>.lock.yml
git commit -m "Regenerate lock file for <workflow-name> after merge"
git push
```

## Why Is This Necessary?

- The `.md` files contain the workflow definition and intent
- The `.lock.yml` files contain the compiled, validated workflow that GitHub Actions executes
- When branches diverge, regenerating ensures:
  - Consistency between `.md` and `.lock.yml`
  - No silent loss of dependency updates
  - Validated workflow syntax
  - Proper schema compliance

## Example Workflow: Merging Feature Branch

```bash
# 1. Start merge
git merge feature/my-workflow

# 2. If conflicts occur on .lock.yml files:
# Review and accept appropriate version, then:
git add .github/workflows/*.lock.yml

# 3. Continue merge
git merge --continue

# 4. Regenerate all lock files
cd <project-directory>
gh aw compile

# 5. Verify and commit
git status
git add .github/workflows/*.lock.yml
git commit -m "Regenerate agentic workflow lock files after merge"
git push
```

## Best Practices

✅ **Do:**
- Always regenerate lock files after merges that modify `.md` workflow files
- Test workflows after merge/regeneration
- Commit lock file updates explicitly
- Use `gh aw compile --validate` to verify before committing

❌ **Don't:**
- Manually edit `.lock.yml` files (edit the `.md` file instead)
- Use `merge=ours` strategy (can silently lose changes)
- Skip lock file regeneration after merges
- Commit lock file conflicts unresolved

## Verification

After regenerating lock files, validate them:

```bash
# Validate all workflows
gh aw compile --validate

# Validate specific workflow
gh aw compile .github/workflows/<workflow-name>.md --validate
```

## References

- [GitHub Agentic Workflows Documentation](https://github.github.io/gh-aw/)
- [gh-aw CLI Reference](https://github.github.io/gh-aw/reference/)
- Git merge strategies: `git help merge`
