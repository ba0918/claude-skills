---
name: commit
description: 変更内容を分析し、論理単位で自動コミットする。確認なしで即実行。「コミットして」「commit」「変更を保存して」で起動。
---

# Auto Commit

Skill that analyzes changes and automatically commits them in logical units without asking for user confirmation.

## Core Principles

1. **No confirmation** — Analyze and execute in one pass. Never prompt the user for confirmation
2. **Logical units** — Group related changes into a single commit, split unrelated changes
3. **No half-baked commits** — Never commit broken code
4. **Safety first** — Never perform destructive operations

## Phase 1: Information Gathering

Execute the following (a single batched shell call is fine):

```bash
git status
git diff
git diff --staged
git log -5 --format='[%h] %an <%ae> | %ar | %s'
git log -1 --format='%H %an %ae'
git branch -vv
```

## Phase 1.5: Best-Effort Test Verification

Apply the "commit への統合" section of the [Verification Gate contract](../shared/references/verification-gate.md) on a best-effort basis. Run the test suite only when a test framework is detected (timeout 120s; on timeout, skip and continue). On test failure, append `⚠️ Tests failing: {failure_summary}` to the commit message body and continue. If no framework is detected, skip. Never block on test failure (Core Principle "No confirmation").

Detection map: `package.json` (scripts.test) → `npm test` / `Cargo.toml` → `cargo test` / `go.mod` → `go test ./...` / `pyproject.toml`, `pytest.ini` → `pytest` / `Makefile` (test target) → `make test`

If nothing in the detection map matches, skip and move on — do not search beyond these marker files (detection deliberately stops here).

## Phase 2: Sanity Check

**Abort the commit** and report the reason if any of the following conditions are met:

### Abort Conditions

- **No changes**: No staged, unstaged, **or untracked** changes exist. Untracked files alone do not trigger this abort condition — they must still be evaluated in Phase 3
- **main/master branch**: Do not commit directly (warn user and exit)
- **Merge conflict in progress**: Unresolved conflict markers exist
- **Obviously broken state**:
  - Files containing syntax errors (quick check only when few files are changed)
  - Added module references where import/require targets don't exist

> **Note**: Sanity checks should be lightweight. Do not run full builds or test suites. Only detect obvious syntactic breakage.

## Phase 3: Analysis and Strategy

### 3.1 Change Classification

Classify each file's changes along the following axes, **including untracked files** (not just staged/modified ones):

- **Path**: src/ / test/ / docs/ / config/ etc.
- **Nature of change**: feat / fix / refactor / docs / test / chore / style / perf
- **Relatedness**: Whether they belong to the same feature/purpose

**Exclusion rules** (applies to untracked and modified files alike):
- **Sensitive files** (`.env`, credentials, private keys, etc.): always exclude. Judge by file name/kind, not contents — exclude even if the contents look like dummy values
- **Non-work-products** (verification-harness byproducts, temporary/scratch files): exclude when clearly not a user work product
- When excluding, state the excluded file(s) and the reason in the Phase 5 report

**Type selection**: When multiple types are defensible (e.g. a new utility could be feat or chore), pick by the change's primary purpose: user-facing capability → feat, dev support/config → chore. If both remain defensible, default to feat.

### 3.2 Commit Strategy

#### A. Single Commit

When all changes belong to the same purpose/theme (e.g. implementation + its tests + its type definitions).

#### B. Split into Multiple Commits

When independent changes are mixed, split by logical unit.

**Criteria for splitting:**
- Different Conventional Commits types are mixed (feat + docs, etc.)
- Multiple independent features/bug fixes
- Changes that may need to be reverted separately in the future

**Do not split when:**
- Tests and implementation belong to the same feature (group under feat)
- Type definitions and the implementation code that uses them

#### C. Amend

Amend the previous commit **only** when **all** of the following are true:

1. The previous commit has not been pushed (ahead of remote tracking branch)
2. The previous commit was authored by yourself
3. The changes clearly belong to the same theme as the previous commit
4. The combined size is reasonable (<50 files & <1000 lines)
5. The combined result is still understandable as a single logical unit

## Phase 4: Execution

### Commit Message Format

```
<type>: <subject>

<body (only if necessary)>
```

- **type**: Conventional Commits (feat / fix / docs / style / refactor / perf / test / chore)
- **subject**: Japanese or English (match the style of the project's existing commit history; if the history is empty or mixed, use the language of the conversation with the user)
- **body**: Only when background explanation is needed. Omit if unnecessary
- **footer**: Do not include by default

### Execution Steps

1. Stage necessary files with `git add` according to the strategy
   - Do not use `git add -A` or `git add .`. Specify files individually
   - Files excluded in Phase 3.1 (sensitive files / non-work-products) must not be staged
2. Execute `git commit` (pass message via HEREDOC format)
3. For multiple commits, repeat in order (commit order among independent units is free — dependency order only matters when one change builds on another)
4. For amend, use `git commit --amend`

### Pre-commit Hook Failure

1. Check files auto-fixed by the hook
2. If the fix is safe (e.g., auto-formatting):
   - Re-stage the fixed files
   - Re-execute as a **new commit** (do not amend — the commit itself was not created when the hook failed)
3. For other errors: Report the reason and abort

## Phase 5: Report

Report execution results concisely.

### On Success

```
✅ <N> commit(s) completed

[abc1234] feat: Add user authentication
  - src/auth.ts, src/auth.test.ts, src/types/auth.ts

[def5678] docs: Update README
  - README.md
```

### On Abort

```
⛔ Commit aborted: <reason>
```

## Prohibited Actions

- Using `--no-verify`
- Amending pushed commits
- Auto-executing `git rebase -i`
- `git push --force`
- `git reset --hard`
- Prompting the user for confirmation
