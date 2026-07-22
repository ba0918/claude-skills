---
name: cycle
description: 実装計画に対して refine（計画品質ゲート）と implement（TDD 自動実装）をサブエージェント委譲で自律実行し、最後にメインコンテキストでサマリー生成・ステータス更新・コミットまで行う。ユーザー確認なしのヘッドレス実行に対応。「cycle」「サイクル回して」「計画を自動実装して」「全自動で実装」で起動。
---

# Cycle

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Run the full refine → auto-implement cycle for an implementation plan autonomously.
Each phase is delegated to a subagent; the main context keeps only progress summaries.

In environments where subagents or other skills cannot be launched, you may execute each
phase's content inline yourself: follow the plan-refine procedure for refine and the
plan-implement procedure for implementation (including their own fallback provisions).
**Inline mode signpost:** when running inline, the delegation machinery in this file — the
"Delegation result relay" section, its wait discipline / watchdog duties, and the
delegation-retry rules — does not apply. Results stay in your own context; no relay files
are needed. The phase logic itself (gates, verdicts, displays) applies unchanged. The same
fallback covers skill invocations (e.g. `claude-skills:commit`): when a skill cannot be
launched, perform its core action yourself following that skill's documented procedure.

## Parameters

- First path in the arguments: plan file path (when omitted, auto-select from `.agents/artifacts/plans/`)
- A number in the arguments: max refine iterations (default: 4)

## Phase 0: Preparation

1. Identify the plan file
   - If the arguments contain a path, use it
   - Otherwise auto-select: list the `*.md` files directly under `.agents/artifacts/plans/`
     in filename-timestamp descending order and pick the first **incomplete** plan (one whose
     Status is not ✅/Completed). Do not use mtime (`ls -t`) — the filename timestamp is
     authoritative; mtime gets reshuffled by edits
   - If there is no incomplete plan: display 「実装対象の計画がない」 and abort the cycle
     (never run a no-op cycle on completed plans)
1.5. Validate the path
   - Confirm the plan file is a `.md` file **directly under** `.agents/artifacts/plans/`
     (subdirectories do not count)
   - If it is not, abort here — this happens before the CYCLE START display, so no CYCLE
     START block is shown:
     ```
     ⛔ CYCLE ABORTED: Plan file is not in .agents/artifacts/plans/
     Found: {actual_path}
     Expected: .agents/artifacts/plans/*.md

     Plan files must be located in .agents/artifacts/plans/.
     If the file was created in the wrong location, move it first:
       mv {actual_path} .agents/artifacts/plans/
     ```
     The `mv` above is guidance presented to the user; the executor must not move the file
     itself and continue. Note that migration from legacy layouts such as `docs/plans/` can
     fall under the migration procedure of the
     [Agent Artifact Store contract](../shared/references/artifact-store.md), so you may add
     a note that the simple `mv` hint targets misplaced newly-created files. Rule of thumb:
     a file under a legacy root (e.g. `docs/plans/`) that already has plan structure and a
     Cycle ID is a migration case, not an mv case
2. Read the plan file and grasp the overview (feature name, step count = the rows of the
   plan's Progress table, current progress)
3. Display the cycle start:
   ```
   ══════════════════════════════════════
   CYCLE START
   Plan: {plan_file_path}
   Feature: {feature_name}
   Steps: {step_count}
   ══════════════════════════════════════
   ```

## Delegation result relay (shared by Phases 1 / 1.5 / 2 — delegation mode only)

Subagent delegation in Phases 1 / 1.5 / 2 follows
[orchestration-patterns.md § delegation result relay](../shared/references/orchestration-patterns.md).
**Two cycle-specific points:**

- **`{run_id}`**: the Cycle ID at the top of the plan file (or the plan filename's timestamp
  if absent). Requirement: the orchestrator and the delegate must derive the same path.
- **`{role}`**: `refine` / `refine-fix` / `implement` per phase. Include the
  `.agents/runtime/delegation/{run_id}_{role}.md` path in the delegation prompt.
- **Wait discipline**: cycle is the **parent orchestrator** of each delegate, so it holds
  [§ wait discipline pillar 3 (upper watchdog)](../shared/references/orchestration-patterns.md).
  List `.agents/runtime/delegation/`, cross-check result-file mtimes against final artifacts
  to judge "all arrived / stalled" before sending a status inquiry (a nudge). The concrete
  procedure is the silent-stall row in "Error handling" below (single source, not repeated
  here). A nudge is a status check, not a re-delegation; it does not multiply the retry
  budget of the fallbacks below.

Path conventions / writer duties / reader duties (inspect the result file on completion or
stall notice; fall back to artifact inspection when missing; retry only when undecidable) /
cleanup are owned by the contract.

## Phase 1: Refine (plan quality gate)

1. Launch a refine agent on a subagent (high-performance model):
   - Prompt: "Execute the skill `claude-skills:plan-refine`. Target: {plan_file_path}. Max
     iterations: {max_iterations}. Loop until every dimension is PASS. **Before sending your
     completion report**, write the full result — each dimension's final score and verdict,
     and every iteration's total score (used for cumulative-stall detection) — to
     `.agents/runtime/delegation/{run_id}_refine.md`. The report message is merely a
     notification that the file was written."
2. Receive the result (per "Delegation result relay" above)
   - On receiving either refine's completion report **or** a stop/wait notice, read
     `.agents/runtime/delegation/{run_id}_refine.md` for per-dimension scores, verdicts, and
     cumulative scores
   - If the result file is missing or incomplete: inspect the plan file body (the artifact
     refine edits) and the Git diff directly, and judge PASS/WARN/BLOCK yourself
   - **If the subagent errored, or neither the result file nor artifact inspection is
     decidable**: retry once automatically. If the retry also fails, abort the cycle
     ```
     ⚠️ Phase 1 agent failed — retrying (1/1)...
     ```
3. **Verdict**:
   - All PASS → Phase 2
   - BLOCKs remain → **Phase 1.5 (fallback)**
   - Only WARNs remain → display the warnings and proceed to Phase 2

Display:
```
── Phase 1: Refine ── {PASS|WARN|BLOCK}
Iterations: {N}
{各観点のスコアサマリー（1行ずつ）}
```

## Phase 1.5: BLOCK fallback (auto-fix)

**Runs only when BLOCKs remain after Phase 1. At most once.**

1. Analyze the remaining BLOCKs
2. Launch a fix agent on a subagent (high-performance model):
   - Prompt: "The review of plan file {plan_file_path} raised the BLOCKs below. Edit the
     plan file to resolve them. **Write a summary of your fixes to
     `.agents/runtime/delegation/{run_id}_refine-fix.md` before sending your completion
     report** (the report is merely a notification that the file was written).\n\nRemaining
     BLOCKs:\n{block_list}"
3. Receive the fix result (per "Delegation result relay" above)
   - On completion report **or** stop/wait notice, read
     `.agents/runtime/delegation/{run_id}_refine-fix.md`. If missing or incomplete, inspect
     the BLOCK-related parts of the plan file and the Git diff directly to confirm whether
     fixes landed
4. **Re-refine**: relaunch the refine agent as in Phase 1 (iterations = the smaller of the
   remaining budget or 2)
5. **Re-verdict**:
   - All PASS or WARN only → Phase 2
   - BLOCKs still remain → abort the cycle; list the remaining BLOCKs and stop

Display:
```
── Phase 1.5: Fallback ── {RESOLVED|UNRESOLVED}
BLOCKs addressed: {N}/{total}
{RESOLVED の場合: Proceeding to Phase 2}
{UNRESOLVED の場合: Cycle aborted — remaining BLOCKs listed above}
```

## Phase 2: Implement (auto-implementation)

1. Launch an implement agent on a subagent (high-performance model):
   - Prompt: "Execute the skill `claude-skills:plan-implement`. Implement every step of plan
     file {plan_file_path}. Follow `skills/shared/references/tdd-contract.md`: test-first
     (RED → GREEN → REFACTOR). Before finishing, apply the Gate Function of
     `skills/shared/references/verification-gate.md`. **Before sending your completion
     report**, write the full result — an implementation summary (files changed, tests,
     commits, per-step completion) and test-run evidence — to the result file
     `.agents/runtime/delegation/{run_id}_implement.md` (the report is merely a notification
     that the file was written). Commit after each completed step and update the status."
2. Receive the result (per "Delegation result relay" above)
   - On completion report **or** stop/wait notice, read
     `.agents/runtime/delegation/{run_id}_implement.md` for the implementation summary, test
     evidence, and per-step completion
   - If the result file is missing or incomplete: inspect `git log` commits, changed files,
     and the plan's Progress directly to judge how far the steps got
   - **If the subagent errored, or neither the result file nor artifact inspection is
     decidable**: retry once automatically. If the retry also fails, display the error,
     record how far the steps got, and abort the cycle
     ```
     ⚠️ Phase 2 agent failed — retrying (1/1)...
     ```

Display:
```
── Phase 2: Implement ── DONE
Files changed: {N}
Tests added: {N}
Commits: {N}
```

`Files changed` counts production-code and test files (not plan/status meta updates).

## Phase 3: Summary generation

**Execution context**: run Phase 3 directly in the main context. Unlike Phases 1 / 1.5 / 2,
**do not delegate it** (the main context owns artifact generation, status management, and
commits end to end).

**Run each Phase 3 step independently; if one step fails, continue with the rest.** Record
failed steps in a `phase3_failures` list and include it in the final display.

**General failure rule**: anything that does not match a guard condition (allowed skip) and
cannot be completed — required file/section missing, unparsable content, unexpected tool
error — is a failure recorded in `phase3_failures`. Do not ask the user and do not abort the
whole cycle for it.

1. Get the Phase 2 commit list with `git log`
2. Generate the summary file at `.agents/artifacts/plans/results/{plan_basename}_result.md`,
   where `{plan_basename}` is the plan filename without its `.md` extension
   (`mkdir -p` the directory if missing)
   - **On failure**: append `"result file generation"` to `phase3_failures` and move on

Summary file content:
```markdown
# Cycle Result: {feature_name}

Artifact paths follow the Agent Artifact Store contract.

**Plan:** {plan_file_path}
**Executed:** {datetime}

## Refine
- Iterations: {N}
- Final verdict: {PASS|WARN}
- {残存 WARN があれば一覧}

## Implementation
- Steps completed: {N}/{total}
- Files changed: {N}
- Tests added: {N}
- Commits: {N}（Phase 2 の実装コミット数。Phase 3 の成果物コミットは含まない）

## Commits
{git log --oneline のコミット一覧}

## Notes
{特記事項があれば}
```

3. Mark status.md as completed:
   - **Step 3a: Pre-check (failure detection first)**: Read `.agents/artifacts/status.md`
     and confirm the Current Session section exists
     - If the Current Session heading itself is absent, or the table is unparsable
       → append `"status.md update"` to `phase3_failures` and move on (**treat as a
       failure, not a guard** — this includes old-format status.md files without session
       management: do not repair or rewrite them, just record and continue)
     - Current Session section exists → Step 3b
   - **Step 3b: Guard conditions (skip when any applies)**:
     - The Current Session body starts with `_No active session` (section exists but
       uninitialized)
     - The Current Session table's Status is `Completed`
     - When either applies, do nothing and move on (not a failure)
   - **Step 3c: Normal processing (no guard applies)**: follow **Case 2 (In Progress →
     Completed)** of [status-update-guide.md](../plan/references/status-update-guide.md).
     Case 2 applies to any still-active session regardless of its Phase label — a session
     still in 🟡 Planning also completes via Case 2 (the cycle has just implemented it):
     - Step 2a: archive to session-history.md
     - Step 2b: clear the Session History section
     - Step 2c: clear Current Session
   - **On failure during Step 3c** (Edit failure, write failure, ...): append
     `"status.md update"` to `phase3_failures` and move on
   - **Step 3d (runs regardless of the Step 3a/3b outcomes):** verify the plan file's own
     **Status:** header is marked completed (implement normally does this; update it here
     if it is stale) — otherwise the next cycle's Phase 0 would reselect this plan. On
     failure, append `"plan status update"` to `phase3_failures` and move on

4. **Commit the cycle artifacts**: commit all uncommitted changes left in the working tree
   after Phase 2
   - Typical targets: the result file from step 2 / `.agents/artifacts/status.md` /
     `.agents/artifacts/session-history.md` updated in step 3 / plan-file updates the
     Phase 2 agent failed to commit
   - Execute the skill `claude-skills:commit` **with no arguments** (the commit skill
     auto-detects targets from `git status` / `git diff` and splits commit units)
   - If step 3 failed, status.md / session-history.md were not updated and naturally stay
     out of the commit (only the result file gets committed)
   - If there is nothing to commit, the commit skill handles the skip
   - **On failure**: append `"commit"` to `phase3_failures` and move on

5. **Auto-close the issue**: read the plan file and check for an `**Issue:**` line
   - If present: extract the issue slug and execute the skill `claude-skills:issue` with
     `close {slug}`
     - If close fails, display a warning only; the cycle itself still counts as a success
       (do not roll back the implementation)
     - **Record the close outcome and include it in the final display of step 6**
   - If absent: skip this step

6. Final display:
```
══════════════════════════════════════
CYCLE COMPLETE
Feature: {feature_name}
Refine: {verdict} ({iterations} rounds)
Implement: {steps_done}/{steps_total} steps
Commits: {N}（サイクル全体で作成したコミット数。Phase 3 の成果物コミットを含む）
Result: {result_file_path}
Issue: {closed ✅ / ⚠️ close failed: {slug} — manual close required / (none)}
{phase3_failures が空でない場合:}
⚠️ Phase 3 partial failures: {phase3_failures をカンマ区切りで表示}
──────────────────────────────────────
💡 Need tweaks? Use /iterate for quick fixes and polish.
══════════════════════════════════════
```

## Error handling

- **BLOCKs remain after Phase 1**: try Phase 1.5 (fallback) once. If BLOCKs still remain,
  abort the cycle and list them.
- **Subagent error in Phase 1/Phase 2**: retry once automatically. If the retry also fails,
  abort the cycle.
- **Delegate stops without reporting in Phase 1/Phase 2** (work done + no completion report
  + only a wait notice — the most common stall): do not treat as an error and re-delegate
  immediately; follow pillar 3 (upper watchdog) of the
  [wait discipline](../shared/references/orchestration-patterns.md). First read
  `.agents/runtime/delegation/{run_id}_{role}.md` → if missing/incomplete, inspect the
  artifacts directly (commit history, changed files, test results, plan Progress) to judge
  phase completion → retry (once) only when undecidable. If the result file or artifacts
  confirm completion, proceed to the next phase even without a delivered report.
- **Error in a Phase 3 step**: record the step in `phase3_failures` and continue with the
  rest. Phase 3 errors never fail the whole cycle.

## Codex second opinion

The plan-reviewer used in Phase 1 (Refine) automatically includes a Codex second opinion:
alongside Claude's 7-dimension review, a comprehensive third-party perspective from Codex is
obtained in parallel. When Codex is unavailable, continue with the 7-dimension review only
(graceful degradation).

## Key rules

- **Delegate each phase to a subagent** (when delegation is available). Keep only summaries
  in the main context.
- **Specify a high-performance model when launching subagents.** Even if the session runs on
  a top-tier model, run delegates on a high-performance model to avoid cost blowups
  (per the model hierarchy in
  [orchestration-patterns.md](../shared/references/orchestration-patterns.md)).
- **Never ignore Phase 1 BLOCKs.** If BLOCKs remain, try the Phase 1.5 fallback; if they
  still remain, do not proceed to implementation.
- **No user confirmation prompts** (headless execution).
- **Retry once on subagent errors.** Abort after a failed retry; do not retry twice.
- **Phase 3 tolerates partial success.** Individual step failures do not roll back the
  cycle.
- When the root cause of a problem is unknown, recommend a read-only pre-investigation with
  `/claude-skills:investigate` before running the cycle.
