# Plan Workflow

1. Read `.agents/artifacts/ideas/idea-status.md`; if absent, reply "No ideas yet." and stop.
2. Have the user select the target idea. Run the explicit selection step even when only one entry exists (present the table; never silently proceed). When interaction is impossible and exactly one entry exists, present the table, proceed with that entry, and state the assumption; with multiple entries, stop and ask for a selection.
3. Read the idea file.
   - **Title source**: the link text in the first column of idea-status.md (= the memo's `#` heading title; Wrap saves it and rebuild-index regenerates with the same value).
   - **Summary source**: the memo's `## Summary` section body.
   - **Exit contract check**: if the idea file contains a `## Exit Contract` section:
     - If status is `BLOCKED`: reply "This idea has unresolved blocking items. Run `/claude-skills:brainstorm-resume` to resolve them before creating a plan." and stop.
     - If status is `CONVERGED`: use the agreements and acceptance criteria as the plan seed (richer than title + summary alone).
   - If no exit contract section: proceed with title + summary as before (backward compatible).
4. Run the `claude-skills:plan-create` skill:
   - **With exit contract**: pass `{Title}: {Agreements summary} — Acceptance criteria: {criteria list}` as the argument.
   - **Without exit contract**: pass `{Title}: {Summary from idea file}` as the argument.
   - plan-create creates `.agents/artifacts/plans/{new_timestamp}_{kebab-title}.md` (`new_timestamp` is `date +%Y%m%d%H%M%S` at plan-create launch). Keep this path for Steps 4.5 and 7.
   - Suppress plan-create's own completion message — Step 7 is this workflow's single completion message.
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
   - Delete the row from idea-status.md and update `Last Updated` to today.
7. In the archived file, change the status to `**Status:** 📋 Planned`.
8. Show the completion message (`{plan path}` is the path kept from Step 4; `{slug}` is the idea memo's filename stem including its timestamp prefix):
   ```
   ✅ Created a plan from the idea!
   📄 Plan: {plan path}
   📦 Archived: .agents/artifacts/ideas/archives/{slug}.md

   ## Next Steps
   1. Run the cycle with `/claude-skills:cycle`
   ```
