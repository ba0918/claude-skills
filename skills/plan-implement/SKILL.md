---
name: plan-implement
description: Implement every step of an implementation plan automatically through the TDD (RED then GREEN then REFACTOR) implement-review loop, reviewing, updating status, and committing at each step. It works both as Phase 2 of cycle and on its own. Use when the user says "plan-implement", "implement the plan", or "implement this plan automatically".
---

# Plan Implement

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Run the automatic implementation loop for an implementation plan.
Act as the orchestrator and drive implementation → review → feedback incorporation autonomously and repeatedly.

When any of the following applies, you may perform that role inline yourself instead of delegating or invoking another skill:
you cannot launch a subagent / another skill (`claude-skills:plan`, etc.) cannot correctly point at the target project /
the step is a trivial change of a few lines where the overhead of delegation does not pay off.
When updating status inline in direct mode, the update must satisfy all of the following
result conditions (what to achieve, not how):

1. The completed step is marked 🟢 Done in the plan file
2. The plan file's top-level `**Status:**` field matches the phase shown in status.md
   (use the status-update-guide vocabulary: 🟡 Planning / 🟡 In Progress / 🟢 Completed)
3. Session History in status.md (or session-history.md) contains a completion row when
   the cycle finishes
4. Each step's notes section in the plan file records the implementation summary
   (changed files, test count) and any accepted WARN/INFO findings

In satellite mode, update only the pinned plan through the authorized write path.
Even inline, the review (Step B) takes the stance of an independent, critical reviewer: do not assume the judgments made
while implementing — re-read only the code and the tests to evaluate them, and state findings explicitly as BLOCK / WARN / INFO.

## Parameters

- Argument: additional instructions (naming a specific step, narrowing the scope, etc.)
- Satellite execution context: a store-relative `pinned_plan`, the already resolved
  `resolved_isolation=worktree`, `satellite_run_id`, and `satellite_capability_file`.
  The capability parameter is a file path, never the raw bearer value.

When this complete context is present, run in **satellite mode**:

- Validate that `pinned_plan` is repository-relative, remains inside the canonical satellite
  artifact store, and matches the run provenance. Read that plan directly; do not select a plan
  through `status.md`.
- read the capability from `satellite_capability_file` only when authorizing a durable plan
  update. Never copy the raw capability into a prompt, artifact, log, commit, or report.
- The delegate updates the pinned plan directly through the authorized satellite-store write
  path. It must not invoke `plan` and must not write `status.md`, `session-history.md`, or derived
  indexes. The main-tree orchestrator composes those singleton files after harvest.
- TDD, review, verification, and per-step commits remain mandatory. Satellite mode changes
  artifact ownership only; it does not weaken any implementation or quality gate below.

Without the complete satellite context, use direct mode exactly as before. A partial context is
an error; do not guess paths, isolation, or capability data.

## Phase 0: Load the Plan and Update Status

0. **Working tree occupancy** — [Workspace Lock contract](../shared/references/workspace-lock.md).
   - **If a workspace-lock token was passed in** (running under `cycle` / `parallel-cycle`):
     do **not** claim and do **not** release. The orchestrator already holds this tree, and
     claiming again would deadlock against its own parent
   - **Standalone run (no token)**: take the tree before writing any project state. `LOCK_HELD` → stop before
     writing project state and show the holder's `skill` / `pid` / `branch` / `started_at`;
     `STALE_RECLAIMED` → report it and continue; `UNAVAILABLE` → warn once and continue
     (fail-open). Release on every exit path

1. In direct mode, read `.agents/artifacts/status.md` and identify the session currently at
   🟡 Planning. In satellite mode, read the validated `pinned_plan` directly.
   - Re-entry from a step partway through (a session already at 🟡 In Progress) is also a normal case
2. Load the corresponding plan file (inside `.agents/artifacts/plans/`)
3. Grasp the overall picture of the plan, the list of steps, and the current progress (do not re-implement 🟢 Done steps)
4. If the argument names a specific step, start from there
5. **Direct mode:** update the status to 🟡 In Progress (invoke the skill
   `claude-skills:plan`; no update is needed if already 🟡 In Progress).
   **Satellite mode:** update only the pinned plan through the authorized write path; do not
   invoke `plan` or write singleton/derived state.

## Phase 1-N: Implementation Loop (repeated per step)

For each step, do the following:

### Step A: TDD Implementation (Red → Green → Refactor)

Launch an implementation agent as a subagent. Make it **strictly observe** the TDD cycle below.

**TDD contract reference**: follow [tdd-contract.md](../shared/references/tdd-contract.md) and proceed test-first (RED → GREEN → REFACTOR).

#### Red (Test First)
1. Write the test **first**, from the requirements of the corresponding step of the plan
   - Express the expected inputs and outputs, the edge cases, and the error paths as tests
   - Observe the target project's `AGENTS.md` / `CLAUDE.md` and the shared [design-principles.md](../shared/references/design-principles.md)
   - Avoid the anti-patterns in [testing-anti-patterns.md](../shared/references/testing-anti-patterns.md)
2. Run the test and **confirm that it fails**
   - A compile error is acceptable (a reference to an unimplemented type or function)
   - Confirm too that no existing test has been broken
   - **Record the essentials of each step's RED failure output (error kind, message) and include them in the completion report** (writing only "RED confirmed" is not acceptable)

#### Green (Minimal Implementation)
3. Write the **minimum implementation** that makes the test pass
   - No excessive abstraction, no implementing ahead of need
   - Make all tests passing the first priority
4. Run the tests and **confirm they all pass**

#### Refactor
5. Tidy the code while the tests pass
   - Remove duplication, improve naming, separate responsibilities
   - **Confirm that all tests still pass** after the refactoring as well
   - When there is nothing to tidy (no duplication to remove, no naming to improve, no responsibility to separate),
     **record that basis and move on to the next step** — REFACTOR has an explicit exit for "no change needed".
     Do not move the structure just to have performed a REFACTOR (that is a YAGNI violation).
     Recording only "REFACTOR done" without stating what was changed, or what made a change unnecessary, is not acceptable

**Verification Gate**: check the test execution results at every step and follow the Gate Function of [verification-gate.md](../shared/references/verification-gate.md). Include the evidence that all tests pass (the command output) in the result file.

Receive the implementation result.

### Step B: Review

1. Launch a review agent as a subagent
   - Give it **strict evaluation criteria**. Make it take a critical stance
   - **When `.agents/config/review-rules.md` exists, you must load it and use it as the review criteria**
   - When there is no `.agents/config/review-rules.md`, use the default viewpoints below:
     - Whether anything violates the target project's own instructions or [design-principles.md](../shared/references/design-principles.md)
     - Whether responsibilities are mixed together
     - Whether the tests are sufficient (coverage, edge cases)
     - Whether there is a problem with performance or memory efficiency
     - Whether there is a security concern
     - Whether there is code duplication or dead code
   - Make it classify findings by severity (BLOCK / WARN / INFO) (definitions per
     [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md))
   - **Even with zero findings, make it report "BLOCK / WARN / INFO: none" explicitly** (leaving evidence that the classification scheme was applied)
2. Receive the review result

### Step C: Judgment and Incorporation

1. Deliberate on the review result
   - **BLOCK**: a fix is mandatory → return to Step A (issue fix instructions)
   - **WARN**: an improvement is desirable → consider the content and decide whether to fix it
     - Fixing it → return to Step A
     - Accepting it → record the rationale in the step's notes in the plan file (written during Step D) and move on
   - **INFO**: reference information → record it and move on
2. When BLOCK/WARN remain, launch a fix agent and address them
3. After the fix, run the Step B review again
4. **Repeat this loop until no BLOCK remains** (count one round trip of Step B review → Step C fix as one iteration, up to 3 iterations **per step**)
   - A review round that produced **zero findings is not counted as an iteration** — an iteration is a round trip that
     actually incorporated a fix. A review with nothing to fix ends the loop instead of consuming the iteration budget

### Step D: Progress Update and Commit (mandatory — must not be skipped)

**Always do this on completing each step. You must not skip it.**

1. In direct mode, invoke the skill `claude-skills:plan` and update the following. In satellite
   mode, perform the same progress and notes update directly in the pinned plan through the
   authorized write path, without invoking `plan` or updating singleton/derived state:
   - Change the status of the completed step to 🟢 Done
   - Note the information for the next step
   - Record a summary of the implementation (changed files, test count, etc.)
2. Commit that step's changes (implementation, tests, status update)
   - Do not track build artifacts or caches (e.g. `__pycache__`, `node_modules`, `target`). If they get mixed in, set up the ignore configuration first
   - In a project where `.agents/artifacts` is outside Git tracking, the status update is not part of the commit (commit only the implementation and the tests)
3. Move on to the next step only after the commit is done

## Phase Final: Completion Handling

After every step is complete:

1. Run a **review of the whole set of changes** in a subagent
   - Check all changes with `git diff`
   - Verify exhaustively that every issue in the implementation plan has been resolved
   - Run the project's test command and confirm everything passes (e.g. `cargo test`, `npm test`, `go test ./...`)
   - Run the project's lint command and confirm there are no warnings (e.g. `cargo clippy`, `eslint`, `golangci-lint`). In a project with no lint configured, skip it and report that
2. If the final review has any finding of WARN or above, go back to the fix loop (maximum 3 iterations — same budget as Step C)
   - **WARN findings that were accepted with recorded rationale during Step C are excluded** from the fix-loop trigger.
     The authoritative record is each step's notes in the plan file, written during Step D
   - A review round with zero actionable findings (after exclusions) ends the loop
   - If 3 iterations are exhausted with findings still open, escalate to the user with the remaining findings
3. Once everything is resolved:
   - In direct mode, invoke the skill `claude-skills:plan` and update the status to 🟢 Completed.
     In satellite mode, mark the pinned plan complete through the authorized write path and leave
     singleton/derived composition to the main-tree orchestrator
   - If uncommitted changes (the status update, etc.) remain, commit them
   - Present the implementation summary to the user

## Key Rules

- **Direct mode always updates status when each step completes. Satellite mode updates only the
  pinned plan and leaves singleton status composition to its orchestrator. Do not defer the
  applicable progress update.**
- **Strictly observe the TDD cycle (Red → Green → Refactor). Write the test before the implementation code.**
- **Implementation without tests is forbidden. If a test cannot be written, revisit the design.**
- **A BLOCK finding must be resolved before moving on.**
- **When the maximum iteration count is exceeded, list the remaining findings and ask the user to decide.**
- Always convey to each agent the contents of the target project's `AGENTS.md` / `CLAUDE.md` and [design-principles.md](../shared/references/design-principles.md).
