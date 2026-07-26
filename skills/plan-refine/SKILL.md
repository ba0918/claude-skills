---
name: plan-refine
description: A plan quality gate that improves an implementation plan through a review-fix loop driven by plan-reviewer, finishing when every dimension is PASS or the iteration limit is reached. It works both as Phase 1 of cycle and on its own. Use when the user says "plan-refine", "polish the plan", "review the plan and fix it", or "refine".
---

# Plan Refine

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Review an implementation plan with the `claude-skills:plan-reviewer` skill and improve it by editing the
plan file directly in response to the problems found. Loop this until every dimension is PASS or
the maximum iteration count is reached.

The vocabulary of the verdicts follows the definitions in [plan-reviewer](../plan-reviewer/SKILL.md). In short: each dimension carries a score of 0-100
(the weight of its heaviest finding), where 0-49 = PASS / 50-79 = WARN / 80-100 = BLOCK.
This skill's termination condition "every dimension PASS" is synonymous with "not a single WARN / BLOCK remaining".

## The plan-reviewer invocation boundary (handing over delegated results)

When launching `claude-skills:plan-reviewer` (as a subagent delegation), receive its result through a file, following
the [delegation result relay](../shared/references/orchestration-patterns.md).
Because a reachability problem has been measured in which the verdicts of reviews launched concurrently underneath fail to return to the aggregator and stall,
do not make the result depend on the delivery of a report message. plan-reviewer writes each dimension's verdict to
`.agents/runtime/delegation/{run_id}_review-{dim}.md`, and those are aggregated. The refine role collects the result from either
plan-reviewer's completion report or its stop/wait notification, and even when no report arrives it falls back to inspecting the
artifacts in this order: (1) plan-reviewer's aggregated result → (2) the per-dimension review result files
`{run_id}_review-{dim}.md` → (3) the body of the plan file (the very thing refine edits).
For `{run_id}`, use the Cycle ID at the top of the plan file (or the timestamp in the file name if there is none).

refine waits as an **intermediate orchestrator** — launching plan-reviewer while itself being a delegate of cycle — and
stalls from undelivered reports have been measured at exactly this position. While waiting, follow the
[wait discipline](../shared/references/orchestration-patterns.md): re-inspect the result file directory without depending on
notifications, and once nothing has arrived for a set period after the last arrival (10 minutes by default), switch to the fallback
inspection above. Recovery for the case where refine itself stalls underneath cycle is left to the pillar-3 watchdog that the
parent (cycle) sets up.

In an environment where plan-reviewer cannot be launched as a skill, use the following inline review substitute as a fallback.
In that case read **both plan-reviewer's SKILL.md body and its references**
(including the dimension definitions, the conditional UI/UX trigger judgment, the fallback provisions, and the output format), and
conduct the review inline yourself with the same dimensions and the same criteria.
In the inline substitute every result is aggregated into the same context, so no file handover is needed.
Because the inline substitute makes the reviewer and the fixer the same actor, suppress bias in the following two ways:
- When reviewing, do not take your own immediately preceding edit as given — re-read the plan body alone and score that
- When raising a verdict in a re-review after a fix, attach the grounds for the resolution (a quotation of the corresponding change). Never mark PASS without grounds

## Parameters

- The first number in the arguments: the maximum iteration count (default: 3)
- A file path in the arguments: the target plan file. When omitted, choose the head of the `*.md` files directly under
  `.agents/artifacts/plans/` sorted by **descending file-name timestamp** (do not use mtime, since edits reorder it)

## Flow

### Iteration 1 (full review)

1. Launch the `claude-skills:plan-reviewer` skill (a full review of the 7 dimensions, UI/UX being conditional)
   - Specify the target file in the arguments. When omitted, the newest file in `.agents/artifacts/plans/` is selected automatically
   - Remember the path of the target file (it is reused in later iterations)
2. Every result PASS → finish (go to the completion report)
3. When there are WARN/BLOCK findings:
   a. Consider each finding and improve the plan by editing the plan file directly
   b. Show the diff (the changed hunks or a summary of them) of **what was improved in that iteration**.
      Getting by with a single cumulative stat covering all iterations is not acceptable.
      For files where change tracking is unavailable, substitute a before/after summary
   c. Move on to the next iteration

### Iteration 2+ (differential review)

1. Re-review only the dimensions that were WARN/BLOCK last time
   - Ask `claude-skills:plan-reviewer` with the target dimensions stated explicitly. When it does not accept a partial dimension list,
     request a full review and use **only the results for the dimensions that were WARN/BLOCK last time** for the verdict
   - Pass the same target file explicitly in the arguments (do not rely on automatic selection)
   - Skip the dimensions that were PASS (this holds down context consumption)
2. Every result PASS → finish
3. Still WARN/BLOCK → improve and continue

### Termination conditions

- Every dimension PASS
- The maximum iteration count is reached → list the remaining WARN/BLOCK findings and finish

### Completion report

Present the following to the user:

- The number of iterations executed (one review counts as one iteration, regardless of whether a fix followed, including a final review-only round)
- A summary of the items improved in each iteration
- The final score and verdict for each dimension
- A list of any WARN/BLOCK findings that remain
