# Plan Workflow

1. Read `.agents/artifacts/ideas/idea-status.md`; if absent, reply "No ideas yet." and stop.
2. Have the user select the target idea. Run the explicit selection step even when only one entry exists (present the table; never silently proceed). When interaction is impossible and exactly one entry exists, present the table, proceed with that entry, and state the assumption; with multiple entries, stop and ask for a selection.
3. Read the idea file.
   - **Title source**: the link text in the first column of idea-status.md (= the memo's `#` heading title; Wrap saves it and rebuild-index regenerates with the same value).
   - **Summary source**: the memo's `## Summary` section body.
   - **Exit contract check**: if the idea file contains a `## Exit Contract` section:
     - If status is `BLOCKED`: reply "This idea has unresolved blocking items. Run `/claude-skills:brainstorm-resume` to resolve them before creating a plan." and stop.
     - If status is `CONVERGED`: use the agreements and acceptance criteria as the plan seed (richer than title + summary alone).
     - If the `**Exit Status:**` line is missing or carries any other value: treat it as
       BLOCKED (safe side) — a half-written exit contract usually means an interrupted
       wrap. Reply that the exit contract is incomplete and suggest
       `/claude-skills:brainstorm-resume`, then stop.
   - If no exit contract section: proceed with title + summary as before (backward compatible).
4. Run the `claude-skills:plan-create` skill in **caller-supplied mode** (its contract
   lives in the plan skill's "Caller-supplied mode" section):
   - Generate the plan path yourself:
     `output_path = .agents/artifacts/plans/{new_timestamp}_{kebab-title}.md`
     (`new_timestamp` is `date +%Y%m%d%H%M%S` at this step; kebab-title is a short ASCII
     translation of the idea title). Keep this path for Steps 4.5 and 8 — because the
     caller supplies it, the path is exact, never a guess at plan-create's own naming.
   - Pass **both** parameters: `output_path` (above) and `skip_status: true`.
     `skip_status` keeps plan-create away from status.md / session-history.md, so a
     previous session's unfinished state never interrupts this workflow.
   - Argument (the plan content seed):
     - **With exit contract**: `{Title}: {Agreements summary} — Acceptance criteria: {criteria list}`
     - **Without exit contract**: `{Title}: {Summary from idea file}`
   - Append the source declaration so the source-material soft gate detects the origin
     without session context: `Source: brainstorm idea {slug} (exit contract {CONVERGED | none})`.
     The plan records the **post-archive** memo path
     `.agents/artifacts/ideas/archives/{slug}.md` (Step 6 moves the memo there).
   - In caller-supplied mode plan-create emits no completion display of its own —
     Step 8 is this workflow's single completion message.
4.5. Optional cycle execution:
   - If `--cycle` is present in the original `$ARGUMENTS`: remove the flag, then run `claude-skills:cycle` with the created plan file path as the argument. Skip Step 7 entirely (cycle produces its own completion log).
   - Otherwise continue to Step 5.
5. Route agreements (only when exit contract is present):
   - Display the routing table from the exit contract as guidance for the human:
     ```
     ## Routing (from exit contract)
     | Destination | Items | Action |
     |-------------|-------|--------|
     {routing table from exit contract}
     ```
   - Routing is guidance, not automatic execution. The human decides which destinations to pursue.
6. Archive — run only after confirming the plan file from Step 4 exists (move the file **before** updating its Status):
   - Ensure `.agents/artifacts/ideas/archives/` exists (`mkdir -p`).
   - Move `.agents/artifacts/ideas/{slug}.md` to `.agents/artifacts/ideas/archives/{slug}.md`.
   - Delete the row from idea-status.md and set **Last Updated** to the newest
     remaining entry's Created timestamp (the deterministic value rebuild-index
     produces; with no entries left, leave it empty).
7. In the archived file, change the status to `**Status:** 📋 Planned`.
8. Show the completion message (`{plan path}` is the path kept from Step 4; `{slug}` is the idea memo's filename stem including its timestamp prefix):
   ```
   ✅ Created a plan from the idea!
   📄 Plan: {plan path}
   📦 Archived: .agents/artifacts/ideas/archives/{slug}.md

   ## Next Steps
   1. Run the cycle with `/claude-skills:cycle`
   ```
