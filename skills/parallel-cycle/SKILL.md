---
name: parallel-cycle
description: Decompose a natural language instruction into multiple plans, check file orthogonality, execute independent cycles in parallel via worktrees, and merge results. Supports both natural language decomposition and direct plan file specification. Use when the user says "parallel-cycle", "run these in parallel", "implement them in parallel", or gives a compound instruction that should be split into independent cycles.
---

# Parallel Cycle

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

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
  │     Create worktree → ingress plan/capability → delegate → collect satellite
  │
  ├── Phase 3: Merge
  │     Merge → verify → publish collected artifacts → cleanup when allowed
  │
  └── Phase 4: Summary
        Unified report of all cycles
```

## Input Detection

Determine input type from `$ARGUMENTS`:

- **All arguments end in `.md`** → Treat as plan file paths. Skip Phase 0, go to Phase 1.
- **Otherwise** → Treat as natural language instruction. Start from Phase 0.

## Preserved Worktrees

A failed cycle leaves its worktree in place (§Failure Handling). **Before Phase 0 / Phase 1, in
both input modes**, run `git worktree list` and report every preserved worktree with its path,
its branch, and whether that branch is already merged into `main`.

Removal is a decision, never a timer:

- **Only when Step 0.2 actually runs** (natural-language mode that reached 2+ plans): fold the
  removal question into that same approval prompt — no second confirmation point is created
  (§Important Rules). Remove only the paths approved there, with
  `git worktree remove --force {path}`
- **Everywhere else** — plan-file mode, the 0-plan exit, the 1-plan headless path, and any
  other headless run: report the list and **remove nothing**. Never open a prompt that exists
  only to ask about cleanup: there is no one present to answer, and a prompt there is
  indistinguishable from a stall

Do not remove a preserved worktree on an age or count threshold, and do not treat "the branch is
merged" as permission to remove it unasked. Merging proves the *committed* work survived; the
reason to keep the tree is everything that was never committed. Age-based cleanup would recreate
the exact failure this rule exists to prevent — the diagnostic state is gone by the time anyone
looks for it.

## Phase 0: Decompose

**Step 0.0: take the main working tree** per the
[Workspace Lock contract](../shared/references/workspace-lock.md), before decomposition and
before writing any project state. `LOCK_HELD` → stop and show the holder's `skill` / `pid` / `branch` /
`started_at`; `STALE_RECLAIMED` → report it and continue; `UNAVAILABLE` → warn once and
continue (fail-open). Release on every exit path.

The lock covers **the main tree only**. Each worktree created in Phase 2 has its own
`.agents/runtime/`, so it is a separate resource and its delegate claims it independently —
do not pass the main tree's token into a worktree delegate.

Decompose a natural language instruction into multiple plans.

### Step 0.1: Analyze and Decompose

Have a subagent decompose the instruction. Do not pin a model here — decomposition and orthogonality judgment are upstream high-stakes decisions and should run on the session model (see [orchestration-patterns.md](../shared/references/orchestration-patterns.md) § Model Tiering):

**Subagent instruction:**
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
- **1 plan** → jump to the "Edge Cases" section below (`claude-skills:cycle` in its own worktree). Skip Step 0.2 **only** — Step 0.3 still runs.
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

Present the choices to the user and obtain approval.

- **y** → Proceed
- **n** → Abort with message
- **edit** → Accept modification instructions, re-decompose (return to Step 0.1)

### Step 0.3: Generate Plan Files

For each approved plan, generate the plan file with a subagent (lightweight model — mechanical file generation from an already-approved decomposition):

Capture `{timestamp}` **once, here, before launching anything**, and resolve each plan's full path
yourself. The path is then handed to the subagent — it is not something the delegate derives.

**Subagent instruction:**
```
Invoke the `claude-skills:plan` skill in caller-supplied mode and create a plan for
the following feature.
Feature: {plan_title}
Description: {plan_description}
Affected files: {file_list}

Caller-supplied parameters:
  output_path: {plan_file_path}
  skip_status: true
```

The `output_path` and `skip_status` parameters are the plan skill's formal
[caller-supplied mode](../plan/SKILL.md#caller-supplied-mode) contract. Do not
override the plan skill's behavior with ad-hoc natural-language instructions.

`{plan_file_path}` is `.agents/artifacts/plans/{timestamp}_{plan_id}_{slug}.md` — **relative to the
repository root**, not to the delegate's working directory — where `{plan_id}` is the plan letter
(`A`, `B`, …) from the approved decomposition.

Two invariants have to hold, and each names one part:

- **The batch is recognizable.** Every plan of one decomposition carries the same `{timestamp}`, so
  the group is visible in `.agents/artifacts/plans/` without consulting anything else. Let each plan
  take its own timestamp and that is gone. The timestamp **groups**; it does not prove membership
  (a plan written in the same second by any other caller shares the prefix), so the authoritative
  record of what a batch contained is the result file's `## Plan Files` list
- **Each plan is unique within the batch.** That is `{plan_id}`'s job, **not** `{slug}`'s. Two plans
  from one instruction can legitimately produce the same slug (§Phase 2), and with the slug as the
  only differentiator they resolve to the *same path* — one silently overwriting the other, or both
  being written at once

The delegate cannot uphold either one: `claude-skills:plan` takes its own clock reading and builds
its own name, so parallel launches that straddle a second boundary land on different timestamps.
That is why the caller assigns the path instead of stating a rule and hoping.

`{timestamp}` is **not** the identifier used for worktrees or for the result file — those name a
*run*, and one batch of plans can be run more than once (§Phase 2, §Step 4.3).

**Concurrency**: Step 0.3 may launch the subagents for all plans in parallel (up to 3 at a time).
That is safe for the **plan files** because `{plan_id}` makes every target path distinct — the
parallelism rests on that, not on an absence of data dependencies.

It is **not** safe for `status.md`. Left alone, `claude-skills:plan` also rewrites
`.agents/artifacts/status.md` and `session-history.md` — read-modify-write on a shared file, three
at a time, each deciding independently which session to archive as abandoned. That is why the
delegation prompt above forbids touching them, and why the consolidated update happens once in
Phase 4 (§Important: status.md Write Suppression).

### Edge Cases

- **0 plans**: Display an error message and exit. Do not invoke any fallback.
- **1 plan**: run `claude-skills:cycle` **inside a worktree**, the same as any other plan. Do NOT
  display the DECOMPOSE RESULT block and do NOT ask for approval — the 1-plan path is headless.

  1. Display only this message (single line, verbatim):
     ```
     Single plan detected. Falling back to /claude-skills:cycle.
     ```
  2. **Run Step 0.3 as usual** and generate the one plan file, with `{plan_id}` = `A`. Do not skip
     it: `claude-skills:cycle` does not build a plan from an instruction — given no path it
     auto-selects the newest incomplete plan under `.agents/artifacts/plans/` and aborts when there
     is none (see [cycle/SKILL.md](../cycle/SKILL.md) Phase 0). A fresh worktree's artifact store is
     empty, so a delegate handed the raw `$ARGUMENTS` would abort every time
  3. Skip Phase 1 — one plan has nothing to intersect — and carry forward the execution state it
     would have produced: **Group 1 = `[A]`, `{N}` = 1, `{M}` = 1, no dependencies**. Phase 3's
     merge order and Phase 4's `Groups:` line read those values, so they have to exist
  4. Enter Phase 2 normally. `{batch_run_id}` is captured at its entry as always, the worktree is created
     by step 1's rule, and the delegate is invoked **inside it** — but running
     `claude-skills:cycle` against the generated plan path, not `claude-skills:plan-implement`, so a
     single plan still passes the refine gate:

     ```
     You are working in a worktree at: {worktree_path}
     Branch: {branch_name}

     Invoke the `claude-skills:cycle` skill with this resolved execution context:
     pinned_plan={repository_relative_plan_path}
     resolved_isolation=worktree
     satellite_run_id={batch_run_id}-{plan_id}
     satellite_capability_file={capability_file_path}

     Treat this as an inner run: do not resolve isolation again or create a nested worktree.
     ```

     Pass no workspace-lock token — the outer orchestrator owns this resolved satellite isolation,
     so the inner delegate neither claims nor releases it (§Phase 2).
  5. Continue through Phase 3 and Phase 4 as usual: the branch is merged, and the worktree is
     removed or preserved by the **same rule as every other cycle** (§Step 3.4,
     §Preserved Worktrees). The result file's `Plan batch` is Step 0.3's `{timestamp}` and its
     `Plan Files` is the one generated path — the same as any natural-language run

  **Isolation is not a function of how many plans there are.** Running one plan directly in the
  main checkout would leave exactly one case where another session's work, or an unrelated starting
  branch, can end up in the commit — and on the polling path, whether that happens is decided by how
  many issues happened to be ready on that tick.

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

### Recovery diagnostic formatter

Every recovery instruction in this skill, including ingress, collect, publish, preserved-cycle,
and interrupted paths, MUST be emitted through this shared exact six-line formatter. Substitute
the closed reason code and the satellite identity; do not emit an additional shortened command.

```text
reason_code={reason_code}
run_id={satellite_run_id}
main_tree_path={main_tree_path}
worktree_path={worktree_path_or_unavailable}
reason={reason}
recovery_command=/claude-skills:artifacts recover --run-id {satellite_run_id}
```

### For Each Group

For each cycle in the group, **in parallel**:

1. **Create the worktree**: create an isolated working tree and branch with git worktree.

   Name both after the **run**, not the plan: branch `parallel/{batch_run_id}-{plan_id}-{slug}` and a
   worktree path carrying the same suffix.

   - `{batch_run_id}` is captured **once at Phase 2 entry** and shared across the batch. Derive it from
     the current time at a precision that cannot repeat across back-to-back runs (sub-second, or
     seconds plus a short random suffix). It must **not** come from the plan file: a preserved
     worktree still holds its branch checked out, git refuses to hand that branch to a second
     worktree, so any plan-derived name collides the moment the same plan is re-run after a failure
   - `{plan_id}` distinguishes plans within the run — the plan letter in natural-language mode, the
     one-based argument position in plan-file mode
   - `{slug}` is for readability only. **Uniqueness must never depend on it**, since two plans can
     legitimately share a slug

   Before ingress, derive `{satellite_run_id}` from `{batch_run_id}` and `{plan_id}` using the
   shared transport helper: `{satellite_run_id}={batch_run_id}-{plan_id}`. This is the lifecycle
   identity for exactly one satellite. For example:
   `Plan A: satellite_run_id={batch_run_id}-A; Plan B: satellite_run_id={batch_run_id}-B`.
   The runtime/provenance, capability file, staging, lifecycle, and recovery command are keyed by
   `{satellite_run_id}`; the batch summary and result filename are keyed only by `{batch_run_id}`.

   If `git worktree add` still fails, do not improvise another path: record that cycle as failed
   and continue (§Failure Handling).
2. **Initialize satellite and ingress the pinned plan** immediately after worktree creation and
   before launching any delegate. Use the shared satellite transport to create authoritative
   main-tree provenance, copy the plan to the same repository-relative path in the satellite,
   create its ingress manifest, and write the mode-`0600` capability file. If ingress fails,
   record the terminal failure, revoke any created capability, preserve the worktree, and emit the
   Recovery diagnostic formatter with `reason_code=SATELLITE_PRESERVED`. Never launch the delegate
   without a complete ingress.

3. **Run the cycle**: launch a subagent (high-performance model — implementation is protected by verification gates, so do not inherit the expensive session model) and run the cycle inside the worktree.
   **Pass no workspace-lock token.** The outer orchestrator owns this resolved satellite
   isolation; the inner delegate neither claims nor releases it:

   **Subagent instruction:**
   ```
   You are working in a worktree at: {worktree_path}
   Branch: {branch_name}

   Invoke the `claude-skills:plan-implement` skill with this resolved execution context:
   pinned_plan={repository_relative_plan_path}
   resolved_isolation=worktree
   batch_run_id={batch_run_id}
   satellite_run_id={batch_run_id}-{plan_id}
   satellite_capability_file={capability_file_path}

   Implement every step, commit after each step, and update the runtime progress file.
   On completion, report: number of files changed, number of tests added, number of commits.
   ```

   The context is authoritative and already resolved; the delegate must not resolve workspace
   policy again or create a nested worktree. Never place the raw capability in this prompt or any
   completion output. Pass only `satellite_capability_file`.

4. **Collect the satellite store** before leaving Phase 2. Enter harvesting, consume or revoke
   the capability as appropriate, and collect validated satellite artifacts into main-runtime
   staging on success, implementation failure, cancellation, and verification failure. The
   durable satellite plan, not completion prose, is the source of progress. Record the delegate
   summary separately as non-authoritative completion prose.

   A collect failure or conflict enters `recovery_required`: must not remove the worktree, must
   retain staging and both source versions, and must emit the Recovery diagnostic formatter. A
   successfully collected failed cycle is also preserved; collected state is not published unless
   its branch later merges and verifies.

   Every preserved, conflict, or interrupted terminal path MUST use the shared six-line structured
   diagnostic formatter from the workspace-isolation contract. Use
   `reason_code=SATELLITE_PRESERVED` for a preserved satellite,
   `reason_code=HARVEST_CONFLICT` for an artifact conflict, and
   `reason_code=HARVEST_INTERRUPTED` when harvest does not complete. Do not hand-compose a shortened
   message: all six fields, including the `{satellite_run_id}` recovery command, are required.

5. **Do not remove the worktree here.** Removal is Step 3.4's decision, and only for a cycle that
   merged cleanly — a worktree torn down in Phase 2 is unavailable when Phase 3's post-merge test
   fails and the revert has to be explained. On cycle failure it is preserved outright
   (§Failure Handling)

### Failure Handling

- If a cycle fails, record the failure and preserve **both the branch and the worktree**. The
  branch only carries what was committed; the uncommitted edits, the test output, and the
  `.agents/` state the run left behind are the part worth diagnosing, and a cycle that died
  mid-implementation may have committed nothing at all
- Report the preserved worktree's path everywhere the failure is reported (Step 4.2 and the
  result file), so the reader can go look without reconstructing the path
- Check if any cycles in later groups depend on the failed cycle
- Mark dependent cycles as "skipped (dependency failure)"

### Concurrency Limit

Launch at most 3 subagents concurrently per group. If a group exceeds 3, split it into sub-batches.

### Important: status.md Write Suppression

Do NOT update `.agents/artifacts/status.md` or `.agents/artifacts/session-history.md` from **any**
delegate — neither the plan-generating subagents of Step 0.3 nor the cycles of Phase 2. Both files
are read-modify-write, and every delegate that touches them decides on its own which session to
archive. The orchestrator performs a single consolidated update in Phase 4.

The rule lives here, but it only takes effect where it is **said to the delegate**: it is written
into the Step 0.3 delegation prompt and the Phase 2 one. A rule stated only in this section reaches
no one who is about to write the file.

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

**Publish collected artifacts** only after that cycle's merge and post-merge verification pass.
Publication must revalidate destination hashes under the lifecycle lock. If publish fails or
detects a conflict, publish nothing, mark `recovery_required`, preserve the worktree and staging,
and emit the Recovery diagnostic formatter with `reason_code=HARVEST_CONFLICT`. If verification
fails and the merge is reverted, do not publish completed progress.

### Step 3.4: Cleanup

Remove the worktree only after the cycle merged, passed its post-merge test, published its
collected artifacts, revoked/consumed its capability, and reached `cleanup_allowed`. Leave every
other worktree in place — failed, merge-reverted, and skipped cycles all keep theirs
(§Preserved Worktrees).

```bash
git worktree remove {worktree_path}   # per successfully merged cycle
git worktree prune                    # bookkeeping only; never removes a live directory
```

## Phase 4: Summary

### Step 4.1: Update Status

Update `.agents/artifacts/status.md` with consolidated results for all cycles.

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
  [C] {title} — ❌ Failed (reason) — worktree kept: {worktree_path}
  [D] {title} — ⏭ Skipped (dependency: C)

Commits: {total_commits}
Files changed: {total_files}
──────────────────────────────────────
```

### Step 4.3: Generate Result File

Save the summary to `.agents/artifacts/plans/results/{batch_run_id}_parallel_result.md`, using the
same `{batch_run_id}` that Phase 2 captured.

The name comes from the **run**, not from the plans, for two reasons. A batch has one result file
but many plans, so no single plan name can stand for it — and in plan-file mode the arguments are
pre-existing files that share nothing to derive a name from. Naming by run also means re-running a
batch after fixing its failures writes a **second** result file instead of overwriting the record of
what failed the first time.

```markdown
# Parallel Cycle Result

**Executed:** {datetime}
**Run ID:** {batch_run_id}
**Plan batch:** {timestamp in natural-language mode; `external` in plan-file mode, where the
arguments are pre-existing files that share no batch timestamp}
**Plans:** {N}
**Groups:** {M}

## Plan Files
{one path per plan — the authoritative record of what this run consumed, and the only one that
holds in plan-file mode}

## Results

| Plan | Title | Status | Commits | Files |
|------|-------|--------|---------|-------|
| A | {title} | ✅ Merged | {n} | {n} |
| B | {title} | ❌ Failed | - | - |

## Commits
{git log --oneline for all merged commits}

## Failed / Skipped Cycles
{details for any non-successful cycles, each with its preserved branch and worktree path}
```

## Important Rules

- **Orchestrator is glue code only** — All heavy logic is delegated to subagent/skill invocations
- **File orthogonality is the safety guarantee** — Never allow parallel execution of plans with file intersections
- **Partial success is acceptable** — Merge what succeeds, preserve what fails
- **Single user confirmation point** — Only Phase 0 approval. Everything else is headless
- **Worktree cleanup is mandatory on success, forbidden on failure** — A failed cycle's worktree
  is the diagnostic evidence; removing it destroys exactly what the failure needs (§Preserved
  Worktrees)
- **No force push, no rebase** — Standard merges only
- **status.md updates are consolidated** — No parallel writes to shared files
