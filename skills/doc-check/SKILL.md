---
name: doc-check
description: Verify that project documentation (README.md, CLAUDE.md, API docs, and so on) matches the reality of the codebase, and fix the inconsistencies automatically. Use when the user says "doc-check", "check the documentation", "documentation consistency", or "check the docs". With no argument it covers the last 5 commits, a number specifies the commit count, `all` checks everything, and a file path checks that document alone. A general-purpose skill usable in any project.
---

# Doc Check

Artifact paths follow the [Artifact Store consumer contract](../shared/references/artifact-paths.md). Resolve and validate the store before reading or writing artifacts.

Skill that verifies consistency between documentation and the codebase, and auto-fixes discrepancies.

## Arguments

- None: Target changes from the last 5 commits
- Number (e.g., `10`): Target changes from the last N commits
- `all`: Target the entire project
- File path (e.g., `CLAUDE.md`, `docs/api.md`): Target only the specified document(s). Multiple files can be separated by spaces

## Phase 1: Discovery

### 1.1 Document Detection

**File path mode** — When arguments contain file path(s) (not a number, not `all`):

1. Verify each specified file exists and is a `.md` file
2. Use only those files as targets — skip the full document detection below
3. If a file does not exist, report it as an error and continue with remaining files

**Default mode** — Detect documentation files in the project:

```bash
# .md files at root
ls *.md 2>/dev/null

# docs/ directory
find docs/ -name '*.md' 2>/dev/null

# CLAUDE.md (project root and .claude/)
ls CLAUDE.md .claude/CLAUDE.md 2>/dev/null
```

Exclude: `node_modules/`, `vendor/`, `.git/`, `CHANGELOG.md`, `LICENSE.md`, `.agents/artifacts/plans/` (plan files are not targets)

### 1.2 Scope Determination

Obtain change context based on arguments:

```bash
# Default (5 commits) or specified number
git log -N --oneline
git diff HEAD~N..HEAD --name-only
git diff HEAD~N..HEAD

# File path mode
# No diff is obtained. Check the specified file(s) against the entire project structure (same as all mode)

# all mode
# No diff is obtained. Target the entire project structure
```

## Phase 2: Structural Check

Cross-reference the file system state against structural descriptions in documentation.
See [references/structural-checks.md](references/structural-checks.md) for detailed detection methods.

### Execution Steps

1. Read each document
2. Detect the following patterns:
   - File/command/module listings in Markdown tables
   - Directory tree diagrams (`├──` `└──` patterns)
   - File path references in code blocks
   - Version number mentions
3. Compare against the actual file system state
4. Detect discrepancies and immediately fix those that are fixable

### Auto-Fix Principles

- **Missing entries**: Add following the format of existing entries
- **Extra entries**: Do not delete; report as WARN (may be intentional)
- **Apply fixes as incremental edits** (edit only the relevant spot, never overwrite the whole file)

## Phase 3: Content Check

Semantic consistency check leveraging LLM capabilities.
See [references/content-checks.md](references/content-checks.md) for detailed perspectives and agent instructions.

### Execution Steps

Launch a subagent **in parallel** for each document:

- Provide each agent with the target document content and change context (diff)
- Have them verify from 4 perspectives: architecture descriptions, workflow descriptions, configuration descriptions, and API documentation
- Have them classify results by fix action (AUTO_FIX / NEEDS_JUDGMENT / OK).
  AUTO_FIX / NEEDS_JUDGMENT follow the shared
  [fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md); `OK` is
  doc-check's own third value (see that contract's "Difference from doc-check's `OK`" section) —
  this axis is orthogonal to severity

In `all` mode, since there is no diff, have agents explore the project structure from scratch.

### Processing Results

1. AUTO_FIX: apply the fix as an incremental edit, following the proposed fix
2. NEEDS_JUDGMENT: confirm with the user first, then fix based on the answer
3. OK: Record as-is

## Phase 4: Report

After all checks are complete, aggregate and display results:

```
══════════════════════════════════════
DOC-CHECK ({scope}: {N} commits / all)
══════════════════════════════════════

✅ Auto-fixed ({N} items)
  - {file}: {fix summary}

⚠️ Needs review ({N} items)
  - {file}: {discrepancy description}

✅ Consistent ({N} items)
  - {file}: {section} → OK

══════════════════════════════════════
```

## Important Rules

- **Do not commit changes** — Only apply fixes; leave committing to the user
- **Maintain generality** — Do not hardcode specific project structures. Detect dynamically from actual state
- **Do not delete extra entries** — They may be intentionally kept; only report them
