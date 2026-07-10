# Detection Rules

Each rule defines a specific inconsistency pattern to detect across documentation artifacts.
Rules are classified into three categories based on required action.

## Classification Criteria

> The AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY axis is a shared contract, defined
> in [../../shared/references/fix-action-taxonomy.md](../../shared/references/fix-action-taxonomy.md)
> (also consumed by context-audit). It is orthogonal to severity. The summary below
> is kept for locality; the shared file is authoritative.

### AUTO_FIX
Conditions: mechanically verifiable + idempotent + no data loss risk.
The same operation produces the same result regardless of how many times it runs.

### NEEDS_JUDGMENT
Conditions: requires semantic interpretation or user intent is ambiguous.
The agent presents findings and suggested actions; the user decides.

### REPORT_ONLY
Conditions: informational only. No action is taken in v1.

---

## Rule Definitions

### Rule 1: stale-idea-status

**Category:** AUTO_FIX

**Detects:** `idea-status.md` status does not match reality (cycle existence, skill implementation status).

**Logic:**
1. Parse each row of the ideas table in `idea-status.md`
2. For each idea:
   - If a matching cycle exists in `.agents/artifacts/plans/` (by title/slug) AND cycle status is Complete → idea status should be `Implemented` or archived
   - If a matching skill directory exists in `skills/` → idea status should be `Implemented` or archived
   - If idea status says `Planned` but no cycle file exists → flag as stale
3. Compare expected status with actual status in the table

**Fix Action:** Update the status column in `idea-status.md` to match the detected reality.

---

### Rule 2: unarchived-idea

**Category:** AUTO_FIX

**Detects:** Ideas with status `Planned` or `Implemented` that have not been moved to `archives/`.

**Logic:**
1. Read `.agents/artifacts/ideas/idea-status.md`
2. For each idea with status `Planned` or `Implemented`:
   - Check if the idea file still exists in `.agents/artifacts/ideas/` (not in `archives/`)
   - If a corresponding cycle exists and is Complete, the idea should be archived

**Fix Action:** Move the idea file to `.agents/artifacts/ideas/archives/` and update `idea-status.md` entry.

---

### Rule 3: orphan-plan-in-status

**Category:** AUTO_FIX

**Detects:** Completed plans still listed in `.agents/artifacts/status.md` Current Session that should have been archived to `session-history.md`.

**Logic:**
1. Read `.agents/artifacts/status.md` Current Session table
2. For each entry:
   - Read the referenced plan file
   - If plan status is `Complete` → it should be in `session-history.md`, not in Current Session
3. Cross-reference with `.agents/artifacts/session-history.md`

**Fix Action:** Remove from `status.md` Current Session table and add to `session-history.md` if not already present.

---

### Rule 4: missing-session-history

**Category:** AUTO_FIX

**Detects:** Completed cycles not recorded in `.agents/artifacts/session-history.md`.

**Logic:**
1. Scan all files in `.agents/artifacts/plans/` (excluding `results/`)
2. For each cycle file:
   - Parse the Status line
   - If status is `Complete`:
     - Check if the cycle ID appears in `.agents/artifacts/session-history.md`
     - If not found → flag as missing
3. Report all missing entries

**Fix Action:** Append missing completed cycles to `.agents/artifacts/session-history.md` following the existing table format.

---

### Rule 5: abandoned-plan

**Category:** NEEDS_JUDGMENT

**Detects:** Plans stuck in `Planning` or `In Progress` status while newer plans have been started.

**Logic:**
1. Scan all files in `.agents/artifacts/plans/`
2. For each file:
   - Parse Status and timestamp from filename
   - If status is `Planning` or `In Progress`:
     - Check if any newer cycle file exists (by timestamp comparison)
     - If newer cycles exist → flag as potentially abandoned
3. Present to user with context (how old, what came after)

**Suggested Action:** Ask user whether to mark as `Abandoned` or keep as active.

---

### Rule 6: duplicate-issue

**Category:** NEEDS_JUDGMENT

**Detects:** Semantically duplicate open issues.

**Logic:**
1. Read `.agents/artifacts/issues/issue-status.md`
2. For each open issue:
   - Read the issue file content
   - Compare title and description against all other open issues
   - Use semantic similarity (title overlap, keyword matching, problem description overlap)
3. Flag pairs with high similarity

**Suggested Action:** Present duplicate candidates to user and ask whether to merge or keep separate.

---

### Rule 7: stale-issue-status

**Category:** NEEDS_JUDGMENT

**Detects:** Issues listed as open in `issue-status.md` but already resolved by a completed cycle.

**Logic:**
1. Read `.agents/artifacts/issues/issue-status.md`
2. For each open issue:
   - Search `.agents/artifacts/plans/` for plans that reference this issue (by title or issue ID)
   - If a referencing cycle has status `Complete` → issue may be resolved
3. Present findings with cycle reference

**Suggested Action:** Ask user whether to close the issue and move to archives.

---

### Rule 8: index-file-mismatch

**Category:** AUTO_FIX

**Detects:** Mismatch between index files (`idea-status.md`, `issue-status.md`) and actual files in the directory.

**Logic:**
1. For `.agents/artifacts/ideas/`:
   - List all `.md` files (excluding `idea-status.md` and `archives/`)
   - Parse all entries in `idea-status.md`
   - Detect: files present but not in index, entries in index but file missing
2. For `.agents/artifacts/issues/`:
   - Same logic with `issue-status.md`

**Fix Action:**
- Files not in index: Add entry to the index table with metadata parsed from the file
- Index entries without files: Mark with a warning comment or remove (if file is in archives)

---

### Rule 9: result-accumulation

**Category:** REPORT_ONLY

**Detects:** Growing number of files in `.agents/artifacts/plans/results/` as an informational warning.

**Logic:**
1. Count files in `.agents/artifacts/plans/results/`
2. If count exceeds threshold (default: 20) → include in report
3. Report file count and oldest/newest file dates

**Action:** Report only. No fix in v1.

---

### Rule 10: date-format-legacy

**Category:** NEEDS_JUDGMENT

**Detects:** Files using legacy date format (`YYYY-MM-DD`) in filenames instead of the unified `yyyymmddhhmmss` format.

**Logic:**
1. Scan filenames in `.agents/artifacts/ideas/`, `.agents/artifacts/issues/`, and `.agents/artifacts/plans/`
2. Detect filenames matching pattern `\d{4}-\d{2}-\d{2}` (legacy format)
3. Compare against expected format `\d{14}` (unified format)
4. Flag files using legacy format

**Suggested Action:** Ask user whether to rename files to the unified format.
