---
name: using-workflow
description: The runtime funnel and routing discipline of the trunk workflow — one rule that makes brainstorm the default entry for any request to build or change something, plus the enumerated exception categories (with their representative skills) that enter elsewhere. Small on purpose so it stays resident; the distributed plugin injects it at session start. Use when deciding which skill a new request should enter through, or when the user asks "where does this work start", 「どのスキルから始める？」「幹のどこから入る？」.
---

# Using the Trunk Workflow

Run this routing check before every response — no exceptions. The requests that
read most like plain conversation are exactly the ones that skip routing, so a
conversational shape is a reason to check, not an exemption.

The trunk: utterance / GitHub issue → brainstorm → plan → implement → review →
alignment (write back to docs/spec) → PR. Routing needs nothing beyond this
file — load no other material for it.

## The One Rule

A request to build or change something enters through **brainstorm** — idea →
requirements → specification, hammered out in dialogue — before any plan or
implementation. GitHub issues take no separate route: a well-groomed issue
simply converges in one round. When in doubt, propose brainstorm.

## Exception Categories (enter elsewhere)

1. **Trunk continuation** — the work already carries its source material: an
   in-flight plan, converged brainstorm agreements, a written spec, or a
   reproduced bug. Enter at the matching station — plan / cycle / iterate for
   planned work, doc-check for write-back to docs, systematic-debugging for a
   reproduced bug. Do not loop back to brainstorm. A bare "implement it"
   (「実装して」) with an agreed plan boards **cycle**, not hand
   implementation. Side lines (ledger, spec-verify, and kin) are matched by
   their own descriptions and never fall through to the brainstorm default.
2. **Terminal and session logistics** — committing (commit), releasing, PR
   mechanics, session handoff (handoff), status or list lookups. These end or
   relay work, never start it. Releasing and PR mechanics have no owning
   skill — they are pull-type termini done with the environment's own means.
3. **Read-only work** — investigation (investigate), debugging diagnosis
   (systematic-debugging), reviews and audits (the review-family skills),
   thinking support when stuck (problem-solving). They produce findings; the
   moment a finding turns into build-or-change work, it enters through
   brainstorm.

Pick the specific skill within a category by its description. A request
matching no category is not an exception — it goes to brainstorm.
