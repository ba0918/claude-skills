---
name: migrate-cycles-to-plans
description: "Migrate docs/cycles/ to .agents/artifacts/plans/ across a project. Renames the directory, updates all text references in markdown files, and flips CRITICAL guard warnings. Supports check (dry-run) and run modes. Use when upgrading from older versions of claude-skills that used docs/cycles/ for plan storage. Triggers: \"migrate\", \"docs/cycles → .agents/artifacts/plans\", \"rename cycles to plans\"."
---

# Migrate: docs/cycles/ → .agents/artifacts/plans/

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Migrate the legacy `docs/cycles/` directory to `.agents/artifacts/plans/`.

Older versions of this plugin stored plan files under `docs/cycles/`. This caused LLMs to frequently create files in `.agents/artifacts/plans/` instead (the natural inference from "plan"). This migration renames the directory and updates all references.

## Usage

```
/claude-skills:migrate-cycles-to-plans          # check mode (dry-run, default)
/claude-skills:migrate-cycles-to-plans check    # same as above
/claude-skills:migrate-cycles-to-plans run      # execute migration
```

## Workflow

1. Parse `$ARGUMENTS`: if empty or `check`, use check mode. If `run`, use run mode.
2. Run the migration script:

```bash
bash skills/migrate-cycles-to-plans/scripts/migrate-cycles-to-plans.sh {mode}
```

The script path is relative to the plugin root. The script uses `git rev-parse --show-toplevel` to find the **user's project root**, so it operates on the current project regardless of where the plugin is installed.

3. Display the script output to the user as-is.

4. If run mode completed successfully, suggest:
   - `git diff` to review changes
   - `/claude-skills:doc-check` to verify consistency
   - `/claude-skills:commit` to commit the migration
