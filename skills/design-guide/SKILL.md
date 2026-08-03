---
name: design-guide
description: Create a project's DESIGN.md (its design system definition) through interactive discovery, and generate mockups based on it. It structures a vague design impression through concrete binary choices, building the foundation for consistent UI generation that does not read as AI-made. Use when the user says "design guide", "create DESIGN.md", "design tokens", or "mockup".
---

# Design Guide

Build a project's DESIGN.md through interactive discovery.
It follows the DESIGN.md format proposed by Google Stitch, producing the design-system definition an AI coding agent needs in order to generate consistent UI.

**The core idea**: design intent is hard to put into words. Instead of open questions, narrow the direction down with **two-to-four concrete choices** and give the user's vague mental image a structure.

## Workflow Selection

The leading keyword of $ARGUMENTS selects the workflow. Read only the workflow file you are
about to execute, in full, before acting:

- `update` → **Update Workflow**: [references/update-workflow.md](references/update-workflow.md) — its Step 4 runs the matching phases of [references/discovery-phases.md](references/discovery-phases.md)
- `mockup` → **Mockup Workflow**: [references/mockup-workflow.md](references/mockup-workflow.md)
- (none, or a free-text description) → **Session Workflow**: [references/session-workflow.md](references/session-workflow.md) — its Phases 1-5 live in [references/discovery-phases.md](references/discovery-phases.md)

## Hard constraint (all workflows)

During discovery (Session and Update), never create or edit any file. DESIGN.md is written
only in Session Phase 6 / Update Step 5, after the user approves the content. Skipping the
questions to "just write the file" is the exact failure this skill exists to prevent — the
workflow files carry the full constraint tables and red flags; this line is the floor, not
the whole rule.

## Completion report (all workflows)

Every workflow's final message conforms to the
[human-readable summary contract](../shared/references/human-readable-summary.md) and begins
with the fixed label `📝 In short:`.

## References

- **Template:** [references/design-md-template.md](references/design-md-template.md)
- **Question bank:** [references/discovery-questions.md](references/discovery-questions.md)
- **Anti-patterns:** [references/anti-patterns.md](references/anti-patterns.md)

## Notes

- DESIGN.md is a "design-system translation layer" for AI agents, not a replacement for a complete design system
- Keep the generated DESIGN.md under version control in Git, and prefer making design changes subject to PR review
- When used alongside the frontend-design skill, the tokens in DESIGN.md win (a project-specific definition outranks frontend-design's general guidelines)
