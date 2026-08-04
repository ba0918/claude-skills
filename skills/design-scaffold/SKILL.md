---
name: design-scaffold
description: Scaffold a machine-readable design system (tokens.json + tokens.css + component-catalog + lint config) out of DESIGN.md. It converts the DESIGN.md written by design-guide into a mechanically verifiable form. Use when the user says "design scaffold", "scaffold", or "generate the tokens".
---

# Design Scaffold

A skill that generates machine-readable design system files from DESIGN.md.
It converts the "human-readable dictionary of values" produced by design-guide into a **schema-based system that can be verified mechanically**.

**Shared contract:** see [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md).

## Preconditions

1. `DESIGN.md` exists at the project root
   - If it does not, display "DESIGN.md not found. Create it with `/claude-skills:design-guide`." and stop
2. Read DESIGN.md and grasp the structure of every section

## Workflow


The workflow runs in three stages. Each stage ends with its own completion report, and each
report is a legitimate stopping point — finishing a stage and stopping is a normal outcome,
not an aborted run. Select a stage by argument, or with no argument start at Stage A and
confirm continuation at each stage boundary. Read only the stage file you are about to
execute, in full:

| Stage | Argument | Generates | Prerequisite | File |
|---|---|---|---|---|
| A | `tokens` | tokens.json / tokens.css / lint-config.json / (React theme) | DESIGN.md | [references/stage-a-tokens.md](references/stage-a-tokens.md) |
| B | `catalog` | component-catalog.json / (React components) | `.design/tokens.json` (+ `.design/tokens.css` only when generating React/Preact components) | [references/stage-b-catalog.md](references/stage-b-catalog.md) |
| C | `layout` | layout-rules.json / pages/*.json | `.design/tokens.json` + `.design/component-catalog.json` | [references/stage-c-layout.md](references/stage-c-layout.md) |

Stopping after Stage A gives the minimum design-lint needs; after Stage B the
design-generate prerequisites are ready; after Stage C, continue to the Base Design
approval flow. A requested stage whose prerequisite files are missing stops with a message
naming the missing file and the stage that produces it.

## Overwrite Confirmation for an Existing .design/

Applies only when running Stage A. When `.design/tokens.json` already exists:

1. Read the existing `version`
2. Present options to the user and confirm:
   - "Overwrite (increment the version)"
   - "Cancel"
3. On overwrite, increment the patch version of `version`

## Absolute Constraints

- Add no value to tokens.json that is not defined in DESIGN.md
- tokens.json conforms to the schema; fix schema violations before finishing
- CSS custom property names follow the design-system-contract naming rules
- Always include an "Auto-generated, DO NOT EDIT MANUALLY" comment at the top of generated files

## References

- **Token Schema:** [references/tokens-schema.json](references/tokens-schema.json)
- **Catalog Schema:** [references/catalog-schema.json](references/catalog-schema.json)
- **Page Schema:** [references/page-schema.json](references/page-schema.json)
- **Layout Schema:** [references/layout-schema.json](references/layout-schema.json)
- **Rubric Schema:** [references/rubric-schema.json](references/rubric-schema.json)
- **Shared contract:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
