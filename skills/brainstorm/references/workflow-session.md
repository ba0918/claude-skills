# Session Workflow

## Constraints

Do not edit, create, or overwrite any file (including notebooks) during the session. Do not generate code, propose implementation work, or start implementation — never say "let me implement this" (explaining concepts in pseudocode is fine).

Allowed: read-only codebase investigation (file reads, pattern search, file listing, read-only shell commands such as `git log`, `git diff`, `ls`), Codex second opinions via a subagent, and dialogue with the user.

Dialogue is natural language only — do not present a choice UI (a pick-one option list, with or without a "recommended" marker) during the session. A recommended-choice list makes the user pick without thinking, reproducing exactly the ritual that requirements definition exists to prevent. Ask open questions — why? what would be enough? what breaks without it? — and let the user answer in their own words.

## Flow

1. Take the theme from $ARGUMENTS (ask the user if absent).
2. Initialize `codex_available = true` and `stuck_hint_shown = false`. Do not pre-create any state files.
3. Enter the sparring loop:
   a. Receive the user's message.
   b. **Stuck detection** (only while `stuck_hint_shown == false`): if the message contains any of these keywords (substring match, case-insensitive) —
      - Japanese: 「行き詰ま」「わからない」「どうすれば」「手詰まり」「煮詰ま」「堂々巡り」「進まない」
      - English: "stuck", "no idea", "don't know", "dead end", "going in circles"

      then place the following block at the very top of the response generated in step d, and set `stuck_hint_shown = true`. Later keyword hits are suppressed. Fixed output order for the whole response: hint block (if any) → Codex-unavailable notice (if any) → response body → `💡 Codex's perspective:` section (if any).
      ```
      💡 When you are stuck, try the thinking tools in `/claude-skills:problem-solving`:
      - `simplify` — find the "everything is a special case of X"
      - `invert` — flip the premise
      - `collide` — collide unrelated concepts
      - `scale` — test at an extreme scale
      - `pattern` — learn from a pattern in another domain
      ```
   c. **Codex second opinion** (only while `codex_available == true`): dispatch the Codex subagent with the theme, the user's message, and a 1–3 sentence summary of the discussion so far (use the literal string `(first turn, no history)` on the first turn). Prompt: "For the sparring theme and user message below, offer a different perspective, a counterargument, an overlooked angle, or a related idea. Theme: {theme}. User message: {user_message}. Discussion so far: {summary}". Pass conversation text only — never file-read results.
      - On failure (call errors out, times out, Codex is unavailable in the environment, or the response is empty / malformed): display `⚠️ Codex unavailable — proceeding without a second opinion` once in the step-d response (positioned per the fixed output order above), set `codex_available = false`, and skip Codex on later turns. Do not fabricate a Codex opinion.
   d. Generate the response (integrating Codex's opinion when present): question, probe, push back, offer alternative angles. When a Codex opinion exists, append at the end:
      ```
      💡 Codex's perspective:
      {summary of Codex's opinion}
      ```
   e. Investigate the codebase read-only as needed.
   f. Ask the user for the next input.
   g. **Wrap gate with self-review**: When the user says "wrap" / 「まとめて」 / 「終わり」 etc., run the pre-wrap self-review (see below).
      - **Clean**: exit the loop.
      - **Issues found**: present them and stay in the loop — the findings become discussion points for the next turn. On the next wrap, re-run the review (do not skip — new issues may have emerged from the discussion).
      - **Force exit**: When the user says "wrap!" / "wrap --force" / 「強制wrap」, exit the loop regardless of outstanding items. List the unresolved review items in the exit message so the Wrap Workflow captures them as Undecided Items with `blocks_plan: true`.
4. On exit, show the pointer to Wrap:
   ```
   {normal exit:}
   Ending the sparring session.
   Run `/claude-skills:brainstorm-wrap` to organize the ideas into a memo.

   {force exit with unresolved items:}
   Ending the sparring session (forced — unresolved review items remain).
   ⚠️ Unresolved:
   - {item 1}
   - {item 2}
   Run `/claude-skills:brainstorm-wrap` to organize the ideas into a memo.
   Unresolved items will be recorded as blocking undecided items in the exit contract.
   ```

**Note**: Response generation and subagent calls cannot run concurrently — call Codex first, then generate the response.

Shared contract details: [../../shared/references/codex-integration.md](../../shared/references/codex-integration.md)

## Sparring behavior

- Probe with questions (Why? What if? How about?); state concerns frankly; propose alternative approaches; periodically summarize the discussion.
- Back feasibility claims with read-only codebase investigation.
- When the discussion starts converging on a specific technology, check the gravitational pull — ask "if you did not use that technology, what would you be trying to solve?" or "can you state the problem without naming the technology?" as questions, not blocks.

## Pre-wrap Self-Review

A lightweight inline review of the accumulated discussion, run every time the user signals wrap intent. No subagent — the agent reviews the conversation in its own context. Re-running on each wrap is intentional: post-review discussion may introduce new issues or resolve existing ones.

### Checklist

Scan the discussion for:

1. **Placeholders** — unresolved "TBD", "TODO", "後で決める", "later", or explicitly deferred decisions that would block downstream work (plan creation or implementation).
2. **Internal contradictions** — agreements or positions taken during the session that conflict with each other, or with codebase evidence found during the session.
3. **Scope deviation** — significant drift from the original theme without explicit acknowledgment from the user.
4. **Ambiguity** — vague terms, unmeasurable conditions, or underspecified behaviors in candidate agreements (e.g., "high performance" without a metric, "simple API" without constraints).
5. **Implicit decisions** — decision categories the implementer would otherwise settle silently. For themes that build or change something, sweep at minimum: persistence of any new state (where it lives, in what form), data lifetime and migration, performance targets for the main operations, and external I/O per operation (network round trips, process spawns). A relevant category counts as resolved only when it has landed as an agreement, an explicit undecided item, or an explicit user judgment that it does not apply — this review having mentioned it on an earlier wrap does not count as landing. Until then it stays an issue, even if nothing said so far is wrong.

### Output format

Place the review block at the top of the response, before any other content:

```
🔍 Pre-wrap review:
- {⚠️ description | ✅ No issues} per category (omit clean categories to keep it short)

{if issues found:}
{N} items to consider before wrapping. Discuss to resolve, or say "wrap!" to force exit with these items recorded as blocking undecided items.
{if all clean:}
✅ All clear — proceeding to wrap.
```

When all categories are clean, skip the per-category listing and output only the "All clear" line, then exit the loop immediately.

### Force exit contract

When the user forces exit via "wrap!" / "wrap --force" / 「強制wrap」, unresolved review items are carried into the Wrap Workflow and must become Undecided Items with `blocks_plan: true` in the exit contract. This ensures the exit contract status is `BLOCKED`, preventing premature plan creation from incomplete agreements.
