# Report Template

Output format for the doc-audit report. Use this template to structure the final report displayed to the user.

## Format

```
══════════════════════════════════════
DOC-AUDIT REPORT
Scanned: {datetime}
Mode: {mode: "full" | "dry-run" | "category:{name}"}
══════════════════════════════════════

Summary
  Ideas:    {count} scanned, {issues} issues
  Issues:   {count} scanned, {issues} issues
  Cycles:   {count} scanned, {issues} issues
  Results:  {count} files
  Total:    {total_issues} issues found

AUTO_FIX ({count})
  1. [{rule_name}] {description}
     Files: {affected_files}
     Action: {fix_action}
  ...

NEEDS_JUDGMENT ({count})
  1. [{rule_name}] {description}
     Files: {affected_files}
     Suggestion: {suggested_action}
  ...

REPORT_ONLY ({count})
  1. [{rule_name}] {description}
  ...

No issues found.              <- When zero issues detected
══════════════════════════════════════
```

## Field Descriptions

| Field | Description |
|-------|-------------|
| `datetime` | Scan execution timestamp in `YYYY-MM-DD HH:MM:SS` format |
| `mode` | Execution mode: `full` (default), `dry-run` (report only), or `category:{name}` (filtered) |
| `count` | Number of artifacts scanned in each category |
| `issues` | Number of problems detected in each category |
| `rule_name` | Detection rule identifier (e.g., `stale-idea-status`) |
| `description` | Human-readable description of the detected problem |
| `affected_files` | Comma-separated list of affected file paths |
| `fix_action` | Description of the automatic fix that will be applied |
| `suggested_action` | Recommended action for NEEDS_JUDGMENT items |

## Section Display Rules

- **AUTO_FIX section**: Only display if there are AUTO_FIX items
- **NEEDS_JUDGMENT section**: Only display if there are NEEDS_JUDGMENT items
- **REPORT_ONLY section**: Only display if there are REPORT_ONLY items
- **"No issues found"**: Only display when total issues across all categories is zero
- **In dry-run mode**: Append `[DRY-RUN] No changes were made.` at the end

## Fix Result Report (after Phase 4)

When fixes are applied, append:

```
══════════════════════════════════════
FIX RESULTS
══════════════════════════════════════

Auto-fixed ({count})
  1. [{rule_name}] {fix_description}
     Status: Done

User-decided ({count})
  1. [{rule_name}] {description}
     Decision: {approved | skipped}
     Status: {Done | Skipped}

Skipped ({count})
  1. [{rule_name}] {description}
     Reason: {reason}

══════════════════════════════════════
```
