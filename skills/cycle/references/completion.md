# Cycle Completion (Phase 5 detail)

Read this file when Phase 5 begins, and execute the five steps in order. Run each step
independently; on failure, record the step in `phase5_failures` and continue (same
partial-failure tolerance as Phase 2).

## Step 1: Generate the result file

Path: `.agents/artifacts/plans/results/{plan_basename}_result.md` (`{plan_basename}` =
plan filename without `.md`; `mkdir -p` the directory if missing). Generating it here —
not in Phase 2 — captures all commits including Phase 3 fix iterations.

- **Inner satellite mode:** do not create this file; defer result-artifact composition
  to the outer orchestrator and retain the final-display facts for the completion
  relay.
- **On failure**: append `"result file generation"` to `phase5_failures`; the final
  display's `Result:` line must then show `⚠️ generation failed — no result file`,
  never a path to a file that was not written.

Content:

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

## Step 2: Mark status.md as completed

Inner satellite mode: skip all of Step 2 — skip singleton status and
session-history composition; the outer orchestrator owns singleton writes.

- **Step 2a: Pre-check**: read `.agents/artifacts/status.md`. If the Current Session
  heading is absent or the table is unparsable (including old-format files without
  session management), append `"status.md update"` to `phase5_failures` and move on —
  **a failure, not a guard**; do not repair or rewrite old formats.
- **Step 2b: Guard**: if the Current Session body starts with `_No active session`, it
  is already archived — do nothing and move on (not a failure). **Decide on that body
  text alone, never on the `Phase` field** — `🟢 Complete` is what Phase 1 writes on a
  session that is still listed, i.e. not yet archived.
- **Step 2c: Normal processing**: follow **Case 2 (In Progress → Completed)** of
  [status-update-guide.md](../../plan/references/status-update-guide.md) — archive to
  session-history.md, clear the Session History section, clear Current Session. Case 2
  applies to any still-listed session regardless of its Phase label. On failure,
  append `"status.md update"` to `phase5_failures` and move on.
- **Record which branch Step 2 took** (`archived` / `already archived` / `failed`) for
  the final display — a silent skip is otherwise indistinguishable from a silent
  success.

## Step 3: Verify plan file status

The plan's own **Status:** header must be marked completed (implement normally does
this; update it here if stale) — otherwise the next cycle's Phase 0 would reselect
this plan. On failure, append `"plan status update"` to `phase5_failures` and move on;
this failure makes completion incomplete even if the implementation and reviews
passed.

## Step 4: Auto-close the issue

Only if Step 3 succeeded — closing an issue while the plan remains re-selectable
creates an inconsistent state. If Step 3 failed, skip and record
`"issue close skipped: plan status incomplete"` in `phase5_failures`.

- **Inner satellite mode:** must not auto-close a linked issue. Return its slug to
  the outer orchestrator, which may close it only after merge, post-merge
  verification, and artifact publication all succeed.
- If the plan has an `**Issue:**` line: extract the slug and execute the skill
  `claude-skills:issue` with `close {slug}`. If close fails, display a warning only —
  the cycle still counts as a success (do not roll back the implementation).
  **Record the close outcome and include it in the final display.**

## Step 5: Final display

Show `CYCLE COMPLETE` only when Step 3 succeeded. If it failed, replace the heading
with `CYCLE INCOMPLETE: plan status update failed`, add
`Recovery: update the plan Status, then re-run completion`, and do not claim the plan
or cycle completed.

```
══════════════════════════════════════
CYCLE COMPLETE
Feature: {feature_name}
Implement: {steps_done}/{steps_total} steps
Review: {PASS / WARN ({N} findings) / fix loop: {N} iterations → {verdict}}
Final Gate: {PASS / WARN}
Commits: {N} (all commits across the cycle)
Result: {result_file_path / ⚠️ generation failed — no result file}
Session: {archived → session-history.md / already archived / ⚠️ update failed}
Issue: {closed ✅ / ⚠️ close failed: {slug} — manual close required / (none)}
{when phase2_failures or phase5_failures is not empty:}
⚠️ Partial failures: {all failures, comma-separated}
──────────────────────────────────────
💡 Next: run /claude-skills:doc-check branch — the trunk's alignment station
   (write implementation-induced changes back to docs) — before commit / PR.
💡 Need tweaks? Use /iterate for quick fixes and polish.
══════════════════════════════════════
```

In inner satellite mode, the completion relay must return the implementation counts,
commit list, plan status, review verdict and findings summary, final gate verdict,
linked issue slug, and phase failures — non-authoritative facts for the outer
orchestrator to compose the result artifact and decide issue closure after harvest,
merge, verification, and publication. Show `Result: deferred to outer orchestrator`,
`Session: deferred to outer orchestrator`, and
`Issue: deferred to outer orchestrator: {slug | none}`.
