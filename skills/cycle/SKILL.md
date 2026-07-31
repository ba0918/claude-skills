---
name: cycle
description: Run automated TDD implementation against an implementation plan, then auto-review with a fix loop and a final gate before completion. Delegates each phase to subagents for context isolation. Supports headless execution with no user confirmation. Use when the user says "cycle", "run the cycle", "implement the plan automatically", or "implement it fully automatically".
---

# Cycle

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Run the auto-implement cycle for an implementation plan autonomously.
The implementation phase is delegated to a subagent; the main context keeps only progress summaries.

In environments where subagents or other skills cannot be launched, you may execute each
phase's content inline yourself: follow the plan-implement procedure for implementation
(including its own fallback provisions).
**Inline mode signpost:** when running inline, the delegation machinery in this file — the
"Delegation result relay" section, its wait discipline / watchdog duties, and the
delegation-retry rules — does not apply. Results stay in your own context; no relay files
are needed. The phase logic itself (gates, verdicts, displays) applies unchanged. The same
fallback covers skill invocations (e.g. `claude-skills:commit`): when a skill cannot be
launched, perform its core action yourself following that skill's documented procedure.

## Parameters

- First path in the arguments: plan file path (when omitted, auto-select from `.agents/artifacts/plans/`)
- Inner satellite context: a store-relative `pinned_plan`, `resolved_isolation=worktree`,
  `satellite_run_id`, and `satellite_capability_file`. The capability parameter is the file path,
  never the bearer value.

When all four inner satellite fields are present, treat them as an authoritative context resolved
by the outer orchestrator:

- Validate the complete context and pinned-plan/provenance binding, then do not auto-select or
  re-resolve the plan. A partial context is an error.
- This inner cycle MUST skip workspace claim and release; do not create or switch branches or
  create a nested worktree; the outer orchestrator already created and owns the isolation boundary.
- When invoking implementation, pass the complete satellite context unchanged to
  `plan-implement`, including the capability file path rather than its contents.
- Across the inner cycle, suppress `status.md`, `session-history.md`, and derived-index writes.
  Implementation updates the progress file and the plan's top-level Status only;
  singleton composition belongs to the outer main-tree orchestrator.
- In inner satellite mode, append the complete resolved context to the implementation prompt.
  No delegate may infer, shorten, or re-resolve that context.

Without the complete context, retain the standalone behavior below. This contract only defines the
inner path used by an existing outer worktree; standalone outer-worktree resolution is separate.

### Standalone isolation boundary

Before Phase 0, Resolve isolation exactly once through the shared workspace-isolation facade.
In `inplace` mode, preserve the existing workflow unchanged. In `worktree` mode the standalone
invocation is the main-tree outer orchestrator and performs this ordered protocol:

1. Create exactly one outer worktree and derive `{satellite_run_id}`.
2. Initialize satellite ingress for the store-relative pinned plan and capability file.
3. Launch one inner run with `pinned_plan`, `resolved_isolation=worktree`,
   `satellite_run_id`, and `satellite_capability_file`. The inner run must not re-resolve
   isolation or create a nested worktree.
4. Collect on every terminal path: success, failure, cancellation, and verification failure.
5. Merge and run post-merge verification in the main tree.
6. Publish only after verification passes. Every failure path preserves staging and the worktree;
   discard requires explicit human authorization.
7. Cleanup only when cleanup_allowed is proven and the capability is revoked.

On every new terminal collect, publish, or cleanup-gate failure, preserve the worktree and invoke
the shared exact six-line formatter with its closed reason code. Its final line is
`recovery_command=/claude-skills:artifacts recover --run-id {satellite_run_id}`. Never mark that
path cleanup-eligible. The outer orchestrator composes singleton artifacts only after publication.

## Phase 0: Preparation

0. **Take the working tree** per the [Workspace Lock contract](../shared/references/workspace-lock.md),
   before plan validation and before writing a single byte of project state.
   In inner satellite mode, skip this entire claim/release step as specified above.
   - `ACQUIRED` / `STALE_RECLAIMED` → continue. Report `STALE_RECLAIMED` in the CYCLE START
     block so a recovered crash is visible rather than silent
   - `LOCK_HELD` → **abort here**, showing the holder's `skill` / `pid` / `branch` /
     `started_at`. Offer only "wait for that session" or "delete
     `.agents/runtime/workspace.claim` after confirming the holder is dead". Never take it over
   - `UNAVAILABLE` → warn once and continue (fail-open)
   - Release the token when the cycle ends, on every exit path including abort

1. Identify the plan file
   - In inner satellite mode, use the validated `pinned_plan` directly
   - If the arguments contain a path, use it
   - Otherwise auto-select: list the `*.md` files directly under `.agents/artifacts/plans/`
     in filename-timestamp descending order and pick the first **incomplete** plan (one whose
     Status is not ✅/Completed). Do not use mtime (`ls -t`) — the filename timestamp is
     authoritative; mtime gets reshuffled by edits
   - If there is no incomplete plan: display "No plan to implement" and abort the cycle
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
1.7. **Branch precondition**: check the current branch
   - In inner satellite mode, skip this step; do not create or switch a branch
   - If the current branch is the repository's default branch (`main` or `master`):
     create and switch to a working branch named `cycle/{plan_timestamp}` (where
     `{plan_timestamp}` is the timestamp portion of the plan filename). This prevents
     Phase 2 Step 2 from being blocked by the commit skill's default-branch guard, and
     keeps cycle work on a reviewable branch
   - If already on a non-default branch: continue on the current branch
2. Read the plan file and grasp the overview (feature name, step count = the number of
   implementation steps listed in the plan)
3. **Save `cycle_start_sha`**: record the current `HEAD` commit SHA (`git rev-parse HEAD`).
   Phase 3 and Phase 4 use this to scope reviews and fixes to only the changes introduced
   by this cycle, excluding prior unrelated commits on the branch.
4. Display the cycle start:
   ```
   ══════════════════════════════════════
   CYCLE START
   Plan: {plan_file_path}
   Feature: {feature_name}
   Steps: {step_count}
   ══════════════════════════════════════
   ```

## Delegation result relay (shared by Phases 1, 3, and 4 — delegation mode only)

Subagent delegation follows
[orchestration-patterns.md § delegation result relay](../shared/references/orchestration-patterns.md).
**Cycle-specific points:**

- **`{run_id}`**: the Cycle ID at the top of the plan file (or the plan filename's timestamp
  if absent). Requirement: the orchestrator and the delegate must derive the same path.
- **`{role}`**: varies by phase — `implement` (Phase 1), `post-review` / `post-review-{N}` /
  `fix-{N}` (Phase 3), `final-holistic` / `final-independent` (Phase 4). Include the
  `.agents/runtime/delegation/{run_id}_{role}.md` path in the delegation prompt.
- **Workspace-lock token**: pass the token from Phase 0 in the delegation prompt, on the same
  path as `{run_id}`. A delegate that receives one neither claims nor releases — that is what
  keeps a delegate from deadlocking against the tree its own orchestrator already holds.
- **Wait discipline**: cycle is the **parent orchestrator** of each delegate, so it holds
  [§ wait discipline pillar 3 (upper watchdog)](../shared/references/orchestration-patterns.md).
  List `.agents/runtime/delegation/`, cross-check result-file mtimes against final artifacts
  to judge "all arrived / stalled" before sending a status inquiry (a nudge). The concrete
  procedure is the silent-stall row in "Error handling" below (single source, not repeated
  here). A nudge is a status check, not a re-delegation; it does not multiply the retry
  budget of the fallbacks below.
- **Role-specific values** (the shared contract requires each referencing skill to state
  these): silent-wait timeout **N = 10 minutes** per delegate — the shared default of
  [§ wait discipline pillar 2](../shared/references/orchestration-patterns.md), adopted
  as-is by the 2026-07-28 ruling on issue #58; revisit only if accumulated cycle-specific
  arrival measurements justify a different value. **Exception**: Phase 3 review delegates
  (`post-review` / `post-review-{N}`) use **N = 20 minutes** because plan-reviewer runs in
  sequential mode when launched as a subagent (7 dimensions inline), which regularly exceeds
  10 minutes.
  Budget expiry does not open a new path: it only marks when the silent-stall row in
  "Error handling" below may start.
  Redelegation limit: pillar 2's "once per viewpoint", no cycle-specific extra budget.
  Optional viewpoints: Phase 4 independent review only — every other delegate cycle launches
  is mandatory.

Path conventions / writer duties / reader duties (inspect the result file on completion or
stall notice; fall back to artifact inspection when missing; retry only when undecidable) /
cleanup are owned by the contract.

## Phase 1: Implement (auto-implementation)

1. Launch an implement agent on a subagent (high-performance model):
   - Prompt: "Execute the skill `claude-skills:plan-implement`. Implement every step of plan
     file {plan_file_path}. Follow `skills/shared/references/tdd-contract.md`: test-first
     (RED → GREEN → REFACTOR). Before finishing, apply the Gate Function of
     `skills/shared/references/verification-gate.md`. **Before sending your completion
     report**, write the full result — an implementation summary (files changed, tests,
     commits, per-step completion) and test-run evidence — to the result file
     `.agents/runtime/delegation/{run_id}_implement.md` (the report is merely a notification
     that the file was written). Commit after each completed step and update the runtime progress file."
   - In inner satellite mode, append `pinned_plan`, `resolved_isolation=worktree`,
     `satellite_run_id`, and `satellite_capability_file` verbatim to this prompt. This is how Cycle
     must pass the complete satellite context unchanged to `plan-implement`; replace "update the
     runtime progress file" with "update the runtime progress file and the plan's top-level Status only; suppress singleton/derived writes."
2. Receive the result (per "Delegation result relay" above)
   - On completion report **or** stop/wait notice, read
     `.agents/runtime/delegation/{run_id}_implement.md` for the implementation summary, test
     evidence, and per-step completion
   - If the result file is missing or incomplete: inspect `git log` commits, changed files,
     and the plan's implementation steps directly to judge how far the steps got
   - **If the subagent errored, or neither the result file nor artifact inspection is
     decidable**: retry once automatically. If the retry also fails, display the error,
     record how far the steps got, and abort the cycle
     ```
     ⚠️ Phase 1 agent failed — retrying (1/1)...
     ```

Display:
```
── Phase 1: Implement ── DONE
Files changed: {N}
Tests added: {N}
Commits: {N}
```

`Files changed` counts production-code and test files (not plan/status meta updates).

## Phase 2: Post-implementation artifacts

**Execution context**: run Phase 2 directly in the main context. Unlike Phase 1,
**do not delegate it** (the main context owns artifact generation and commits end to end).

**Run each Phase 2 step independently; if one step fails, continue with the rest.** Record
failed steps in a `phase2_failures` list and include it in the final display.

**General failure rule**: anything that does not match a guard condition (allowed skip) and
cannot be completed — required file/section missing, unparsable content, unexpected tool
error — is a failure recorded in `phase2_failures`. Do not ask the user and do not abort the
whole cycle for it.

1. Get the Phase 1 commit list with `git log` (retain for the result file in Phase 5)
2. **Commit tracked changes**: commit any tracked (non-ignored) changes remaining in the
   working tree after Phase 1
   - Inner satellite mode does not skip this step: tracked implementation commits remain mandatory.
   - Files under the artifact store (`.agents/artifacts/`) are structurally excluded from
     Git by [safety invariant 3 of the artifact-store contract](../shared/references/artifact-store.md)
     and will never appear in `git status` — do not attempt to stage or commit them
   - Typical tracked targets: implementation files or project configuration the Phase 1
     agent failed to commit
   - Execute the skill `claude-skills:commit` **with no arguments** (the commit skill
     auto-detects targets from `git status` / `git diff` and splits commit units)
   - If there is nothing to commit, the commit skill handles the skip
   - **On failure**: append `"commit"` to `phase2_failures` and move on

3. **Clean tree gate**: after committing, verify the working tree has no uncommitted
   or untracked non-ignored files (`git status --porcelain --untracked-files=all` returns
   empty). Phase 3/4 review `git diff {cycle_start_sha}..HEAD` which only covers committed
   changes — uncommitted modifications AND newly created non-ignored files would both be
   invisible to the review.
   - If clean → continue
   - If dirty (any non-ignored uncommitted or untracked files remain) → **abort the cycle**:
     ```
     ⛔ CYCLE ABORTED: Uncommitted implementation changes detected
     Dirty files:
       {list from git status --porcelain --untracked-files=all}
     Phase 3/4 review covers only committed changes. Uncommitted or untracked
     implementation files would bypass review entirely.
     Fix the commit failure and re-run the cycle.
     ```
     Revert the plan file's **Status:** to `⚠️ Review Failed` before aborting.
   - Gitignored files (e.g. `.agents/`, `__pycache__/`) are excluded by `git status` and
     do not trigger this gate.

Display:
```
── Phase 2: Artifacts ── DONE
Commits: {N}
{when phase2_failures is not empty:}
⚠️ Phase 2 partial failures: {phase2_failures, comma-separated}
```

## Phase 3: Post-implementation review

Automated review of the implementation using plan-reviewer, with a fix loop for BLOCK
findings. This is the second stage of the 3-stage review structure (brainstorm self-review →
**cycle post-review** → final gate).

**Execution context**: the main context orchestrates Phase 3, but review and fix agents are
delegated to subagents (high-performance model). The main context holds only verdicts and
finding summaries.

**Inner satellite mode:** Phase 3 runs normally. Fix commits apply to the satellite worktree.

**plan-reviewer execution mode:** plan-reviewer is launched as a subagent in Phase 3. Per
plan-reviewer's execution fallback rule, a subagent context triggers sequential mode
(dimensions run inline, Codex second opinion is skipped). This is expected behavior — the
7-dimension review still runs with full coverage; the Codex independent perspective is
provided separately in Phase 4.

### Step 1: Initial review

Launch a review subagent (high-performance model):
- Prompt: "Execute the skill `claude-skills:plan-reviewer`. Review the implementation of
  plan file {plan_file_path}. Scope the review to changes introduced by this cycle only:
  use `git diff {cycle_start_sha}..HEAD` as the implementation diff. **Before sending your
  completion report**, write the full review result (overall verdict, dimension scores, all
  findings with file/location/severity/suggestion, escalation items) to
  `.agents/runtime/delegation/{run_id}_{role}.md`. The report is merely a notification that
  the file was written."
- For the initial review, `{role}` = `post-review`. For re-reviews after a fix iteration,
  `{role}` = `post-review-{N}` where N is the iteration number.
- Follow the [delegation result relay](#delegation-result-relay-shared-by-phases-1-3-and-4--delegation-mode-only)

### Step 2: Verdict branch

Read the review result and branch. **If escalation items are present alongside a score-band
verdict, ESCALATE takes priority regardless of the score band** (BLOCK+ESCALATE and
WARN+ESCALATE both route to ESCALATE):

| Verdict | Action |
|---------|--------|
| PASS | Proceed to Phase 4 |
| WARN | Record findings, proceed to Phase 4 |
| BLOCK (no escalation items) | Enter the fix loop (Step 3) |
| ESCALATE (any escalation items present) | Abort the cycle immediately (Step 2a) |

**Step 2a: ESCALATE abort**

Before displaying the abort message, revert the plan file's **Status:** header to
`⚠️ Review Failed` so that a future cycle can re-select this plan.

```
⛔ CYCLE ABORTED: Specification gap detected
Escalation items:
  {list of escalation findings with spec gap details}
Action: Resolve spec gaps in brainstorm before re-running the cycle.
  → /claude-skills:brainstorm
```

### Step 3: Fix loop (max 2 iterations)

Repeat up to 2 times:

a. Extract fix-targeted findings from the review result: include all findings with severity
   `critical`, plus all findings with severity `important` from dimensions whose verdict is
   BLOCK (score 80-100). Minor findings and important findings from non-BLOCK dimensions are
   WARN-level — record them but do not include them in the fix payload.
   (Per the [output format](../plan-reviewer/references/output-format.md), findings carry
   `severity: critical / important / minor`; BLOCK is the dimension/overall verdict, not a
   finding severity.)
b. Launch a targeted-fix subagent (high-performance model):
   - Prompt: "Fix the following review findings in the implementation. For each finding,
     apply the suggested fix or an equivalent correction. After all fixes, run the full test
     suite and verify all tests pass. Commit the fixes. **Before sending your completion
     report**, write the result (files changed, test output, findings addressed vs not
     addressed) to `.agents/runtime/delegation/{run_id}_fix-{N}.md`."
   - Append the fix-targeted findings as structured data (severity, task, title, description,
     location, suggestion)
   - Follow the delegation result relay with `{role}` = `fix-{N}`
c. After the fix subagent completes, run the same clean tree gate as Phase 2 Step 3
   (`git status --porcelain --untracked-files=all` must be empty). If dirty, revert plan
   status to `⚠️ Review Failed` and abort — uncommitted fix changes would be invisible to
   the re-review.
d. Re-launch the review (same prompt as Step 1) with `{role}` = `post-review-{N}`
e. Branch on the new verdict:
   - **PASS / WARN** → proceed to Phase 4
   - **ESCALATE** → revert plan status and abort (same as Step 2a)
   - **BLOCK and iteration < 2** → repeat from (a)
   - **BLOCK and iteration ≥ 2** → revert plan status and abort:
     ```
     ⛔ CYCLE ABORTED: Review loop exhausted (2 fix iterations)
     Remaining BLOCK findings:
       {list of unresolved BLOCK findings}
     Action: Fix manually with /iterate and re-run the cycle.
     ```

Display:
```
── Phase 3: Review ──
Review: {verdict} (max score: {N}, driven by {dimension})
{when fix loop ran, show each iteration:}
  Fix iteration {N}: {findings_addressed}/{total} findings addressed
  Re-review: {verdict} (max score: {N})
{when WARN findings exist:}
  ⚠️ WARN findings recorded: {count}
```

## Phase 4: Final gate

Pre-PR holistic review by a high-capability model and an independent review system. Phase 3
verified dimensional correctness; Phase 4 catches cross-cutting issues the 7-dimension
review may have missed. Phase 3's sequential mode skips the Codex second opinion, so
Phase 4's independent review is the sole Codex perspective in the cycle — the two phases
are complementary, not redundant.

Phase 4 produces a review verdict; it does not itself transition the change into a protected
state such as `publishable`. Do not block this review solely because SHA-bound
`machine_verified` / `semantic_reviewed` evidence for a later publication transition is not
present, and do not fabricate or reuse such evidence here. The caller that performs the
protected-state transition owns that quality-gate check and must re-earn evidence for the
exact target SHA.

**Inner satellite mode:** Phase 4 runs normally. The holistic review operates on the
satellite worktree's diff; the independent review receives only the plan file contents.

### Step 1: Launch parallel reviews

Launch two reviews in parallel:

a. **Holistic review** (high-performance model):
   - Prompt: "Review the implementation diff for plan {plan_file_path} holistically, scoped
     to changes from this cycle only (`git diff {cycle_start_sha}..HEAD`).
     You are the final gate before this becomes a PR. Focus on:
     - Cross-cutting concerns the dimensional review may have missed
     - Design coherence across all changes
     - Subtle integration issues between changed components
     - Overall fitness for merge
     Output: verdict (PASS/WARN/BLOCK), findings list (each with severity and description),
     and overall assessment.
     **Before sending your completion report**, write the result to
     `.agents/runtime/delegation/{run_id}_final-holistic.md`."
   - Follow the delegation result relay with `{role}` = `final-holistic`

b. **Independent review** (external review system):
   - Prompt: "Review the following implementation against its plan comprehensively. Point out
     problems, oversights, and spec conformance issues.
     Plan file contents: {plan file contents}.
     Output: verdict (PASS/WARN/BLOCK) and findings list (each with severity: critical /
     important / minor, title, description, and suggestion).
     Write the result to `.agents/runtime/delegation/{run_id}_final-independent.md` before
     sending your completion report."
   - Follow [codex-integration.md](../shared/references/codex-integration.md)
   - **Security constraint**: pass only the plan file contents. Never pass source code

### Step 2: Aggregate and branch

Collect both reviews following the [wait discipline](../shared/references/orchestration-patterns.md):
- **Holistic review**: required. On timeout, redelegate once; if still missing after
  redelegation, record the gap and continue with whatever arrived
- **Independent review**: optional. On timeout or error:
  ```
  ⚠️ Independent review unavailable — proceeding with holistic review only.
  ```

Determine the overall verdict:
- If holistic review arrived: overall verdict = worst of all arrived reviews
  (BLOCK > WARN > PASS)
- If holistic review did not arrive (even after redelegation): overall verdict = UNVERIFIED,
  regardless of independent review result. The independent review sees only the plan file
  and cannot substitute for implementation-level verification

| Verdict | Action |
|---------|--------|
| PASS | Proceed to Phase 5 |
| WARN | Record findings, proceed to Phase 5 |
| BLOCK | Stop the cycle (no fix loop) — see below |
| UNVERIFIED | Stop the cycle — see below |

**BLOCK / UNVERIFIED stop:**

Before displaying the stop message, revert the plan file's **Status:** header to
`⚠️ Review Failed` so that a future cycle can re-select this plan.

```
⛔ CYCLE STOPPED: Final gate {BLOCK / UNVERIFIED}
{when BLOCK:}
Findings:
  {list of BLOCK findings from both reviews}
{when BLOCK:}
Action: Use /iterate to address findings, then re-run the cycle.
{when UNVERIFIED:}
The required holistic implementation review is unavailable. The plan-only
independent review cannot substitute for implementation-level verification.
Action: Re-run the cycle (the holistic review will be reattempted).
```

Display:
```
── Phase 4: Final Gate ──
Holistic: {verdict / ⚠️ unavailable}
Independent: {verdict / ⚠️ unavailable}
Final: {overall verdict}
```

## Phase 5: Completion

This phase runs only after Phase 3 and Phase 4 pass or warn. If either phase aborted,
stopped, or returned UNVERIFIED, Phase 5 does not execute.

**Execution context**: run directly in the main context (same as Phase 2).

**Run each Phase 5 step independently; if one step fails, continue with the rest.** Record
failed steps in `phase5_failures`. Phase 5 follows the same partial-failure tolerance as
Phase 2.

1. **Generate the result file** at `.agents/artifacts/plans/results/{plan_basename}_result.md`,
   where `{plan_basename}` is the plan filename without its `.md` extension
   (`mkdir -p` the directory if missing). This step runs in Phase 5 (not Phase 2) so that it
   captures all commits including Phase 3 fix iterations.
   - **Inner satellite mode:** defer result-artifact composition to the outer orchestrator. Do
     not create this file in the satellite; retain the facts listed in the final display for
     the completion relay.
   - **On failure**: append `"result file generation"` to `phase5_failures` and move on

   Result file content:
   ```markdown
   # Cycle Result: {feature_name}

   Artifact paths follow the Agent Artifact Store contract.

   **Plan:** {plan_file_path}
   **Executed:** {datetime}

   ## Implementation
   - Steps completed: {N}/{total}
   - Files changed: {N}
   - Tests added: {N}
   - Commits: {N} (all commits across the cycle, including fix iterations)

   ## Review
   - Post-implementation review: {verdict} (max score: {N})
   - Fix iterations: {N}
   - Final gate: {verdict}

   ## Commits
   {the full commit list from git log --oneline}

   ## Notes
   {anything noteworthy}
   ```

2. **Mark status.md as completed**:
   - **Inner satellite mode:** skip all of Step 2; skip singleton status and session-history
     composition. The outer orchestrator owns those writes.
   - **Step 2a: Pre-check (failure detection first)**: Read `.agents/artifacts/status.md`
     and confirm the Current Session section exists
     - If the Current Session heading itself is absent, or the table is unparsable
       → append `"status.md update"` to `phase5_failures` and move on (**treat as a
       failure, not a guard** — this includes old-format status.md files without session
       management: do not repair or rewrite them, just record and continue)
     - Current Session section exists → Step 2b
   - **Step 2b: Guard (skip only when already archived)**: the Current Session body starts
     with `_No active session` → Case 2 has already run; do nothing and move on (not a
     failure). **Decide on that body text alone, never on the `Phase` field** — `🟢 Complete`
     is what Phase 1 writes on a session that is still listed, i.e. not yet archived.
   - **Step 2c: Normal processing (guard does not apply)**: follow **Case 2 (In Progress →
     Completed)** of [status-update-guide.md](../plan/references/status-update-guide.md).
     Case 2 applies to any still-listed session regardless of its Phase label:
     - Step 2a: archive to session-history.md
     - Step 2b: clear the Session History section
     - Step 2c: clear Current Session
   - **On failure during Step 2c** (Edit failure, write failure, ...): append
     `"status.md update"` to `phase5_failures` and move on
   - **Record which branch Step 2 took** (`archived` / `already archived` / `failed`) in the
     final display — a silent skip is otherwise indistinguishable from a silent success

3. **Verify plan file status**: verify the plan file's own **Status:** header is marked
   completed (implement normally does this; update it here if it is stale) — otherwise the
   next cycle's Phase 0 would reselect this plan. On failure, append `"plan status update"`
   to `phase5_failures` and move on

4. **Auto-close the issue**: read the plan file and check for an `**Issue:**` line
   - **Inner satellite mode:** must not auto-close a linked issue. Return its slug to the outer
     orchestrator, which may close it only after merge, post-merge verification, and artifact
     publication all succeed.
   - If present: extract the issue slug and execute the skill `claude-skills:issue` with
     `close {slug}`
     - If close fails, display a warning only; the cycle itself still counts as a success
       (do not roll back the implementation)
     - **Record the close outcome and include it in the final display**
   - If absent: skip this step

5. **Final display**:
```
══════════════════════════════════════
CYCLE COMPLETE
Feature: {feature_name}
Implement: {steps_done}/{steps_total} steps
Review: {PASS / WARN ({N} findings) / fix loop: {N} iterations → {verdict}}
Final Gate: {PASS / WARN}
Commits: {N} (all commits across the cycle)
Result: {result_file_path}
Session: {archived → session-history.md / already archived / ⚠️ update failed}
Issue: {closed ✅ / ⚠️ close failed: {slug} — manual close required / (none)}
{when phase2_failures or phase5_failures is not empty:}
⚠️ Partial failures: {all failures, comma-separated}
──────────────────────────────────────
💡 Need tweaks? Use /iterate for quick fixes and polish.
══════════════════════════════════════
```

In inner satellite mode, the completion relay must return the implementation counts, commit list,
plan status, review verdict and findings summary, final gate verdict, linked issue slug, and
phase failures. These are non-authoritative facts for the outer orchestrator to compose the
result artifact and decide issue closure after harvest, merge, verification, and publication.
Show `Result: deferred to outer orchestrator`, `Session: deferred to outer orchestrator`,
and `Issue: deferred to outer orchestrator: {slug | none}`.

## Error handling

- **Subagent error in Phase 1**: retry once automatically. If the retry also fails,
  abort the cycle.
- **Delegate stops without reporting in Phase 1** (work done + no completion report
  + only a wait notice — the most common stall): do not treat as an error and re-delegate
  immediately; follow pillar 3 (upper watchdog) of the
  [wait discipline](../shared/references/orchestration-patterns.md). First read
  `.agents/runtime/delegation/{run_id}_{role}.md` → if missing/incomplete, inspect the
  artifacts directly (commit history, changed files, test results, plan steps) to judge
  phase completion → retry (once) only when undecidable. If the result file or artifacts
  confirm completion, proceed to the next phase even without a delivered report.
- **Error in a Phase 2 step**: record the step in `phase2_failures` and continue with the
  rest. **Exception**: the clean tree gate (Step 3) is a hard stop — if uncommitted or
  untracked non-ignored files remain after the commit step, the cycle aborts (uncommitted
  or untracked changes would bypass Phase 3/4 review). Revert plan status before aborting.
- **Review subagent error in Phase 3**: retry once. If the retry also fails, abort the cycle
  (revert plan status to `⚠️ Review Failed` before aborting). Follow the same delegation
  result relay and wait discipline as Phase 1, using the extended 20-minute timeout for
  review delegates.
- **Fix subagent error in Phase 3**: retry once. If the retry also fails, abort the cycle
  (revert plan status to `⚠️ Review Failed` before aborting).
- **Dirty tree after Phase 3 fix**: if the clean tree gate after a fix subagent detects
  uncommitted or untracked non-ignored files, abort the cycle (same behavior as the Phase 2
  clean tree gate). Revert plan status before aborting.
- **ESCALATE in Phase 3**: abort the cycle immediately with brainstorm redirect. This is an
  intentional abort (spec gaps cannot be resolved by implementation fixes), not an error.
  Revert plan status before aborting.
- **Review subagent error in Phase 4**: holistic review is required — retry once, then record
  the gap and continue with whatever arrived (this is an exception to the general "abort
  after failed retry" rule because Phase 4 is a secondary gate after Phase 3 already passed).
  Independent review is optional — on error, warn and continue.
- **Error in a Phase 5 step**: record the step in `phase5_failures` and continue with the
  rest. Phase 5 errors never fail the whole cycle (same tolerance as Phase 2).

## Key rules

- **Delegate each phase to a subagent** (when delegation is available). Keep only summaries
  in the main context.
- **Specify a high-performance model when launching subagents.** Even if the session runs on
  a top-tier model, run delegates on a high-performance model to avoid cost blowups
  (per the model hierarchy in
  [orchestration-patterns.md](../shared/references/orchestration-patterns.md)).
- **No user confirmation prompts** (headless execution).
- **Retry once on subagent errors.** Abort after a failed retry; do not retry twice.
  Exception: Phase 4 holistic review degrades gracefully instead of aborting (see Error
  handling).
- **Phase 2 and Phase 5 tolerate partial success.** Individual step failures do not roll back
  the cycle.
- **Phase 3 aborts on ESCALATE or exhausted fix loop.** ESCALATE = spec gap (brainstorm
  redirect). Exhausted loop = 2 fix iterations with BLOCK remaining. All abort paths revert
  the plan status to allow re-selection.
- **Phase 4 stops on BLOCK or UNVERIFIED without a fix loop.** The final gate is a quality
  gate, not a fix opportunity. Use /iterate for post-gate fixes, then re-run the cycle.
- **Phase 5 runs only after Phase 3 and Phase 4 pass or warn.** Issue close, result file
  generation, and status completion are gated on review success.
- When the root cause of a problem is unknown, recommend a read-only pre-investigation with
  `/claude-skills:investigate` before running the cycle.
