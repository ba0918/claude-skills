---
name: parallel-cycle
description: Decompose a natural language instruction into multiple plans, check file orthogonality, execute independent cycles in parallel via git worktrees, and merge results. Supports both natural language decomposition and direct plan file specification. Use when the user says "parallel-cycle", "並行実行", "並列で実装", or gives a compound instruction that should be split into independent cycles.
---

# Parallel Cycle (Codex Edition)

Orchestrator skill that decomposes a compound instruction into multiple independent plans, executes them in parallel using git worktrees, and merges the results. Codex CLI 版は **headless 実行** を前提とする（ユーザー承認プロンプトは出さない。分解結果は `send_message` で報告のみ）。

## Codex CLI ツールの使い分け

- **shell** — `git worktree add/remove/prune`, `git merge`, `git checkout`, `git pull`, `git log`, `ls`, `cat`, `mkdir`, `date` などのシェル操作
- **apply_patch** — `docs/plans/results/*.md` や `docs/status.md` の書き込み
- **spawn_agent** / **wait_agent** — decompose / plan 生成 / plan-implement 実行の委譲
- **$\<skill-name\>** — `$plan`, `$plan-implement`, `$cycle` などサブスキルの起動
- **send_message** — ユーザーへの進捗・結果報告

## Flow Overview

```
Input (natural language or plan files)
  │
  ├── Phase 0: Decompose (if natural language)
  │     Parse instruction → split into plans → build dependency graph
  │     → report to user via send_message (no approval prompt)
  │
  ├── Phase 1: Orthogonality Check & Grouping
  │     Extract affected files + dependencies → intersection check → execution groups
  │
  ├── Phase 2: Parallel Execution (per group)
  │     git worktree add → spawn_agent ($plan-implement) → wait_agent → git worktree remove
  │
  ├── Phase 3: Merge
  │     Merge successful branches → test → revert on failure
  │
  └── Phase 4: Summary
        Unified report of all cycles
```

## Input Detection

`$ARGUMENTS` を shell で空白区切りし、全トークンを確認する:

- **全トークンが `.md` で終わる** → plan file paths として扱う。**Phase 0 をスキップし Phase 1 から開始**
- **それ以外** → 自然言語指示として扱う。Phase 0 から開始

## Phase 0: Decompose

自然言語指示を複数の独立 plan に分解する。

### Step 0.1: Analyze and Decompose

`spawn_agent` で分解エージェントを起動する:

**プロンプト:**
```
Analyze the following instruction and decompose it into independent implementation plans.
Follow the decomposition guide principles in references/decompose-guide.md.

Instruction: {$ARGUMENTS}

For each plan, produce:
- Plan letter and title
- One-line description
- List of affected files (be conservative — include broadly)
- Dependencies (which other plans must complete first)
- Priority number

Also produce the dependency graph and suggested execution groups.
Return the result as a structured report.
```

`wait_agent` で結果を受け取る。

詳細な分解原則は [references/decompose-guide.md](references/decompose-guide.md) を参照。

**Immediately after Step 0.1, count the resulting plans and branch:**

- **0 plans** → jump to the "Edge Cases" section below (error exit). Skip Step 0.2 and Step 0.3.
- **1 plan** → jump to the "Edge Cases" section below (fallback to `$cycle`). Skip Step 0.2 and Step 0.3.
- **2+ plans** → continue to Step 0.2.

### Step 0.2: Report Decomposition (headless)

分解結果を `send_message` でユーザーに報告する（承認プロンプトは出さない。Codex は headless 実行）:

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
Proceeding to Phase 1 (headless).
```

ユーザー側で中断したい場合は Ctrl+C で割り込む運用。承認フローは設けない。

### Step 0.3: Generate Plan Files

承認済みの各 plan について、`spawn_agent` で `$plan` を起動して plan ファイルを生成する。

**プロンプト（各 plan ごと）:**
```
Invoke $plan to create a plan for the following feature.
Feature: {plan_title}
Description: {plan_description}
Affected files: {file_list}
Dependencies: {dependency_list}
```

Each plan is saved to `docs/plans/{timestamp}_{slug}.md`. All plans in the same batch share a single `{timestamp}` (captured once at Step 0.3 entry via `shell: date +%Y%m%d%H%M%S`) and are differentiated only by `{slug}`.

**Parallelism**: Step 0.3 may `spawn_agent` for all plans in parallel (up to the 3-concurrent cap). Plan file generation is an independent write per plan; there is no data dependency between generations. 必要なら `wait_agent` を順次呼び出して全 plan の生成完了を待つ。

### Edge Cases

- **0 plans**: `send_message` でエラーを報告して exit。fallback は invoke しない。
  ```
  ⛔ PARALLEL-CYCLE ABORTED: Instruction decomposed to 0 plans.
  Reason: {agent-reported reason}
  Please re-run with a more specific instruction.
  ```

- **1 plan**: `$cycle` に fallback する。DECOMPOSE RESULT ブロックの表示や承認は行わない（headless）。

  1. `send_message` で fallback メッセージを単独送信（verbatim）:
     ```
     Single plan detected. Falling back to $cycle.
     ```
  2. Step 0.3 をスキップ（plan ファイルを生成しない）。downstream の `$cycle` が必要なら自前で plan を作成する。
  3. `$cycle` を起動し、`$ARGUMENTS` の原文をそのまま入力として渡す。re-word, summarize, plan ファイルパスへの差し替えは行わない。
  4. `$cycle` 起動直後に parallel-cycle は exit。Phase 1, 2, 3, 4 には進まない。

## Phase 1: Orthogonality Check & Grouping

詳細ロジックは [references/orthogonality-check.md](references/orthogonality-check.md) を参照。

### Step 1.1: Extract Affected Files and Dependencies

各 plan ファイルを `shell: cat` で読み込み、以下を抽出する:

- **Files to Change**（または等価なセクション） → orthogonality check の入力となる affected file set
- **Dependencies**（または等価なセクション） → 明示的な依存グラフ。該当セクションが無ければ「全 plan と独立」として扱う

どちらも Step 1.3 の入力になる。direct plan file mode（Phase 0 skipped）では dependency graph の入手源は plan ファイルのこれらのセクション**のみ**（decompose-time graph は存在しない）。

### Step 1.2: Compute Intersections

全 pair について file set intersection を計算する。

### Step 1.3: Build Execution Groups

intersection と dependency graph を結合:

1. ファイル交差を持つ plan 同士は別グループ
2. 依存を持つ plan は依存先より後のグループ
3. 制約の範囲で並列度を最大化
4. グループあたり最大 3 並列（超過時は sub-batch に分割）

**Tie-breaking rules** (when two plans share files but no dependency determines the order):

1. plan ファイルに priority が宣言されていれば → 値の小さい方が先
2. priority が同値または未宣言の場合:
   - Direct plan file mode（Phase 0 skipped）→ 引数順（先に列挙された plan が先）
   - Natural language mode（Phase 0 executed）→ plan letter の昇順（[A] の前に [B]）

tie-break は deterministic に決めきる。暗黙の判断に委ねない。

### Step 1.4: Display Groups

`send_message` で実行計画を報告:

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

各グループを逐次実行する。グループ内の cycle は並列実行する。

### For Each Group

グループ内の各 cycle について **並列** で:

1. **Worktree 作成**: `shell` で git worktree を作成:
   ```bash
   git worktree add .worktrees/parallel-cycle/{plan_letter}-{slug} -b parallel-cycle/{plan_letter}-{slug}
   ```
2. **Cycle 実行**: `spawn_agent` で `$plan-implement` を worktree 内で起動する:

   **プロンプト:**
   ```
   You are working in a worktree at: {worktree_path}
   Branch: {branch_name}

   Invoke $plan-implement for the plan file: {plan_file_path}
   Implement all steps. Commit after each step. Update the progress table.
   When done, report: files changed, tests added, commits made.
   ```
3. **結果回収**: `wait_agent` で各 agent の結果を受け取り、success/failure と summary を記録する
4. **Worktree 削除**: `shell` で worktree を cleanup:
   ```bash
   git worktree remove .worktrees/parallel-cycle/{plan_letter}-{slug}
   ```

### Failure Handling

- cycle が失敗した場合、失敗を記録し branch は**保持**する
- 後続グループの plan のうち失敗 cycle に依存するものは `skipped (dependency failure)` でマーク

### Concurrency Limit

`spawn_agent` の並列起動は グループあたり最大 3 まで。グループ内の cycle が 3 を超える場合は sub-batch に分割し、sub-batch を逐次実行する。sub-batch 分割順序は Step 1.3 の tie-break ルールに従う。

### Important: status.md Write Suppression

並列実行中、個別 cycle から `docs/status.md` / `docs/session-history.md` への書き込みは**行わない**。Orchestrator が Phase 4 で一括更新する。spawn する `$plan-implement` エージェントのプロンプトに「status.md / session-history.md を更新しないこと」を明記する。

## Phase 3: Merge

詳細は [references/merge-strategy.md](references/merge-strategy.md) を参照。

### Step 3.1: Pre-merge Sync

```bash
git checkout main
git pull --ff-only
```

### Step 3.2: Merge Each Successful Branch

グループ順、同一グループ内は alphabetical / argument order に従って:

```bash
git merge --no-ff {branch_name} -m "merge: parallel-cycle {plan_title}"
```

### Step 3.3: Post-merge Test

プロジェクトにテストランナーがあれば:
- 各 merge 後にテストを実行（例: `npm test`, `pytest`, `cargo test`）
- 失敗時: `git revert -m 1 HEAD --no-edit` で merge を取り消し、該当 cycle を `merge-reverted` として記録

テストランナーが無ければ本ステップは skip する。

### Step 3.4: Cleanup

```bash
git worktree prune
```

## Phase 4: Summary

### Step 4.1: Update Status

`apply_patch` で `docs/status.md` を更新し、全 cycle の集約結果を反映する。

### Step 4.2: Display Summary

`send_message` で最終サマリーを送信:

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

`apply_patch` で `docs/plans/results/{base_plan_name}_result.md` にサマリーを保存する（`docs/plans/results/` が無ければ `shell: mkdir -p` で先に作成）:

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

- **Orchestrator is glue code only** — 重い処理はすべて `spawn_agent` / `$<skill>` に委譲する
- **File orthogonality is the safety guarantee** — ファイル交差を持つ plan を同じグループで並列実行しない
- **Partial success is acceptable** — 成功した cycle のみ merge し、失敗した cycle の branch は保持する
- **Headless execution** — ユーザー承認プロンプトは出さない（Codex 方針）。分解結果・実行計画は `send_message` で報告のみ
- **Worktree cleanup is mandatory** — 成功・失敗問わず必ず `git worktree remove` する
- **No force push, no rebase** — 標準 merge のみ
- **status.md updates are consolidated** — 並列実行中は共有ファイルに書き込まない
- **Shell リダイレクトで巨大ファイルを作らない** — `docs/plans/results/*.md` や `docs/status.md` の書き込みは `apply_patch` を使う
