---
name: commit
description: 変更内容を分析し、論理単位で自動コミットする。確認なしで即実行。
---

# Auto Commit

Skill that analyzes changes and automatically commits them in logical units without asking for user confirmation.

## Core Principles

1. **No confirmation** — Analyze and execute in one pass. Never prompt the user for confirmation
2. **Logical units** — Group related changes into a single commit, split unrelated changes
3. **No half-baked commits** — Never commit broken code
4. **Safety first** — Never perform destructive operations

## Phase 1: Information Gathering

Execute the following **in parallel**:

```bash
git status
git diff
git diff --staged
git log -5 --format='[%h] %an <%ae> | %ar | %s'
git log -1 --format='%H %an %ae'
git branch -vv
```

## Phase 1.5: Best-Effort Test Verification

**Verification Gate** (best-effort): `skills/shared/references/verification-gate.md` をベストエフォートで適用する。commit の Core Principle「No confirmation」を遵守し、テスト失敗でブロックしない。

1. テストフレームワークを自動検出する:
   - `package.json` (scripts.test) → `npm test`
   - `Cargo.toml` → `cargo test`
   - `go.mod` → `go test ./...`
   - `pyproject.toml` / `pytest.ini` → `pytest`
   - `Makefile` (test ターゲット) → `make test`
2. テストフレームワークが検出できた場合、`shell` でテストスイートを実行する（タイムアウト: 120秒）
3. 結果に応じた処理:
   - **全パス**: 通常通りコミットに進む
   - **テスト失敗**: コミットメッセージ body に `⚠️ Tests failing: {failure_summary}` を追記してコミット続行
   - **テストフレームワーク不明**: スキップ（従来通り即コミット）
   - **タイムアウト**: スキップしてコミット続行

## Phase 2: Sanity Check

**Abort the commit** and report the reason if any of the following conditions are met:

### Abort Conditions

- **No changes**: Neither staged nor unstaged changes exist
- **main/master branch**: Do not commit directly (warn user and exit)
- **Merge conflict in progress**: Unresolved conflict markers exist
- **Obviously broken state**:
  - Files containing syntax errors (quick check only when few files are changed)
  - Added module references where import/require targets don't exist

> **Note**: Sanity checks should be lightweight. Do not run full builds or test suites. Only detect obvious syntactic breakage.

## Phase 3: Analysis and Strategy

### 3.1 Change Classification

Classify each file's changes along the following axes:

- **Path**: src/ / test/ / docs/ / config/ etc.
- **Nature of change**: feat / fix / refactor / docs / test / chore / style / perf
- **Relatedness**: Whether they belong to the same feature/purpose

### 3.2 Commit Strategy

#### A. Single Commit

When all changes belong to the same purpose/theme.

```
Example: src/auth.ts, src/auth.test.ts, src/types/auth.ts
→ All related to auth feature → 1 commit
```

#### B. Split into Multiple Commits

When independent changes are mixed, split by logical unit.

```
Example:
  Change 1: src/user.ts (new feature)
  Change 2: README.md (documentation update)
→ Split into feat: ... and docs: ... as 2 commits
```

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
- **subject**: Japanese or English (match the style of the project's existing commit history)
- **body**: Only when background explanation is needed. Omit if unnecessary
- **footer**: Do not include by default

### Execution Steps

1. Stage necessary files with `git add` according to the strategy
   - Do not use `git add -A` or `git add .`. Specify files individually
   - Exclude sensitive files such as `.env`, credentials, private keys, etc.
2. Execute `git commit` (pass message via HEREDOC format)
3. For multiple commits, repeat in order
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
- Prompting the user for confirmation (using request_user_input)
