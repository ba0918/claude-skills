---
name: iterate
description: cycle 完了後の追加指示を、サイズ適応型の軽量改善ループで実行する。修正・機能追加どちらにも対応。「iterate」「追加修正」「ここ直して」「これも追加して」「もうちょっと改善して」で起動。cycle よりも軽く、直接作業よりも品質を担保する中間的なワークフロー。
---

# Iterate

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Skill that auto-determines task size for additional instructions after a cycle, then runs the appropriate improvement loop.

## Flow Overview

```
Additional instruction → Scope analysis → Size judgment ─→ Small → Implement → Light review → Done
                                                         └→ Large → Propose to user ─→ Continue → Implement → Thorough review → Done
                                                                                       └→ Plan → Suggest /claude-skills:plan-create
```

## Phase 0: Acquire Context

1. Identify the latest plan file
   ```bash
   ls -t .agents/artifacts/plans/*.md 2>/dev/null | grep -v _result | head -1
   ```
2. Load context using the following fallback chain:
   - **Plan file exists** → Read it to understand what has already been implemented. No warning.
   - **Plan file not found, `.agents/artifacts/status.md` exists** → Read `.agents/artifacts/status.md` to infer current project state. Display:
     ```
     ⚠️ No plan file found. Using .agents/artifacts/status.md as fallback context.
     ```
   - **Neither exists** → Try `git log --oneline -10` and `git diff HEAD~3 --stat`. If `HEAD~3` cannot be resolved (e.g., fresh repo with fewer than 4 commits), degrade stepwise: `HEAD~1` → `HEAD` → `git log --oneline -10` only. Display based on what was retrieved:
     - git log + diff successful:
       ```
       ⚠️ No plan file or status.md found. Using partial context from git history.
       ```
     - git log only (no diff available):
       ```
       ⚠️ No plan file or status.md found. Only git log available — proceeding with minimal context.
       ```
     - git log also fails (non-git dir or empty repo):
       ```
       ⚠️ No plan file, status.md, or git history found. Proceeding with instructions only.
       ```
3. **Detect previous iterate runs**: Check the plan file (if loaded) for existing `## Additional Changes` sections. If found, use **all** sections as cumulative context (not just the latest) so that consecutive iterate calls build on the complete change history rather than only the most recent increment.
4. Get the user's additional instructions from `$ARGUMENTS`

## Phase 1: Scope Analysis

探索型サブエージェントに委譲して調査する:

1. Compare the additional instructions against existing code and estimate the impact scope
2. List files that need to be changed
3. Determine whether new files need to be created
4. Determine whether design decisions are needed

See [references/scope-criteria.md](references/scope-criteria.md) for detailed criteria.

## Phase 2: Size Judgment and Branching

### Pre-check: Consecutive Call Detection

Before size judgment, check if this is a consecutive iterate call within the same session by looking for `## Additional Changes` sections in the plan file (loaded in Phase 0, Step 3).

**If no plan file was loaded in Phase 0** (fallback path was used), skip this pre-check entirely and treat as 1st call. Display a single-line notice so the skipped check is visible in the log:
```
ℹ️ Consecutive call detection skipped (no plan file loaded).
```

Count `N = (number of ## Additional Changes sections found) + 1` (current call included).

- **N = 2 (2nd call)** → Display a notice but proceed normally:
  ```
  ℹ️ This is the 2nd iterate call in this session.
  ```
- **N >= 3 (3rd+ call)** → Trigger cumulative Large warning（ユーザーに選択肢を提示して確認）:
  ```
  ⚠️ Cumulative iterate detected ({N}th call this session)
  Multiple consecutive iterate calls may indicate the task exceeds iterate's scope.

  Options:
  1. Continue with iterate (cumulative changes will be tracked)
  2. Create a plan via /claude-skills:plan-create (recommended for complex changes)
  ```
  - User selects "1" → Proceed to normal size judgment below
  - User selects "2" → Suggest running `/claude-skills:plan-create` and exit

### If Small

Display:
```
── Scope: Small ──
Affected files: {file_list}
Estimated change size: {estimate}
→ Executing via lightweight loop
```

Proceed to Phase 3.

### If Large

ユーザーに選択肢を提示して判断を仰ぐ:

```
── Scope: Large ──
Affected files: {file_list}
Estimated change size: {estimate}
Reason for Large judgment: {reasons}

Options:
1. Execute via iterate (with thorough review)
2. Create a plan via /claude-skills:plan-create (recommended)
```

- User selects "1" → Proceed to Phase 3 (Large mode)
- User selects "2" → Suggest running `/claude-skills:plan-create` and exit

## Phase 3: Implementation

実装サブエージェントを起動する。Phase 2 のサイズ判定に応じてモデルを選択: **Small** なら軽量モデル（スコープが小さく検証ゲートがあるため安全）、**Large** なら高性能モデル。See [orchestration-patterns.md](../shared/references/orchestration-patterns.md) § Model Tiering.

Instructions to the agent:
- Implement the additional instructions
- Follow existing code style and conventions
- Comply with CLAUDE.md rules
- Reference `.claude/review-rules.md` if it exists
- Follow `skills/shared/references/tdd-contract.md`: write tests FIRST (RED), then minimal implementation (GREEN), then refactor (REFACTOR)
  - **Exception — non-executable changes** (documentation only: README/CHANGELOG/comments/markdown with no behavior change): TDD does not apply. Instead, the implementation agent must (a) state explicitly that TDD is skipped because the change has no executable behavior, and (b) still run the existing test suite to confirm nothing breaks.
    - **Config files are NOT automatically non-executable**: `tsconfig.json` strict-mode flips, `package.json` dep/script changes, linter rule changes, CI workflow edits all affect runtime or build behavior → TDD applies (write a test proving the new behavior, or at minimum a regression test confirming build/test pipeline still passes). Only pure content edits (e.g., `description` field in `package.json`) qualify as non-executable.
- Avoid testing anti-patterns defined in `rules/testing-anti-patterns.md`
- Run existing tests after implementation and confirm all pass

## Phase 4: Review + Codex セカンドオピニオン

See [references/light-review.md](references/light-review.md) for detailed review perspectives.

**レビュー / Codex エージェントを起動する前に**: iterate のメインコンテキストで diff を一度取得し、両エージェントに同じ入力を渡す。
```bash
git diff HEAD           # uncommitted changes, to be committed shortly
# or
git diff <base>..HEAD   # if the implementation agent already committed
```
Store the diff output and inline it into both agent prompts. If the diff exceeds ~50KB, substitute `git diff --stat` + a list of changed files + selected critical hunks instead. Never hand raw source files to Codex — diff only.

### If Small

**2 つのサブエージェントを並行起動する**（同一メッセージで同時に発行）:
1. **レビューエージェント**（高性能モデル）:
   - Security + Implementation Quality の 2 観点でレビュー
   - `.claude/review-rules.md` があれば追加基準として使用
   - `skills/shared/references/verification-gate.md` Gate Function を適用: テスト実行証拠なしで PASS を出さない
     - **例外 — 非実行的変更**（Phase 3 で定義したドキュメントのみの変更）: 既存テストスイートがパスすること、または実行コードへの影響がないことの明示的宣言で Gate Function を満たす。レビューエージェントはどちらのパスを適用するか明記する
   - Findings を BLOCK / WARN / PASS に分類
2. **Codex セカンドオピニオンエージェント**（シェルコマンドのみ使用可能）:
   - change diff (`git diff`) とユーザーの指示をプロンプトに直接提供
   - diff が ~50KB を超える場合は要約 diff（ファイルリスト + `git diff --stat` + 重要な hunks）を渡す
   - 設計上の問題、エッジケース、代替アプローチを求める
   - セキュリティ制約: diff のみを渡し、生のソースファイルは渡さない

### If Large (user chose to continue)

**2 つのサブエージェントを並行起動する**（同一メッセージで同時に発行）:
1. **レビューエージェント**（高性能モデル）:
   - Security + Implementation Quality + Architecture + Completeness の 4 観点でレビュー
   - `.claude/review-rules.md` があれば追加基準として使用
   - `skills/shared/references/verification-gate.md` Gate Function を適用: テスト実行証拠なしで PASS を出さない
     - **例外 — 非実行的変更**（Phase 3 で定義したドキュメントのみの変更）: 既存テストスイートがパスすること、または実行コードへの影響がないことの明示的宣言で Gate Function を満たす。レビューエージェントはどちらのパスを適用するか明記する
   - Findings を BLOCK / WARN / PASS に分類
2. **Codex セカンドオピニオンエージェント**（シェルコマンドのみ使用可能）:
   - change diff (`git diff`) とユーザーの指示をプロンプトに直接提供
   - diff が ~50KB を超える場合は要約 diff（ファイルリスト + `git diff --stat` + 重要な hunks）を渡す
   - 設計上の問題、エッジケース、代替アプローチを求める
   - セキュリティ制約: diff のみを渡し、生のソースファイルは渡さない

### Codex Result Integration

- If Codex agent succeeds: merge Codex findings with `[Codex]` prefix into the review results (deduplicate against existing findings)
- If Codex agent fails: display `⚠️ Codex second opinion unavailable — proceeding with existing review only.` and continue with review agent results only
- Codex findings contribute to WARN/BLOCK judgment. Classify Codex findings using [../shared/references/severity-and-verdicts.md](../shared/references/severity-and-verdicts.md):
  - **Critical** severity (exploitable security hole, data loss, contract violation affecting callers) → BLOCK
  - **High** severity (likely bug, wrong output under common inputs) → BLOCK
  - **Medium** (suboptimal but correct) → WARN
  - **Low** (style, naming, minor refactor hints) → informational only

Common patterns: [../shared/references/codex-integration.md](../shared/references/codex-integration.md)

### Processing Review Results

- **BLOCK found** → Fix and re-review (max 2 iterations)
  - **If BLOCK remains after 2 iterations**: Halt without completion. Display:
    ```
    ⚠️ BLOCK not resolved after 2 fix iterations. Unresolved findings:
    - {finding 1}
    - {finding 2}
    Recommendation: escalate to user — consider /claude-skills:plan-create for a broader design pass,
    or address manually before retrying iterate.
    ```
    Exit without executing Phase 5 or Phase 6. **Never complete with unresolved BLOCK.**
- **WARN only** → Apply fixes and complete
- **All PASS** → Complete as-is

## Phase 5: Traceability

1. Append an "Additional Changes" section to the latest plan file.
   - **If no plan file was loaded in Phase 0** (fallback path was used), skip **this step only** (not step 2). Display:
     ```
     ⚠️ Traceability skipped: no plan file found. Changes are recorded in git commits only.
     ```
   - Step 2 (commit) always runs regardless of plan file presence — the commit itself is the minimum traceability record.

   **`{datetime}` format**: Use `YYYY-MM-DD HH:MM` (24h, local time). Example: `2026-04-21 14:30`.

```markdown

## Additional Changes ({datetime})

### Instructions
{User's additional instructions}

### Changes Made
- {Changed files and summary}

### Review Results
- Security: {PASS|WARN}
- Implementation Quality: {PASS|WARN}
- Codex Second Opinion: {PASS|WARN|unavailable}
```

2. `claude-skills:commit` スキルを呼び出して変更をコミットする

## Phase 6: Completion Report

```
══════════════════════════════════════
ITERATE COMPLETE
Scope: {Small|Large}
Files changed: {N}
Review: {PASS|WARN}
Plan updated: {plan_file_path}
══════════════════════════════════════
```

## Important Rules

- **Judge size by actual code impact** — Do not be swayed by the user's expressions like "just a small thing"
- **Do not block on Large judgment** — Always present options to the user
- **If unexpected impact is discovered during implementation, halt and report**. Return path when halted in Phase 3:
  1. If the newly discovered impact pushes the scope from Small → Large, re-enter Phase 2 with the updated scope and present the Large options to the user（選択肢を提示して確認）.
  2. If the impact is ambiguous or crosses module boundaries in unforeseen ways, escalate to the user directly (do not auto-resume). Suggest `/claude-skills:plan-create` as the fallback.
  3. Never silently continue past a halt.
- **Headless operation**: Do not prompt for confirmation except for user choice on Large judgment and halt escalations
- **BLOCK findings must be resolved** — Never complete with unresolved BLOCK items (see Phase 4 "Processing Review Results" for the 2-iteration cap behavior)
