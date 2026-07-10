---
name: doc-audit
description: docs 内の全アーティファクト（ideas, issues, cycles, session-history）を横断スキャンし、不整合を検出・自動修復する。「doc-audit」「ドキュメント監査」「docs 監査」で起動。--dry-run でレポートのみ、カテゴリ指定（ideas/issues/cycles）で対象を限定可能。汎用スキル。
---

# Doc Audit

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Skill that scans all documentation artifacts within the project and detects/fixes inconsistencies between them.

## Distinction from doc-check

- **doc-check**: Verifies consistency between **documentation and code** (code <-> docs)
- **doc-audit**: Verifies consistency between **documentation and documentation** (docs <-> docs)

## Arguments

- None: Full scan of all categories
- `--dry-run`: Report only, no fixes applied
- Category name (`ideas`, `issues`, `cycles`): Scan only the specified category

Parse `$ARGUMENTS` to determine the execution mode:
- If contains `--dry-run` or `dry-run` → set dry_run = true
- If contains `ideas`, `issues`, or `cycles` → set category filter
- Both can be combined (e.g., `--dry-run ideas`)

## Prerequisites

Before starting, verify:

1. Check if `docs/` directory exists in the project root
   - If not found → report "Target directory `docs/` not found." and stop
2. Note which index files exist:
   - `.agents/artifacts/ideas/idea-status.md` — if missing, skip idea-related rules
   - `.agents/artifacts/issues/issue-status.md` — if missing, skip issue-related rules
   - `.agents/artifacts/status.md` — if missing, skip status-related rules
   - `.agents/artifacts/session-history.md` — if missing, skip history-related rules

## Phase 1: Scan

Collect metadata from all documentation artifacts. Execute scans sequentially.

### 1.1 Ideas Scan (skip if category filter excludes)

```
Target: .agents/artifacts/ideas/
```

1. Read `.agents/artifacts/ideas/idea-status.md`
   - Parse the Markdown table: extract each row's idea name, file link, tags, created date, status, summary
   - If parse fails → record WARN "Failed to parse idea-status.md" and skip idea rules
2. List all `.md` files in `.agents/artifacts/ideas/` (excluding `idea-status.md`)
3. List all files in `.agents/artifacts/ideas/archives/` (create list; directory may not exist)
4. For each idea entry:
   - Check if a corresponding cycle exists in `.agents/artifacts/plans/` by matching slug/title
   - Check if a corresponding skill directory exists in `skills/` by matching name
5. Record: `{ideas: [{name, file, status, has_cycle, cycle_status, has_skill, is_archived}]}`

### 1.2 Issues Scan (skip if category filter excludes)

```
Target: .agents/artifacts/issues/
```

1. Read `.agents/artifacts/issues/issue-status.md`
   - Parse the Markdown table: extract each row's issue name, file link, tags, created date, summary
   - If parse fails → record WARN and skip issue rules
2. List all `.md` files in `.agents/artifacts/issues/` (excluding `issue-status.md`)
3. List all files in `.agents/artifacts/issues/archives/`
4. For each issue entry:
   - Check if a corresponding cycle references this issue
5. Record: `{issues: [{name, file, tags, is_resolved_by_cycle, cycle_ref}]}`

### 1.3 Cycles Scan (skip if category filter excludes)

```
Target: .agents/artifacts/plans/
```

1. List all `.md` files in `.agents/artifacts/plans/` (excluding `results/` subdirectory)
2. For each cycle file:
   - Parse filename: extract timestamp and slug
   - Read the file and parse: Status line, Cycle ID, Feature name, Started date
   - Determine if Completed: status contains "Complete" or "Done"
3. Read `.agents/artifacts/session-history.md`
   - Parse the table: extract all recorded cycle IDs
4. Read `.agents/artifacts/status.md`
   - Parse Current Session table: extract listed cycle IDs and their phases
5. Count files in `.agents/artifacts/plans/results/` if directory exists
6. Record: `{cycles: [{id, slug, status, is_completed, in_session_history, in_status_current}], results_count}`

### 1.4 Cross-Reference Data Assembly

Combine all scan data into a unified structure for analysis:

```
scan_result = {
  ideas: [...],
  issues: [...],
  cycles: [...],
  results_count: N,
  skipped_categories: [...],
  parse_warnings: [...]
}
```

## Phase 2: Analyze

Apply detection rules from [references/checks.md](references/checks.md) to the scan results.

### Execution

For each applicable rule (respecting category filter):

1. Evaluate the rule's logic against the scan data
2. If a problem is detected, record (the `category` values follow the shared
   [fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md); `severity`
   is doc-audit's local ERROR/WARN/INFO scale, orthogonal to `category`):
   ```
   {
     rule: "rule_name",
     category: "AUTO_FIX" | "NEEDS_JUDGMENT" | "REPORT_ONLY",
     severity: "ERROR" | "WARN" | "INFO",
     description: "Human-readable description",
     affected_files: ["path1", "path2"],
     fix_action: "Description of fix" (for AUTO_FIX),
     suggested_action: "Suggestion" (for NEEDS_JUDGMENT)
   }
   ```
3. If no problems are detected for a rule, skip it (do not record OK entries)

### Rule Application Order

Apply rules in numeric order (Rule 1 through Rule 10). This ensures:
- Index-level checks (Rules 1, 2, 8) run before cross-reference checks (Rules 3, 4)
- Simple checks before semantic checks (Rules 5, 6, 7)
- Informational checks last (Rule 9, 10)

### Category-to-Rule Mapping

| Category Filter | Applicable Rules |
|----------------|-----------------|
| `ideas` | 1, 2, 8 (ideas part) |
| `issues` | 6, 7, 8 (issues part) |
| `cycles` | 3, 4, 5, 9, 10 |
| (none/all) | All rules 1-10 |

## Phase 3: Report

Generate the audit report following [references/report-template.md](references/report-template.md).

### Steps

1. Group detected problems by category (AUTO_FIX, NEEDS_JUDGMENT, REPORT_ONLY)
2. Format using the report template
3. Display the report to the user
4. If `dry_run` is true → display `[DRY-RUN] No changes were made.` and **stop here**

## Phase 4: Fix

Apply fixes for detected problems. **Skip entirely if dry_run is true.**

### 4.1 AUTO_FIX Processing

For each AUTO_FIX problem, in order:

1. Display the problem and planned action
2. Execute the fix:
   - **Status updates** (Rules 1, 3, 7): 該当 Markdown テーブルを差分編集
   - **File moves** (Rule 2): シェルでファイルを移動し、インデックスを差分編集
   - **History additions** (Rule 4): session-history.md に行を追記
   - **Index sync** (Rule 8): インデックスファイルにエントリを追加・更新
3. Record result: `{rule, status: "Done", description}`

**Idempotency guarantee**: Before each fix, verify the problem still exists. If already resolved (e.g., by a previous fix in this run), skip.

### 4.2 NEEDS_JUDGMENT Processing

For each NEEDS_JUDGMENT problem, in order:

1. Present the problem to the user with full context:
   - What was detected
   - Why it matters
   - Suggested action
   - Affected files
2. Ask the user directly: "Fix this? (describe what will happen) or skip?"
3. Based on user response:
   - **Approved**: Execute the suggested fix, record `{status: "Done", decision: "approved"}`
   - **Skipped**: Record `{status: "Skipped", decision: "skipped"}` and move to next

### 4.3 Fix Results Summary

After all fixes are processed, display the fix results report following the template in [references/report-template.md](references/report-template.md).

## Error Handling

| Case | Action |
|------|--------|
| `docs/` directory does not exist | Report "Target directory not found" and exit |
| `idea-status.md` / `issue-status.md` missing | Skip the corresponding category's scan and note in report |
| `.agents/artifacts/status.md` / `.agents/artifacts/session-history.md` missing | Skip related checks and note in report |
| Markdown table parse failure | Skip the file's rule checks and report as WARN |
| File write error during AUTO_FIX | Record error and continue to next problem (partial fix tolerance) |
| `archives/` directory does not exist | Create it before executing the move operation |

## Important Rules

- **Path safety**: All file **write operations** (edit, move, create) must be within `docs/` directory. Read-only checks (e.g., verifying `skills/` directory existence for Rule 1) are permitted outside `docs/`. Do not access files outside the project root.
- **Idempotent fixes**: Every AUTO_FIX operation must produce the same result when run multiple times.
- **No data loss**: Never delete files. Move to archives instead of deleting. Status updates preserve existing content.
- **Dry-run fidelity**: In dry-run mode, absolutely zero file modifications. Only read and report.
- **User sovereignty for NEEDS_JUDGMENT**: Never execute NEEDS_JUDGMENT fixes without explicit user approval.
- **Do not commit**: This skill only applies fixes. Committing is left to the user or the commit skill.
- **Graceful degradation**: If a scan/check fails, skip it and continue with remaining checks. Report all skips.
