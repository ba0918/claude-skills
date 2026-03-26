---
name: doc-check
description: プロジェクトのドキュメント（README.md、CLAUDE.md、API ドキュメント等）とコードベースの実態の整合性を検証し、不整合を自動修正する。「doc-check」「ドキュメントチェック」「ドキュメント整合性」「docs 確認」で起動。引数なしで直近5コミット、数値で指定コミット数、`all` で全体チェック。汎用スキル — あらゆるプロジェクトで使用可能。
---

# Doc Check

Skill that verifies consistency between documentation and the codebase, and auto-fixes discrepancies.

## Arguments

- None: Target changes from the last 5 commits
- Number (e.g., `10`): Target changes from the last N commits
- `all`: Target the entire project

## Phase 1: Discovery

### 1.1 Document Detection

Detect documentation files in the project:

```bash
# .md files at root
ls *.md 2>/dev/null

# docs/ directory
find docs/ -name '*.md' 2>/dev/null

# CLAUDE.md (project root and .claude/)
ls CLAUDE.md .claude/CLAUDE.md 2>/dev/null
```

Exclude: `node_modules/`, `vendor/`, `.git/`, `CHANGELOG.md`, `LICENSE.md`, `docs/plans/` (plan files are not targets)

### 1.2 Scope Determination

Obtain change context based on arguments:

```bash
# Default (5 commits) or specified number
git log -N --oneline
git diff HEAD~N..HEAD --name-only
git diff HEAD~N..HEAD

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
- **Use the Edit tool for fixes** (do not overwrite entire files with Write)

## Phase 3: Content Check

Semantic consistency check leveraging LLM capabilities.
See [references/content-checks.md](references/content-checks.md) for detailed perspectives and agent instructions.

### Execution Steps

Launch Agent tools (general-purpose) **in parallel** for each document:

- Provide each agent with the target document content and change context (diff)
- Have them verify from 4 perspectives: architecture descriptions, workflow descriptions, configuration descriptions, and API documentation
- Have them classify results by severity (AUTO_FIX / NEEDS_JUDGMENT / OK)

In `all` mode, since there is no diff, have agents explore the project structure from scratch.

### Processing Results

1. AUTO_FIX: Apply fixes using the Edit tool based on the fix suggestion
2. NEEDS_JUDGMENT: Confirm with user via AskUserQuestion, then fix based on their response
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
- **Run structural checks first** — Perform fast, reliable structural checks first; defer costly content checks
- **Leverage parallel execution** — Run content checks in parallel agents per document to reduce processing time
