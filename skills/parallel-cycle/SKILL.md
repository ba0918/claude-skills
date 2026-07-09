---
name: parallel-cycle
description: Decompose a natural language instruction into multiple plans, check file orthogonality, execute independent cycles in parallel via worktrees, and merge results. Supports both natural language decomposition and direct plan file specification. Use when the user says "parallel-cycle", "並行実行", "並列で実装", or gives a compound instruction that should be split into independent cycles.
---

# Parallel Cycle

Orchestrator skill that decomposes a compound instruction into multiple independent plans, executes them in parallel using worktrees, and merges the results.

## Flow Overview

```
Input (natural language or plan files)
  │
  ├── Phase 0: Decompose (if natural language)
  │     Parse instruction → split into plans → build dependency graph
  │     → present to user for approval
  │
  ├── Phase 1: Orthogonality Check & Grouping
  │     Extract affected files → intersection check → execution groups
  │
  ├── Phase 2: Parallel Execution (per group)
  │     worktree 作成 → サブエージェント (cycle) → worktree 削除
  │
  ├── Phase 3: Merge
  │     Merge successful branches → test → revert on failure
  │
  └── Phase 4: Summary
        Unified report of all cycles
```

## Input Detection

Determine input type from `$ARGUMENTS`:

- **All arguments end in `.md`** → Treat as plan file paths. Skip Phase 0, go to Phase 1.
- **Otherwise** → Treat as natural language instruction. Start from Phase 0.

## Phase 0: Decompose

Decompose a natural language instruction into multiple plans.

### Step 0.1: Analyze and Decompose

サブエージェントに指示を分解させる。ここではモデルを明示指定しない — 分解と直交性判定は上流の重要判断であり、セッションモデルで実行すべき（see [orchestration-patterns.md](../shared/references/orchestration-patterns.md) § Model Tiering）:

**サブエージェントへの指示:**
```
Analyze the following instruction and decompose it into independent implementation plans.
Follow the decomposition guide principles.

Instruction: {$ARGUMENTS}

For each plan, produce:
- Plan letter and title
- One-line description
- List of affected files (be conservative — include broadly)
- Dependencies (which other plans must complete first)
- Priority number

Also produce the dependency graph and suggested execution groups.
```

See [references/decompose-guide.md](references/decompose-guide.md) for detailed decomposition principles.

**Immediately after Step 0.1, count the resulting plans and branch:**

- **0 plans** → jump to the "Edge Cases" section below (error exit). Skip Step 0.2 and Step 0.3.
- **1 plan** → jump to the "Edge Cases" section below (fallback to `claude-skills:cycle`). Skip Step 0.2 and Step 0.3.
- **2+ plans** → continue to Step 0.2.

### Step 0.2: User Approval

Present the decomposition result to the user:

```
══════════════════════════════════════
DECOMPOSE RESULT
══════════════════════════════════════

Plans: {N}
Execution groups: {M}

Group 1 (sequential):
  [A] {title} — no dependencies

Group 2 (parallel):
  [B] {title} — depends on A
  [D] {title} — depends on A

Group 3 (sequential):
  [C] {title} — depends on B

Estimated total groups: {M} rounds
──────────────────────────────────────
Proceed? (y/n/edit)
```

ユーザーに選択肢を提示して承認を得る。

- **y** → Proceed
- **n** → Abort with message
- **edit** → Accept modification instructions, re-decompose (return to Step 0.1)

### Step 0.3: Generate Plan Files

承認された各計画について、サブエージェント（軽量モデル — 承認済み分解からの機械的ファイル生成）で計画ファイルを生成する:

**サブエージェントへの指示:**
```
`claude-skills:plan` スキルを呼び出して以下の機能の計画を作成せよ。
Feature: {plan_title}
Description: {plan_description}
Affected files: {file_list}
```

Each plan is saved to `docs/plans/{timestamp}_{slug}.md`. All plans in the same batch share a single `{timestamp}` (captured once at Step 0.3 entry) and are differentiated only by `{slug}`.

**並行性**: Step 0.3 では全計画のサブエージェントを並行起動してよい（最大 3 並行）。計画ファイル生成は計画ごとに独立した書き込みで、生成間にデータ依存はない。

### Edge Cases

- **0 plans**: Display an error message and exit. Do not invoke any fallback.
- **1 plan**: Fall back to `/claude-skills:cycle` using the steps below. Do NOT display the DECOMPOSE RESULT block and do NOT ask for approval — 1-plan fallback is headless.

  1. Display only the fallback message (single line, verbatim):
     ```
     Single plan detected. Falling back to /claude-skills:cycle.
     ```
  2. Skip Step 0.3 (do NOT generate a plan file). The downstream `claude-skills:cycle` skill will create a plan itself if it needs one.
  3. `claude-skills:cycle` スキルを呼び出し、元の `$ARGUMENTS` 文字列をそのまま入力として渡す。言い換え・要約・計画ファイルパスへの置換はしない。
  4. スキル呼び出し後は即座に終了する。Phase 1, Phase 2, Phase 3, Phase 4 には進まない。

## Phase 1: Orthogonality Check & Grouping

See [references/orthogonality-check.md](references/orthogonality-check.md) for detailed logic.

### Step 1.1: Extract Affected Files and Dependencies

Read each plan file and extract:

- **Files to Change** (or equivalent section) → affected file set for orthogonality check
- **Dependencies** (or equivalent section) → explicit dependency graph. If no such section exists, treat the plan as independent of all others.

Both are inputs to Step 1.3. In direct plan file mode (Phase 0 skipped), the dependency graph comes entirely from these extracted sections — there is no separate decompose-time graph.

### Step 1.2: Compute Intersections

For every pair of plans, compute file set intersections.

### Step 1.3: Build Execution Groups

Combine intersection results with the dependency graph:

1. Plans with file intersections → must be in different groups
2. Plans with dependencies → dependent goes in a later group
3. Maximize parallelism within constraints
4. Maximum 3 concurrent cycles per group (split into sub-batches if more)

**Tie-breaking rules** (when two plans share files but no dependency determines the order):

1. If priorities are declared in the plan files → lower priority value goes first
2. If priorities are equal or absent:
   - Direct plan file mode (Phase 0 skipped) → argument order (first-listed plan goes first)
   - Natural language mode (Phase 0 executed) → plan letter (alphabetical; [A] before [B])

The tie-break is deterministic — never leave the order to implicit judgment.

### Step 1.4: Display Groups

```
══════════════════════════════════════
EXECUTION PLAN
══════════════════════════════════════

Group 1: [A]
Group 2: [B, D]  (parallel)
Group 3: [C]

Total rounds: 3
──────────────────────────────────────
```

## Phase 2: Parallel Execution

Execute each group sequentially. Within each group, execute cycles in parallel.

### For Each Group

For each cycle in the group, **in parallel**:

1. **worktree 作成**: git worktree で分離された作業ツリーとブランチを作成する
2. **cycle 実行**: サブエージェント（高性能モデル — 実装は検証ゲートで保護されるため、高額セッションモデルを継承させない）を起動して worktree 内で cycle を実行する:

   **サブエージェントへの指示:**
   ```
   You are working in a worktree at: {worktree_path}
   Branch: {branch_name}

   `claude-skills:plan-implement` スキルを呼び出して計画ファイル {plan_file_path} を実装せよ。
   全ステップを実装し、各ステップ後にコミットし、進捗テーブルを更新する。
   完了時に報告: 変更ファイル数、追加テスト数、コミット数。
   ```

3. **結果収集**: 各 cycle の成功/失敗とサマリーを記録する
4. **worktree 削除**: git worktree を削除してクリーンアップする

### Failure Handling

- If a cycle fails, record the failure and preserve the branch
- Check if any cycles in later groups depend on the failed cycle
- Mark dependent cycles as "skipped (dependency failure)"

### Concurrency Limit

グループあたり最大 3 サブエージェントを並行起動する。3 を超える場合はサブバッチに分割する。

### Important: status.md Write Suppression

During parallel execution, do NOT update `docs/status.md` or `docs/session-history.md` from individual cycles. The orchestrator will perform a single consolidated update after all cycles complete.

## Phase 3: Merge

See [references/merge-strategy.md](references/merge-strategy.md) for detailed strategy.

### Step 3.1: Pre-merge Sync

```bash
git checkout main
git pull --ff-only
```

### Step 3.2: Merge Each Successful Branch

In group order, then alphabetical within groups:

```bash
git merge --no-ff {branch_name} -m "merge: parallel-cycle {plan_title}"
```

### Step 3.3: Post-merge Test

If the project has a test runner:
- Run tests after each merge
- On failure: `git revert -m 1 HEAD --no-edit`
- Record the cycle as "merge-reverted"

If no test runner exists, skip this step.

### Step 3.4: Cleanup

```bash
git worktree prune
```

## Phase 4: Summary

### Step 4.1: Update Status

Update `docs/status.md` with consolidated results for all cycles.

### Step 4.2: Display Summary

```
══════════════════════════════════════
PARALLEL CYCLE COMPLETE
══════════════════════════════════════

Plans executed: {N}
Groups: {M}

Results:
  [A] {title} — ✅ Merged
  [B] {title} — ✅ Merged
  [C] {title} — ❌ Failed (reason)
  [D] {title} — ⏭ Skipped (dependency: C)

Commits: {total_commits}
Files changed: {total_files}
──────────────────────────────────────
```

### Step 4.3: Generate Result File

Save the summary to `docs/plans/results/{base_plan_name}_result.md`:

```markdown
# Parallel Cycle Result

**Executed:** {datetime}
**Plans:** {N}
**Groups:** {M}

## Results

| Plan | Title | Status | Commits | Files |
|------|-------|--------|---------|-------|
| A | {title} | ✅ Merged | {n} | {n} |
| B | {title} | ❌ Failed | - | - |

## Commits
{git log --oneline for all merged commits}

## Failed / Skipped Cycles
{details for any non-successful cycles}
```

## Important Rules

- **Orchestrator is glue code only** — All heavy logic is delegated to subagent/skill invocations
- **File orthogonality is the safety guarantee** — Never allow parallel execution of plans with file intersections
- **Partial success is acceptable** — Merge what succeeds, preserve what fails
- **Single user confirmation point** — Only Phase 0 approval. Everything else is headless
- **Worktree cleanup is mandatory** — Success or failure, always clean up
- **No force push, no rebase** — Standard merges only
- **status.md updates are consolidated** — No parallel writes to shared files
