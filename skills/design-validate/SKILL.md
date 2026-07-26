---
name: design-validate
description: A multi-stage verification gate for design system compliance. It verifies in the order Static Lint then Visual Regression then Rubric Judge, and approves reflecting the work in code only when every gate passes. Use when the user says "design validate", "validate the design", or "run the validation".
---

# Design Validate

A **multi-stage verification gate** for design-system conformance.
It verifies in the order Static Lint → Visual Regression Test → Rubric Judge, and approves reflecting the code once every gate passes.

**Shared contracts:**
- [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md) — the shared contract for design-system verification
- [../shared/references/verification-gate.md](../shared/references/verification-gate.md) — the shared contract for the pre-completion verification gate

**Pipeline specification:** see [references/validation-pipeline.md](references/validation-pipeline.md).

## Prerequisites

1. `.design/tokens.json` must exist (required)
2. `.design/lint-config.json` must exist (the default is used when omitted)
3. `.design/component-catalog.json` must exist (required by DL101-103)
4. `.design/rubric.json` must exist (the default rubric is used when omitted)
5. `.design/baseline/` must exist (required by the visual test; without it, only the lint runs)

## Workflow

### Step 1: Environment check

1. Confirm the required files exist
2. Verify the baseline hashes (tokensHash / catalogHash in approval.json)
3. Determine which verification levels are available:
   - tokens.json present → Level 1 (lint) available
   - baseline present + Playwright present → Level 3 (visual) available
   - rubric.json present → Level 4 (rubric) available
4. Display the environment summary:
   ```
   🔍 Validation Environment
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   tokens.json:    ✅ Found (v1.0.0)
   catalog.json:   ✅ Found (4 components)
   baseline:       ✅ Approved (2026-04-14)
   Playwright:     ✅ Available
   rubric.json:    ✅ Found (7 criteria)
   
   Available stages: Lint ✅ | Visual ✅ | Rubric ✅
   ```

### Step 2: Stage 1 — Baseline Check

Following Stage 1 of validation-pipeline.md, verify the integrity of the baseline.

- Hashes match → continue
- Hashes differ → display a warning and present the path to re-approval. Switch to lint-only mode

### Step 3: Stage 2 — Static Lint

Run the same logic as the design-lint skill internally.

1. Scan every target file
2. Apply DL001-006 (Token) + DL101-103 (Component) + DL201-204 (Page/Layout)
3. Map the results onto R001, R002, R003

**Short-circuit evaluation:** any mechanical item FAILs → skip Stages 3 and 4 and FAIL immediately

```
❌ Stage 2: Static Lint — FAIL

R001 Token Compliance: FAIL (3 violations)
R002 Component Compliance: PASS
R003 Layout Compliance: PASS

Needs fixing:
  src/components/Header.tsx:42 — DL001: hard-coded color '#FF6B6B'
  src/pages/Landing.tsx:15 — DL006: CSS variable not used '#2563EB'
  src/pages/Landing.tsx:28 — DL001: hard-coded color '#10B981'

The Visual / Rubric stages were skipped.
Fix the lint violations first, then re-run.
```

### Step 4: Stage 3 — Visual Regression

Comparison against the baseline screenshots.

1. Confirm the Storybook build (whether `npx storybook build` is possible)
   - Not possible → skip and redistribute the weight
2. Take screenshots with Playwright
3. Compare pixel by pixel against the corresponding files in baseline/screenshots/
4. At or below `maxDiffPixelRatio` → pass
5. Map the results onto R004, R007

**Graceful degradation when it is not installed:**
```
⚠️ Stage 3: Visual Regression — SKIPPED
Storybook / Playwright are not installed, so the visual test was skipped.
The weights of R004 and R007 are redistributed across the other items.
```

### Step 5: Stage 4 — Rubric Judge

Launch an independent judge subagent.

1. Prepare the target screenshots (already taken in Stage 3, or use the baseline)
2. Read the Do's/Don'ts sections of DESIGN.md
3. Build the prompt for the `llm-judge` items of rubric.json
4. Launch the subagent and obtain a structured evaluation
5. Map the results onto R005, R006

**Important:** the judge subagent is **read-only**. It never edits a file.

### Step 6: Aggregation and the final verdict

Following Stage 5 of validation-pipeline.md:

1. Compute the weighted average of every item
2. Compare against `passingScore`
3. Build the evidence JSON
4. Save it to `.design/validate-report.json`

### Step 7: Display the result

**On PASS:**
```
✅ Design Validation: PASS (Score: 93.5/100)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| ID   | Name                   | Score | Method     |
|------|------------------------|-------|------------|
| R001 | Token Compliance       | 100   | mechanical |
| R002 | Component Compliance   | 100   | mechanical |
| R003 | Layout Compliance      | 100   | mechanical |
| R004 | Visual Consistency     | 95    | visual     |
| R005 | Visual Harmony         | 100   | llm-judge  |
| R006 | Interaction Coherence  | 50    | llm-judge  |
| R007 | Responsive Behavior    | 100   | visual     |

📄 Evidence: .design/validate-report.json

Reflected in the code — OK! ✅
```

**On FAIL:**
```
❌ Design Validation: FAIL (Score: 65.0/100, required: 80)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{per-item score table}

Items needing improvement:
  R001 Token Compliance: 3 violations → replace with var(--*)
  R006 Interaction Coherence: the ghost button hover effect is inconsistent

📄 Evidence: .design/validate-report.json
```

## Execution modes via $ARGUMENTS

| Argument | Behavior |
|------|------|
| (none) | Run every stage |
| `lint` | Stage 2 only (lint only) |
| `visual` | Stage 2 + Stage 3 (lint + visual) |
| `full` | Every stage (the same as the default) |
| `report` | Display the most recent validate-report.json |

## Absolute Constraints

- **Never fabricate** a verification result. Every score is based on the actual output of a tool run
- Emit the evidence in the form prescribed by the verification-gate contract
- Run the LLM judge in a **subagent separate** from the LLM that generated the design
- Never judge a visual test as "pass" without a baseline
- Leave evidence even in the lint-only case (as partial evidence)

## References

- **Pipeline specification:** [references/validation-pipeline.md](references/validation-pipeline.md)
- **Rubric Schema:** [../design-scaffold/references/rubric-schema.json](../design-scaffold/references/rubric-schema.json)
- **Shared contract:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
- **Verification gate:** [../shared/references/verification-gate.md](../shared/references/verification-gate.md)
