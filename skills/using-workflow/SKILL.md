---
name: using-workflow
description: The runtime funnel of the trunk workflow — one routing rule that makes brainstorm the default entry for any request to build or change something, plus the enumerated exception categories that enter elsewhere. Small on purpose so it can be loaded residently at session start. Use when deciding which skill a new request should enter through, or when the user asks "where does this work start", 「どのスキルから始める？」「幹のどこから入る？」.
---

# Using the Trunk Workflow

The trunk: utterance / GitHub issue → brainstorm → plan → implement → review →
alignment (write back to docs/spec) → PR. The canonical diagram and the funnel
principle live in [skill-authoring](../shared/references/skill-authoring.md); this
skill carries only the runtime routing rule.

## The One Rule

A request to build or change something enters through **brainstorm** — idea →
requirements → specification, hammered out in dialogue — before any plan or
implementation. GitHub issues take no separate route: a well-groomed issue simply
converges in one round. When in doubt, propose brainstorm first.

## Exception Categories (enter elsewhere)

1. **Trunk continuation** — the work already carries its source material: an
   in-flight plan, converged brainstorm agreements, a written spec, or a reproduced
   bug. Enter at the matching station (plan / implement / review); do not loop back
   to brainstorm.
2. **Terminal and session logistics** — committing, releasing, PR mechanics, session
   handoff, status or list lookups. These end or relay work; they never start it.
3. **Read-only work** — investigation, debugging diagnosis, reviews, audits. They
   produce findings; the moment a finding turns into build-or-change work, that work
   enters through brainstorm.

A request matching no category is not an exception — it goes to brainstorm.

## Resident Loading

This file is deliberately a few dozen lines so it can stay resident. Environments
with a session-start injection mechanism can emit this file's body at session start
(read-only injection only — no state-mutating commands); the repository README shows
a concrete configuration example.
