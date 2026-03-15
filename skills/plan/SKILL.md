---
name: plan
description: Create timestamped implementation plans with automatic docs/status.md management and progress tracking. Use when user requests (1) "make a plan", "create a plan", "design this feature" for creating new plans, or (2) "update status", "planning done", "implementation complete", "cycle done" for updating implementation progress, or (3) "resume", "continue from last time", "前回の続き", "前回の続きから" for loading the current session state. Alternative to Claude Code's standard plan mode with timestamp-based file naming and status tracking.
---

# Plan

Create implementation plans with timestamp-based filenames and automatic project status tracking.

## Quick Start

When the user requests a plan:

1. Generate timestamp: `yyyymmddhhmmss` format
2. Create plan document: `docs/cycles/{timestamp}_{feature-slug}.md`
3. Update status tracker: `docs/status.md`
4. Guide user to next steps (typically `tdd-red`)

## Workflow

### Phase 1: Initialize

Create necessary directories and generate timestamp.

```bash
# Generate timestamp
date +%Y%m%d%H%M%S

# Ensure directories exist
mkdir -p docs/cycles
```

### Phase 2: Gather Requirements

Ask the user:

1. **Feature name** - What are we implementing?
2. **Brief description** - What is the goal?
3. **Type** - New feature / Enhancement / Bug fix / Refactoring

Keep questions concise. Avoid overwhelming the user with too many questions at once.

### Phase 3: Create Plan Document

**File path:** `docs/cycles/{timestamp}_{feature-slug}.md`

**CRITICAL**: Plan files MUST be created under `docs/cycles/` directory. Do NOT use `docs/plans/` or any other directory. This constraint applies regardless of how this skill is invoked (directly, via issue-cycle, or any other caller).

**Feature slug rules:**
- Convert spaces to hyphens
- Lowercase
- Remove non-alphanumeric characters except hyphens
- Example: "Markdown Hot Reload" → "markdown-hot-reload"

**Template:** See [references/plan-template.md](references/plan-template.md) for the full plan document structure.

**Key sections:**
- Overview and goals
- Architecture design (layer analysis, file structure)
- Implementation steps (numbered, with affected files)
- Test list (organized by layer)
- Security checklist
- Progress tracking table

### Phase 4: Update Status Tracker

Read existing `docs/status.md` if it exists.

**Legacy format auto-migration:**

If `docs/status.md` exists, check for legacy format (inline session history without `session-history.md` link). If detected, run the migration steps defined in [references/status-update-guide.md](references/status-update-guide.md) § "Legacy Format Auto-Migration" **before** writing new session data. This transparently converts old-style status files to the new separated format.

**Update logic:**

- **If status.md exists:** (After migration if needed) Move current session to history, add new session to current
- **If status.md doesn't exist:** Create new file using [references/status-template.md](references/status-template.md)

**Status structure:**
- Current Session (table format with Cycle ID, feature, started time, phase, plan link)
- Session History (previous sessions with completion status)
- Quick Links (to project documentation)

### Phase 5: Confirm and Next Steps

Display to user:

```
✅ Implementation plan created!

📄 Plan: docs/cycles/{timestamp}_{feature-slug}.md
📊 Status: docs/status.md

## Next Steps

1. Review the plan
2. Write tests - "テスト書いて" or "write tests"
3. Implement - "実装して" or "implement this"
4. Commit - "コミットして" (commit will handle it)

Keep it simple. No heavy reviews. Fast tempo! 🚀
```

## Resume Workflow

Use when user wants to resume from previous session:
- "前回の続き" / "continue from last time"
- "前回の続きから" / "resume from last time"
- "続きから" / "resume"
- "再開" / "continue"

### Resume Process

1. **Read current status**
   ```bash
   cat docs/status.md
   ```

2. **Display current session**
   - Show Cycle ID, feature name, phase, plan link
   - Show current focus description
   - Guide user on next steps based on phase

3. **Confirm readiness**
   ```
   📋 Current Session Loaded!

   Cycle: {cycle-id}
   Feature: {feature-name}
   Phase: {phase}
   Plan: docs/cycles/{cycle-id}_{feature-slug}.md

   Current Focus:
   {current-focus-description}

   Ready to continue! 🚀
   ```

## Status Update Workflow

Use when user wants to update implementation progress:
- "update status" / "planning done"
- "start implementation" / "implementation done"
- "cycle complete" / "done"

### Update Process

1. **Read current status**
   ```bash
   cat docs/status.md
   ```

2. **Determine new phase**
   - 🟡 Planning → 🟡 In Progress (when starting implementation)
   - 🟡 In Progress → 🟢 Completed (when cycle done)

3. **Update docs/status.md**
   - Update Current Session phase
   - If completed:
     1. Archive the session to `docs/session-history.md` (add as first row in table format)
     2. If `docs/session-history.md` does not exist, create it with headers
     3. Remove Completed entries from Session History in status.md
     4. Clear Current Session
   - Update "Last Updated" timestamp

4. **Confirm update**
   ```
   ✅ Status updated!

   Cycle: {cycle-id}
   Phase: {new-phase}
   Updated: {timestamp}
   ```

### Status Phase Meanings

- **🟡 Planning**: Plan document created, not yet implementing
- **🟡 In Progress**: Actively implementing (tests/code/commits)
- **🟢 Completed**: Cycle finished, all tasks done

## Lightweight TDD Workflow

After creating the plan, follow this simple workflow:

1. **Write tests** - Create failing tests for the feature
2. **Implement** - Write minimal code to pass tests
3. **Refactor** - Clean up code while keeping tests green
4. **Commit** - Use `commit` to commit changes

No heavy review processes. Keep the tempo fast and development flow smooth.

## File Organization

```
docs/
├── status.md                           # Auto-managed status tracker
├── session-history.md                  # Completed sessions archive (auto-managed)
└── cycles/                             # All implementation plans
    ├── 20260208143000_feature-a.md    # Timestamped plans
    ├── 20260208150000_feature-b.md
    └── 20260208163000_feature-c.md
```

### session-history.md

Archive destination for completed sessions. Managed in table format with new entries prepended to the top. Completed sessions are automatically moved here to prevent status.md from growing too large.

## Templates and Guides

- **Plan document:** [references/plan-template.md](references/plan-template.md)
- **Status tracker:** [references/status-template.md](references/status-template.md)
- **Status update:** [references/status-update-guide.md](references/status-update-guide.md)

Load these templates/guides when creating documents or updating status.

## Notes

- Timestamps use `yyyymmddhhmmss` format for chronological sorting
- Feature slugs are URL-safe (lowercase, hyphens only)
- Status.md automatically archives previous sessions
- Plan documents follow project's architecture principles (layer separation, TDD, etc.)
- If you discover out-of-scope issues during investigation, record them with `/issue-create` and continue with the plan
