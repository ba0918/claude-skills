# Exit Contract — Fill Guide

How to populate the `## Exit Contract` section in an idea memo. The canonical form is the one embedded in [idea-template.md](idea-template.md) — this file explains what each field means and how downstream consumers use it.

## Where it lives

The exit contract is a section within the idea memo, not a standalone file. When the wrap workflow determines that the session produced actionable agreements (Step 3), it populates the `## Exit Contract` section in the idea memo. The section heading, field names, and sub-heading levels must match [idea-template.md](idea-template.md) exactly — the Plan Workflow detects `## Exit Contract` and `**Exit Status:**` by text match.

## Field reference

### Exit Status

`**Exit Status:** CONVERGED` or `**Exit Status:** BLOCKED`

- **CONVERGED**: all blocking undecided items resolved, agreements reached. The Plan Workflow will proceed.
- **BLOCKED**: undecided items with `Blocks plan? = true` remain. The Plan Workflow will refuse to create a plan.

### Agreements

| Column | Meaning |
|--------|---------|
| # | Identifier (A1, A2, ...). Referenced by Acceptance Criteria and Routing |
| Decision | What was decided, in one sentence |
| Rationale | Why this was decided (the reason, not a restatement) |
| Destination | Where this agreement goes next. Typically `ledger` |

Each agreement becomes a candidate for `ledger extract`.

### Undecided Items

| Column | Meaning |
|--------|---------|
| # | Identifier (U1, U2, ...) |
| Item | The open question |
| Why undecided | What information or decision is missing |
| Blocks plan? | `true` if this item must be resolved before plan creation. Any `true` entry sets Exit Status to BLOCKED |

### Acceptance Criteria

| Column | Meaning |
|--------|---------|
| # | Identifier (C1, C2, ...) |
| Criterion | An observable behavior or constraint the implementation must satisfy |
| Verifiable? | `yes` if this can be tested mechanically; `no` if it requires human judgment. Criteria with `no` are recorded but flagged — they cannot become clauses |
| Source | Which agreement or discussion point produced this criterion |

Each verifiable criterion becomes a candidate for `spec-verify formalize`.

### Codebase Evidence

Code investigation results that grounded the discussion. File paths and findings only — no inline code blocks.

### Routing

Where each piece of the exit contract goes next. This table is guidance for the human or orchestrator, not automatic execution.

| Destination | What goes there | How |
|-------------|----------------|-----|
| Ledger | Agreements | `ledger extract` with agreements as input |
| Plan | Agreements + acceptance criteria | `plan-create` with agreements as the What & Why seed |
| Spec | Agreements-based spec draft | Generate via [spec-generation.md](spec-generation.md) to `docs/spec/` (CONVERGED only) |
| Docs | Domain knowledge discovered | Update relevant docs (manual or via `doc-write`) |
| Clauses | Verifiable acceptance criteria | `spec-verify formalize` (follow-up, not blocking) |
