---
name: parallel-cycle
description: Decompose a natural language instruction into multiple plans, check file orthogonality, execute independent cycles in parallel via worktrees, and merge results. Supports both natural language decomposition and direct plan file specification.
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
  │     EnterWorktree → Agent (cycle) → ExitWorktree
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

Use the Agent tool to decompose the instruction:

**Agent prompt:**
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

Use AskUserQuestion for approval.

- **y** → Proceed
- **n** → Abort with message
- **edit** → Accept modification instructions, re-decompose (return to Step 0.1)

### Step 0.3: Generate Plan Files

For each approved plan, use the Agent tool to generate a plan file:

**Agent prompt:**
```
Use the Skill tool to invoke `claude-skills:plan` to create a plan for the following feature.
Feature: {plan_title}
Description: {plan_description}
Affected files: {file_list}
```

Each plan is saved to `docs/plans/{timestamp}_{slug}.md`.

### Edge Cases

- **0 plans**: Display error message and exit
- **1 plan**: Display message and fall back to normal `/claude-skills:cycle`:
  ```
  Single plan detected. Falling back to /claude-skills:cycle.
  ```
  Invoke the `claude-skills:cycle` skill via Skill tool and exit.

## Phase 1: Orthogonality Check & Grouping

See [references/orthogonality-check.md](references/orthogonality-check.md) for detailed logic.

### Step 1.1: Extract Affected Files

Read each plan file and extract the file list from the "Files to Change" or equivalent section.

### Step 1.2: Compute Intersections

For every pair of plans, compute file set intersections.

### Step 1.3: Build Execution Groups

Combine intersection results with the dependency graph:

1. Plans with file intersections → must be in different groups
2. Plans with dependencies → dependent goes in a later group
3. Maximize parallelism within constraints
4. Maximum 3 concurrent cycles per group (split into sub-batches if more)

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

1. **Create worktree**: Use the `EnterWorktree` tool to create an isolated worktree and branch
2. **Execute cycle**: Use the Agent tool to run the cycle in the worktree:

   **Agent prompt:**
   ```
   You are working in a worktree at: {worktree_path}
   Branch: {branch_name}

   Execute the Skill tool to invoke `claude-skills:plan-implement` for the plan file: {plan_file_path}
   Implement all steps. Commit after each step. Update the progress table.
   When done, report: files changed, tests added, commits made.
   ```

3. **Collect result**: Record success/failure and summary for each cycle
4. **Cleanup worktree**: Use the `ExitWorktree` tool to remove the worktree

### Failure Handling

- If a cycle fails, record the failure and preserve the branch
- Check if any cycles in later groups depend on the failed cycle
- Mark dependent cycles as "skipped (dependency failure)"

### Concurrency Limit

Maximum 3 Agent invocations in parallel per group. If a group has more than 3 cycles, split into sub-batches of 3.

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

- **Orchestrator is glue code only** — All heavy logic is delegated to Agent/Skill invocations
- **File orthogonality is the safety guarantee** — Never allow parallel execution of plans with file intersections
- **Partial success is acceptable** — Merge what succeeds, preserve what fails
- **Single user confirmation point** — Only Phase 0 approval. Everything else is headless
- **Worktree cleanup is mandatory** — Success or failure, always clean up
- **No force push, no rebase** — Standard merges only
- **status.md updates are consolidated** — No parallel writes to shared files
