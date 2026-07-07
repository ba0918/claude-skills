# Decompose Guide - Instruction Decomposition

Guide for decomposing a natural language instruction into multiple independent plans.

## Decomposition Principles

### 1. Cut at Feature Boundaries

One plan = one user-facing feature or capability. Do not mix unrelated features into the same plan.

```
Good:  Plan A = "User authentication",  Plan B = "Weight CRUD"
Bad:   Plan A = "User authentication + Weight model creation"
```

### 2. Determine Dependencies via Data Flow

If Plan B uses a table, API, or module created by Plan A, then B depends on A.

```
A creates: users table, auth middleware
B uses: auth middleware → B depends on A
```

### 3. Estimate Affected Files Conservatively

When uncertain, include files broadly. Over-estimation makes plans non-parallel (safe). Under-estimation risks file conflicts (dangerous).

Include:
- Source files to create or modify
- Test files for the changed source files
- Configuration files that need updates (package.json, tsconfig.json, etc.)
- Migration files or schema changes

### 4. Place Shared Infrastructure in the First Plan

Database migrations, shared type definitions, configuration changes, and utility modules that multiple plans depend on should be placed in the earliest plan.

## Decomposition Output Format

For each plan, produce the following structure:

```
Plan {letter}: {title}
  Description: {one-line summary}
  Affected files: [{file1}, {file2}, ...]
  Dependencies: [{plan_letter}, ...] or "none"
  Priority: {number} (lower = earlier)
```

After listing all plans, produce the dependency graph and execution groups:

```
Dependency graph:
  A → B → C
  A → D

Execution groups:
  Group 1: [A]
  Group 2: [B, D]  ← parallel (files are orthogonal)
  Group 3: [C]
```

## Edge Case Handling

| Scenario | Action |
|----------|--------|
| Instruction is too vague to decompose | Return error, request clarification |
| Decomposes into 0 plans | Return error, request clarification |
| Decomposes into 1 plan | Fall back to normal `$cycle` (skip parallel overhead) |
| A plan has empty affected files | Treat as orthogonal to all other plans, place in any group |
| Circular dependency detected | Report error, suggest restructuring |

## User Approval Display Format

```
══════════════════════════════════════
DECOMPOSE RESULT
══════════════════════════════════════

Plans: {N}
Execution groups: {M}

Group 1 (sequential):
  [A] {title} — no dependencies

Group 2 (parallel):
  [B] {title} — depends on A
  [D] {title} — depends on A

Group 3 (sequential):
  [C] {title} — depends on B

Estimated total groups: {M} rounds
──────────────────────────────────────
Proceed? (y/n/edit)
```

- **y**: Proceed to Phase 1
- **n**: Abort
- **edit**: Accept modification instructions and re-decompose

## Plan Generation

After approval, generate each plan using the same format as `$plan`. Each plan file is saved to `docs/plans/{timestamp}_{slug}.md` with its own timestamp (or a shared timestamp with different slugs).

The "Files to Change" section in each plan is critical — it is the input for the orthogonality check in Phase 1.
