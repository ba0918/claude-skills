---
name: doc-check
description: Verify that project documentation (README.md, CLAUDE.md, API docs, docs/spec, and so on) matches the reality of the codebase, and fix the inconsistencies automatically. Use when the user says "doc-check", "check the documentation", "documentation consistency", "check the docs", or wants the trunk's alignment phase (write implementation-induced changes back to docs before a PR). With no argument it covers the last 5 commits, a number specifies the commit count, `all` checks everything, `branch` checks the current branch's diff against the default branch (the alignment station), and a file path checks that document alone. A general-purpose skill usable in any project.
---

# Doc Check

Artifact paths follow the [Artifact Store consumer contract](../shared/references/artifact-paths.md). Resolve and validate the store before reading or writing artifacts.

Skill that verifies consistency between documentation and the codebase, and auto-fixes discrepancies.

## Arguments

- None: Target changes from the last 5 commits
- Number (e.g., `10`): Target changes from the last N commits
- `all`: Target the entire project
- `branch`: Target the current branch's diff against the default branch (merge-base). The trunk's alignment station — run it after implementation and review, before the PR (or, in flows that advance the default branch without a PR, before publication)
- File path (e.g., `CLAUDE.md`, `docs/api.md`): Target only the specified document(s). Multiple files can be separated by spaces

## Phase 1: Discovery

### 1.1 Document Detection

**File path mode** — When arguments contain file path(s) (not a number, not `all`, not `branch`):

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

# branch mode: diff against the default branch from the merge-base.
# Fallback chain origin/HEAD → origin/main → local main — each step changes what
# "base" means: origin/HEAD needs a configured remote HEAD; the final fallback
# compares against the LOCAL main, which may be behind or ahead of the remote.
base_branch=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)
git rev-parse --verify -q "$base_branch" >/dev/null || base_branch=main
base=$(git merge-base "$base_branch" HEAD)
git log "$base"..HEAD --oneline
git diff "$base"..HEAD --name-only
git diff "$base"..HEAD

# File path mode
# No diff is obtained. Check the specified file(s) against the entire project structure (same as all mode)

# all mode
# No diff is obtained. Target the entire project structure
```

In branch mode, decide the stop condition **by branch name, not by diff emptiness**:
when `git rev-parse --abbrev-ref HEAD` equals the default branch name, report "nothing
to align" and stop — a local default branch ahead of its remote yields a non-empty
merge-base diff, and running the immediate AUTO_FIX there would rewrite the default
branch directly. On a feature branch whose diff is empty, likewise report "nothing to
align" and stop.

Note on range: the branch-mode range (merge-base..HEAD) can be wider than a single
cycle's review range (its start SHA..HEAD) when several cycles share one branch.
Already-aligned earlier changes may then resurface as NEEDS_JUDGMENT. This widening is
by design — the station aligns the whole branch, not the latest cycle.

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
- **Extra entries**: Do not delete; classify as NEEDS_JUDGMENT (the extra entry may be
  intentional) — it surfaces in the Phase 4 "⚠️ Needs review" bucket
- **Apply fixes as incremental edits** (edit only the relevant spot, never overwrite the whole file)
- AUTO_FIX in this skill applies immediately, with no per-finding confirmation — the
  declared exception in [fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md):
  nothing is committed, every applied fix is enumerated in the Phase 4 report, and the
  human confirms once at commit / merge review

## Phase 3: Content Check

Semantic consistency check leveraging LLM capabilities.
See [references/content-checks.md](references/content-checks.md) for detailed perspectives and agent instructions.

### Execution Steps

Launch a subagent **in parallel** for each document:

- Provide each agent with the target document content and change context (diff)
- Have them verify from 6 perspectives: architecture descriptions, workflow descriptions, configuration descriptions, API documentation, undocumented-change detection (diff modes only), and spec conformance (when `docs/spec/` exists)
- Have them classify results by fix action (AUTO_FIX / NEEDS_JUDGMENT / OK).
  AUTO_FIX / NEEDS_JUDGMENT follow the shared
  [fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md); `OK` is
  doc-check's own third value (see that contract's "Difference from doc-check's `OK`" section) —
  this axis is orthogonal to severity

In `all` and file-path modes, since there is no diff, have agents explore the project structure from scratch (perspective 5 is skipped in both — it needs a diff to anchor "new"; perspective 6 still runs against the implementation). Spec edits are never AUTO_FIX: a spec is the human-approved statement of what the behavior should be, so every spec-side fix routes through NEEDS_JUDGMENT (see content-checks perspective 6).

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
