---
name: using-workflow
description: The runtime funnel and routing discipline of the trunk workflow — one rule that makes brainstorm the default entry for any request to build or change something, plus the enumerated exception categories (with their representative skills) that enter elsewhere. Small on purpose so it stays resident; the distributed plugin injects it at session start. Use when deciding which skill a new request should enter through, or when the user asks "where does this work start", 「どのスキルから始める？」「幹のどこから入る？」.
---

# Using the Trunk Workflow

The trunk: utterance / GitHub issue → brainstorm → plan → implement → review →
alignment (write back to docs/spec) → PR. The canonical diagram and the funnel
principle live in [skill-authoring](../shared/references/skill-authoring.md); this
skill carries only the runtime routing rule.

## The Routing Check

The more naturally an instruction can be answered as plain conversation, the more
likely skill matching never runs (measured over real sessions: spontaneous firing in
11 of 68 prompts). Before responding to an instruction directly with conversation or
work, run the routing below once.

## The One Rule

A request to build or change something enters through **brainstorm** — idea →
requirements → specification, hammered out in dialogue — before any plan or
implementation. GitHub issues take no separate route: a well-groomed issue simply
converges in one round. When in doubt, propose brainstorm first.

## Exception Categories (enter elsewhere)

1. **Trunk continuation** — the work already carries its source material: an
   in-flight plan, converged brainstorm agreements, a written spec, or a reproduced
   bug. Enter at the matching station — plan / cycle / iterate for planned work,
   systematic-debugging for a reproduced bug — do not loop back to brainstorm.
2. **Terminal and session logistics** — committing (commit), releasing, PR
   mechanics, session handoff (handoff), status or list lookups. These end or relay
   work; they never start it.
3. **Read-only work** — investigation (investigate), debugging diagnosis
   (systematic-debugging), reviews and audits (the review-family skills), thinking
   support when stuck (problem-solving). They produce findings; the moment a finding
   turns into build-or-change work, that work enters through brainstorm.

Within a category, pick the specific skill by its description. A request matching no
category is not an exception — it goes to brainstorm.

## Resident Loading

This file is deliberately small so it can stay resident. The distributed plugin
injects its body (frontmatter excluded) at session start — no manual setup for
plugin users. Without the plugin, wire an equivalent read-only injection (no
state-mutating commands); the repository README shows a configuration example.
