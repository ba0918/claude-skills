# Runtime Progress File

The runtime progress file tracks implementation state separately from the plan. The plan is a stable human-readable spec; the progress file is the mutable execution log.

## Path

```
.agents/runtime/progress/{cycle_id}.md
```

`{cycle_id}` is resolved from the plan's `**Cycle ID:**` header, or from the plan filename's timestamp portion if absent.

In satellite mode, the progress file lives in the satellite artifact store alongside the pinned plan, at the same relative path. Satellite ingress copies the plan; the progress file is created fresh in the satellite (no ingress needed for a new run). On harvest, the main-tree orchestrator collects the progress file alongside the plan.

## Format

```markdown
# Progress: {feature_name}

**Plan:** {plan_file_path}
**Cycle ID:** {cycle_id}
**Last Updated:** {YYYY-MM-DD HH:MM:SS}

## Steps

| # | Title | Status | Files Changed | Tests | Notes |
|---|-------|--------|---------------|-------|-------|
| 1 | {step title} | 🟢 Done | {file list} | {count} | {summary, accepted WARN findings} |
| 2 | {step title} | 🟡 In Progress | | | |
| 3 | {step title} | ⚪ Pending | | | |
```

## Fields

| Column | Description |
|--------|-------------|
| # | Step number matching the plan's Implementation Steps |
| Title | Step title from the plan |
| Status | `⚪ Pending` / `🟡 In Progress` / `🟢 Done` |
| Files Changed | Comma-separated list of changed files |
| Tests | Number of tests added or modified |
| Notes | Implementation summary, accepted WARN/INFO findings with rationale |

## Rules

- **Create on first step start**: `mkdir -p .agents/runtime/progress/` and create the file when Phase 1 begins. Initialize all steps as `⚪ Pending`.
- **Update on step completion**: mark the step `🟢 Done` and fill in Files Changed, Tests, and Notes.
- **Re-entry**: on re-entry (session resume), read the progress file to identify completed steps. Do not re-implement `🟢 Done` steps.
- **Plan changes**: if the plan's Implementation Steps change between sessions, steps present in the progress file but absent from the plan are stale — ignore them. Steps in the plan but absent from the progress file are new — add them as `⚪ Pending`.
- **Completion**: when all steps are `🟢 Done`, the progress file remains as-is. The plan's top-level `**Status:**` is updated to `🟢 Completed`.
- **Retention**: the progress file is retained after completion for audit. It is not deleted by cycle or plan-implement.
