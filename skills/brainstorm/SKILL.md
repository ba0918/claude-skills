---
name: brainstorm
description: The default entry of the trunk workflow — a heavy phase that drives an idea through requirements definition into a specification by dialogue, before any plan or implementation. Runs a file-edit-free sparring session (open natural-language questions only, no choice UI), then wraps into an exit contract — agreements, undecided items, acceptance criteria — routed to plan, GitHub issue, or docs/spec. Use when the user says "brainstorm", "spar on an idea", "I have an idea", "define the requirements", "nail down the spec", 「壁打ち」「要件定義」「要件を詰めたい」「仕様を決めたい」, proposes a new feature or design change, or starts work from a GitHub issue (issues also enter through brainstorm).
---

# Brainstorm

Artifact paths follow the [Artifact Store consumer contract](../shared/references/artifact-paths.md). Resolve and validate the store before reading or writing artifacts.

The default entry of the trunk workflow — idea → requirements → specification, hammered out in dialogue. Discussion only during the session — the agent never drifts into implementation. On wrap, the session outcomes are structured into an exit contract that routes agreements to their proper destinations (plan, GitHub issue, docs/spec — with ledger and clauses as side lines for decision records and machine-verifiable contracts).

## Workflow Selection

Decide the workflow from the leading keyword of $ARGUMENTS, then read **only** the matching workflow file and follow it:

- `wrap` → [references/workflow-wrap.md](references/workflow-wrap.md) (organize & summarize)
- `list` → [references/workflow-list.md](references/workflow-list.md)
- `plan` → [references/workflow-plan.md](references/workflow-plan.md) (convert to plan)
- `resume` → [references/workflow-resume.md](references/workflow-resume.md) (restart from an existing memo)
- (none or a theme string) → [references/workflow-session.md](references/workflow-session.md)

## File Structure (generated in the project using this skill)

```
.agents/artifacts/ideas/
  idea-status.md             - index file
  yyyymmddhhmmss_{slug}.md   - individual idea memos
  archives/                  - store for planned / dropped ideas
```

## Status Types

| Status | Meaning |
|--------|---------|
| 💡 Idea | Sparred, no actionable agreements yet |
| ✅ Converged | Exit contract generated, ready for plan creation |
| 🚧 Blocked | Exit contract has unresolved blocking items |
| 📋 Planned | Converted to a plan |
| 🗑️ Dropped | Abandoned |

## Templates

- **Idea memo:** [references/idea-template.md](references/idea-template.md)
- **Exit contract:** [references/exit-contract-template.md](references/exit-contract-template.md)

## Notes

- idea-status.md is the index — reading it alone gives the full picture.
- Plan / Drop both archive the memo (move to archives/ + delete the table row).
- Keep sensitive information out of sparring memos.
- The exit contract is optional — exploratory sessions that do not converge on agreements produce a plain idea memo.
- Specification and design changes require brainstorm consensus. Reviews that find spec gaps escalate back to brainstorm, not to the plan or implementation directly.
