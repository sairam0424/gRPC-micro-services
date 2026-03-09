# Agent Context Strategy

Goal: keep agent context deterministic, minimal, and grounded in source-of-truth files.

## Context Loading Order
1. `AGENTS.md`
2. `ARCHITECTURE.md`
3. relevant product spec and active execution plan
4. targeted technical deep docs
5. proto contracts and touched code

## Context Budget Rules
- Load only the files needed for the current task.
- Prefer canonical docs over repeated ad hoc summaries.
- If a fact is uncertain, re-check code/contract files before planning.

## Anti-Patterns
- Broad, unfocused context loading.
- Using stale secondary docs when canonical docs exist.
- Proceeding with unresolved architecture contradictions.

## Output Discipline
Every substantial task output should include:
- linked plan/spec
- validation evidence
- debt/quality updates when needed
