# Wrap Workflow

## Precondition

If the current conversation contains no sparring session (bare `/claude-skills:brainstorm-wrap`), reply "No sparring session found. Run `/claude-skills:brainstorm {theme}` first to hold one." and stop.

## Steps

1. Organize the sparring content from the current conversation.
2. Confirm the title and summary with the user. When interaction is impossible, derive them from the conversation and state that assumption in the completion message.
3. **Exit contract judgment**: Determine whether the session produced actionable agreements (decisions with rationale, acceptance criteria, codebase evidence) OR the session ended with a force exit carrying unresolved review items. If either condition is true, generate the exit contract sections in the idea memo (Step 5). If the session was purely exploratory with no convergence and no force exit, skip the exit contract sections — the memo remains a plain idea memo. When force exit unresolved items are present, record them as Undecided Items with `blocks_plan: true` — this is mandatory even if no agreements were reached.
4. Ensure `.agents/artifacts/ideas/` exists (`mkdir -p`).
5. Generate the slug: `yyyymmddhhmmss_{kebab-title}` (`date +%Y%m%d%H%M%S`; kebab-title is a short ASCII translation of the title). If `.agents/artifacts/ideas/{slug}.md` already exists, re-run `date` for a fresh timestamp — overwriting an existing memo is reserved for Wrap after Resume.
6. Create the memo at `.agents/artifacts/ideas/{slug}.md` from [idea-template.md](idea-template.md). When the exit contract judgment (Step 3) is positive, also populate the exit contract sections per [exit-contract-template.md](exit-contract-template.md):
   - **Agreements**: each decision with rationale and destination (plan / GitHub issue / docs/spec; ledger only when a decision record is wanted)
   - **Undecided Items**: open questions with `blocks_plan` flag
   - **Acceptance Criteria**: observable behaviors/constraints with verifiability flag
   - **Codebase Evidence**: file paths and findings that grounded the discussion
   - **Routing**: where each piece goes next (plan / GitHub issue / docs/spec / docs; ledger and clauses as side lines)
   - **Status**: `CONVERGED` if no blocking undecided items remain; `BLOCKED` otherwise
7. **Spec generation** (only when exit contract status is `CONVERGED`):
   Follow the procedure in [spec-generation.md](spec-generation.md) to generate a human-readable spec draft in the consumer project's `docs/spec/` directory. The agent autonomously selects the target domain file (match existing or create new), presents the draft with matching rationale to the human, and writes only after approval. After writing, record the spec path in the idea memo's exit contract Routing table (destination `Spec`, action `Generated at {path}`) so that `brainstorm-plan` can pass it to `plan-create` without re-scanning. In headless mode (interaction impossible), save the draft to `.agents/artifacts/ideas/{slug}_spec_draft.md` instead of writing to `docs/spec/` — the human reviews and moves it later. Skip this step entirely when the exit contract is `BLOCKED` or absent.
8. Update `.agents/artifacts/ideas/idea-status.md` (create with this header if absent):
   ```markdown
   # Idea Status

   **Last Updated:** YYYY-MM-DD HH:MM:SS

   | Idea | Tags | Created | Status | Summary |
   |------|------|---------|--------|---------|
   ```
9. Append a row. The link text is the memo's `#` heading title (the human-readable title confirmed in Step 2) — idea-status.md is a derived index and rebuild-index regenerates each row from the memo's `#` heading, so a kebab slug here would flip on every rebuild:
   ```
   | [{the idea's # heading title}]({slug}.md) | `{tags}` | {YYYY-MM-DD HH:MM:SS} | {status_icon} | {summary} |
   ```
   Status icon: `💡 Idea` for plain memos, `✅ Converged` for CONVERGED exit contracts, `🚧 Blocked` for BLOCKED exit contracts.
10. Update **Last Updated** to now.
11. Show the completion message, opening with a summary-first block per the [human-readable summary contract](../../shared/references/human-readable-summary.md): state the core of the saved idea in 1–2 plain lines and name the open questions left by the session (or "none"). No verbatim replay or exhaustive lists:
   ```
   📝 In short: {what the saved idea amounts to, in 1-2 plain lines that reach
      someone who has not read the memo}. Undecided: {the remaining points, or "none"}

   ✅ Idea saved!
   📄 File: .agents/artifacts/ideas/{slug}.md
   📋 Index: .agents/artifacts/ideas/idea-status.md
   {when spec was generated:}
   📄 Spec: docs/spec/{domain}.md
   {when exit contract is CONVERGED:}
   📋 Exit contract: CONVERGED — ready for routing
      Next: `/claude-skills:brainstorm-plan` to create a plan from the agreements
      Or route agreements to GitHub issues (grouped per stage) / docs — or the side lines (ledger / clauses)
   {when exit contract is BLOCKED:}
   🚧 Exit contract: BLOCKED — undecided items block plan creation
      Resume with `/claude-skills:brainstorm-resume` to resolve them
   {when no exit contract:}
   💡 No actionable agreements yet — resume or start a new session when ready
   ```

## Wrap after Resume

When Wrap runs after Resume, it **updates the existing memo in place** (same slug, no new file). The idea-status.md row stays as-is; only **Last Updated** changes.

## Security

If the sparring content contains sensitive information, confirm with the user before writing it to the memo. When interaction is impossible and sensitive information is detected, do not write the memo — report that explicit confirmation is required. Keep secret values (tokens, keys, personal data) out of the summary block as well — omit or replace with a category name per the contract's degradation rule.
