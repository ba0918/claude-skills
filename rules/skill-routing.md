# Skill Routing — Recall Rules for Skill Invocation

The main cause of missed skill firing is not the discriminability of descriptions but recall (salience).
In the trigger-eval measurement (2026-07-03 run), a sonnet selector given the description list answered all 138 cases correctly, yet in a real session an indirect investigation request ("I just want to know why it fails") did not fire investigate and the model answered directly.
Across 30 days of real sessions, spontaneous firing from natural-language instructions occurred in only 11 of 68 prompts.

In other words, the more naturally an instruction can be answered as plain conversation, the more likely skill matching itself never runs.
This rule is a routing table that compensates for that recall gap from the always-resident context side.

## Rules

**Before responding to the user's instruction directly with conversation or work**, check once whether it matches one of the patterns below,
and if it matches, consider invoking the corresponding skill (deciding not to invoke is acceptable, but do not skip the check):

| How the user phrases it (examples of indirect expressions) | Skill to consider |
|---|---|
| "I want to know why X happens", "just find the cause", "investigate it, no fix needed", "I want to see the impact scope" | investigate |
| "What do you think about X?", "this feature might be handy", "I have an idea" (a design/feature consultation, not chit-chat) | brainstorm |
| "I'm stuck", "I can't come up with a good approach", "I want a change of perspective" | problem-solving |
| "commit this", "commit + push", "save the changes" | commit |
| "turn this into a document", "document these findings" | doc-write |
| "let's make a plan and proceed", "draw up the implementation steps" | plan |
| "fix this bug" (asked to fix it with the root cause not yet identified) | systematic-debugging |
| "check whether the same problem exists elsewhere and fix it too", "roll the fix out horizontally" | sweep-fix |
| "clean up / refactor without changing behavior" | refactor |

- For cases not in the table, judge as usual
- If the user explicitly names a skill or slash command, always follow it
- If the corresponding skill is not available in the environment, skip the check and respond normally

## Operational Notes

- `rules/` is not auto-deployed by the Plugin format. To use it, copy it to `~/.claude/rules/`,
  or paste the summary table into the project's or the user's `AGENTS.md`
- Add table rows only on the basis of indirect expressions that actually failed to fire in measurement (do not bloat the table speculatively; the table itself consumes context budget)
- Run regression checks of firing accuracy with the trigger-eval skill
