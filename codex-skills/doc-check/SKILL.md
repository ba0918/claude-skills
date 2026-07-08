---
name: doc-check
description: プロジェクトのドキュメント（README.md、AGENTS.md / CLAUDE.md、API ドキュメント等）とコードベースの実態の整合性を検証し、不整合を自動修正する。「doc-check」「ドキュメントチェック」「ドキュメント整合性」「docs 確認」で起動。引数なしで直近5コミット、数値で指定コミット数、`all` で全体チェック、ファイルパスで特定ドキュメントのみチェック。汎用スキル — あらゆるプロジェクトで使用可能。
---

# Doc Check (Codex Edition)

Skill that verifies consistency between documentation and the codebase, and auto-fixes discrepancies.

## Codex CLI ツールの使い分け

- **shell**（検証コマンド） — ドキュメントの読取（`cat`）・ファイルシステム状態の確認（`ls` / `find` / `rg` / `grep`）・変更コンテキストの取得（`git log` / `git diff`）・バージョン照合（`package.json` / `Cargo.toml` / `pyproject.toml` 等の突き合わせ）。構造チェックの機械的な照合はすべて shell で行う
- **spawn_agent** / **wait_agent** — Phase 3（Content Check）の意味的整合検証をドキュメントごとに並行委譲する（承認不要の読み取り専用調査エージェント。委譲後は必要時に `wait_agent` で結果を回収する）
- **apply_patch** — 不整合の自動修正（構造チェックの補完・AUTO_FIX の適用）。ファイル全体を上書きせず該当箇所のみパッチする（shell リダイレクトでのファイル書き込みは禁止）
- **会話ターンでの確認** — NEEDS_JUDGMENT のように解釈が分かれる不整合は、会話ターンで平文の質問（選択肢を列挙し番号/短文で回答を促す）としてユーザに確認する。**Codex の `request_user_input` は Plan mode 限定（default/exec 不可）のため使わない。** headless/exec で応答が得られない文脈では確認を求めず、安全側（自動修正せず報告のみ）に降格する

## Arguments

- None: Target changes from the last 5 commits
- Number (e.g., `10`): Target changes from the last N commits
- `all`: Target the entire project
- File path (e.g., `AGENTS.md`, `docs/api.md`): Target only the specified document(s). Multiple files can be separated by spaces

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

# Project instruction docs (Codex: AGENTS.md / Claude Code: CLAUDE.md — both are valid targets)
ls AGENTS.md CLAUDE.md .codex/AGENTS.md .claude/CLAUDE.md 2>/dev/null
```

Exclude: `node_modules/`, `vendor/`, `.git/`, `CHANGELOG.md`, `LICENSE.md`, `docs/plans/` (plan files are not targets)

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

1. Read each document (`cat` via shell)
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
- **Use apply_patch for fixes** (do not overwrite entire files; patch only the affected lines)

## Phase 3: Content Check

Semantic consistency check leveraging LLM capabilities.
See [references/content-checks.md](references/content-checks.md) for detailed perspectives and agent instructions.

### Execution Steps

Launch **spawn_agent** (approval-free, read-only investigation agents) **in parallel** for each document, and recover results with **wait_agent** when needed:

- Provide each agent with the target document content and change context (diff)
- Have them verify from 4 perspectives: architecture descriptions, workflow descriptions, configuration descriptions, and API documentation
- Have them classify results by fix action (AUTO_FIX / NEEDS_JUDGMENT / OK).
  AUTO_FIX / NEEDS_JUDGMENT follow the shared
  [fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md); `OK` is
  doc-check's own third value (see that contract's "doc-check の `OK` との差異" section) —
  this axis is orthogonal to severity

In `all` mode, since there is no diff, have agents explore the project structure from scratch.

### Processing Results

1. AUTO_FIX: Apply fixes using apply_patch based on the fix suggestion
2. NEEDS_JUDGMENT: Confirm with the user via a plain conversation-turn question (enumerate the options and prompt for a number / short reply), then fix based on their response. In headless/exec contexts where no reply can be obtained, do not ask — downgrade to the safe default (report only, no auto-fix)
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
- **Leverage parallel execution** — Run content checks in parallel spawn_agent per document to reduce processing time
