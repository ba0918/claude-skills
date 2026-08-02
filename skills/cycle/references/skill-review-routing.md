# The skill-reviewer path in Phase 3

Read this when Phase 3 Step 0.5 routed all or part of the diff to skill-reviewer. It replaces Steps 1–3 for the
skill-artifact files; on a mixed diff, the general files still go through Steps 1–3 unchanged, and the same
problem is never counted in both reviews — attribute it to the reviewer that owns the file.

## Step 1s: Review

Launch a review subagent (high-performance model):

- Prompt: "Execute the skill `claude-skills:skill-reviewer`. Review these skill-artifact files changed by this
  cycle: {skill_artifact_file_list}. Use `git diff {cycle_start_sha}..HEAD -- {skill_artifact_file_list}` as the
  diff. Emit the two-channel document of its output contract and confirm it passes
  `skills/skill-reviewer/scripts/validate_review_output.py`. **Before sending your completion report**, write that
  validated document plus your findings to `.agents/runtime/delegation/{run_id}_{role}.md`. The report is merely a
  notification that the file was written."
- `{role}` = `post-review-skill` initially; `post-review-skill-{N}` for the re-review after fix iteration N. Follow
  the delegation result relay.

## Step 2s: Verdict branch

skill-reviewer is a diagnostic instrument, not a gate, so its two channels carry different consumer rights. This
branch governs the skill-reviewer result only — the plan-reviewer branches in the main body stay as they are.

| Channel and verdict | Action |
|---------------------|--------|
| `diagnostics` (WARN / OPPORTUNITY / INFO) | Record in the Phase 5 result. It never triggers a fix, a re-review, or a stop — headless included |
| `control_candidates` WARN | Record and continue. Auto-fix only findings carrying `fix_action: AUTO_FIX`, at most one iteration, reusing Step 2b's mechanics with `{role}` = `fix-skill-warn`. An unresolved WARN here is **not** a headless stop condition |
| `control_candidates` BLOCK | Enter the Step 3 fix loop with the payload restricted to those findings, re-reviewing with `{role}` = `post-review-skill-{N}` |
| No `control_candidates` BLOCK | Proceed — to Phase 4, or to the plan-reviewer branch when the diff is mixed |

Step 3 mechanics on this path: skip Step 3(a)'s severity/dimension extraction — a `control_candidates` entry
carries no `severity` field and no dimension verdicts (the output schema rejects both), so the fix payload is
every `control_candidates` BLOCK finding as-is, sanitized per fix-delegation. Steps 3(b)–(c) apply unchanged.
Step 3(d)'s re-review re-runs **Step 1s above** — not the main body's Step 1, which would swap the reviewer back
to plan-reviewer — with `{role}` = `post-review-skill-{N}`. The 2-iteration cap is shared.

Why the WARN policy differs from the plan-reviewer path: severity and whether a fix may be automated are
orthogonal axes ([fix-action-taxonomy.md](../../shared/references/fix-action-taxonomy.md)), and no contract says
"WARN implies AUTO_FIX". The main body's blanket WARN auto-fix is a cycle policy, so setting a different consumer
policy per path contradicts nothing. Routing diagnostic output into that blanket policy is precisely how a
diagnostic instrument turns back into a gate.

If the delegate reports that its output failed the validator, treat the review as not delivered: redelegate once,
then continue with whatever findings arrived and record the gap. A malformed diagnostic never escalates into a
stop.
