# Status Update Guide

Detailed instructions for updating docs/status.md during implementation cycles.

## Legacy Format Auto-Migration

When reading an existing `docs/status.md`, check whether it uses the legacy format (inline session history) and automatically migrate it to the new format (session-history.md separated).

### Detection Criteria

The file is in **legacy format** if ALL of the following are true:

1. A `## 📜 Session History` or `## Session History` section exists
2. That section does NOT contain a link to `[session-history.md]`
3. That section contains table data rows (`|` で始まる行で、ヘッダー行 `| Cycle ID |` や区切り行 `|---` を除く行)

If the section already contains a link to `session-history.md`, the file is already in the new format — skip migration.

### Migration Steps

When legacy format is detected, perform the following **before** writing the new session:

#### Step 1: Extract history data rows

From the `## 📜 Session History` or `## Session History` section, collect all table rows that:
- Start with `|`
- Are NOT header rows (contain `Cycle ID`)
- Are NOT separator rows (contain `|---`)

#### Step 2: Write to session-history.md

- **If `docs/session-history.md` exists:** Insert the extracted rows immediately after the header separator row (`|---|`), before any existing data rows
- **If `docs/session-history.md` does not exist:** Create it with:

```markdown
# Session History

| Cycle ID | Feature | Started | Completed | Plan |
|----------|---------|---------|-----------|------|
{extracted rows}
```

#### Step 3: Replace Session History section in status.md

Replace the entire Session History section content with the archive link:

```markdown
## 📜 Session History

_Archived sessions can be found in [session-history.md](./session-history.md)._
```

#### Step 4: Ensure Quick Links section exists

If `## 🔗 Quick Links` section is missing, add it (using the template from status-template.md):

```markdown
## 🔗 Quick Links

- [Architecture](./ARCHITECTURE.md)
- [Coding Principles](./CODING_PRINCIPLES.md)
- [All Cycles](./cycles/)
- [Project Root](../)
```

#### Step 5: Ensure footer note exists

If the footer note (`**Note:** This file is auto-managed by the \`plan\` skill.`) is missing, append it at the end of the file.

### Idempotency

- If the file is already in new format (contains `session-history.md` link in Session History section), skip all migration steps
- If `docs/status.md` does not exist, skip migration (a new file will be created from the template)
- Running migration multiple times produces the same result

### Timing

Migration runs at Phase 4 ("Read existing status.md"), **before** any new session data is written. This ensures the file is in the correct format before updates are applied.

---

## When to Update Status

### Trigger Phrases
- "update status" / "planning done"
- "start implementation" / "implementation done"
- "cycle complete" / "done"

## Status Phases

| Phase | Emoji | Meaning |
|-------|-------|---------|
| Planning | 🟡 | Plan created, not yet implementing |
| In Progress | 🟡 | Actively writing tests/code/commits |
| Completed | 🟢 | Cycle finished, all tasks done |

## Update Workflow

### Step 1: Read Current Status

```bash
cat docs/status.md
```

Parse the "Current Session" table to extract:
- Cycle ID
- Feature name
- Current phase
- Plan link

### Step 2: Determine New Phase

Ask user or infer from context:

**Planning → In Progress**
- User says: "planning done", "start implementation"
- Trigger: User starts writing code/tests

**In Progress → Completed**
- User says: "implementation done", "cycle complete", "done"
- Trigger: User commits final changes

### Step 3: Update docs/status.md

#### Case 1: Planning → In Progress

```markdown
## 🎯 Current Session

| Field | Value |
|-------|-------|
| **Cycle ID** | `20260208010855` |
| **Feature** | Phase 3: Options UI & Hot Reload |
| **Started** | 2026-02-08 01:08:55 |
| **Phase** | 🟡 In Progress |  <!-- Changed from Planning -->
| **Plan** | [docs/plans/20260208010855_phase-3-options-ui-hot-reload.md](./cycles/20260208010855_phase-3-options-ui-hot-reload.md) |

**Current Focus:**
Phase 3-1 implementation in progress. Theme system extended with 4 new themes.
```

Update:
- Phase: `🟡 Planning` → `🟡 In Progress`
- Current Focus: Update with current work
- Last Updated: Update timestamp

#### Case 2: In Progress → Completed

Move Current Session to Session History archive and clear Current Session.

**Step 2a: Archive to session-history.md**

Archive the completed session to `docs/session-history.md`.

1. If `docs/session-history.md` does not exist, create it with the following header:

```markdown
# Session History

| Cycle ID | Feature | Started | Completed | Plan |
|----------|---------|---------|-----------|------|
```

2. Add new entry as the first row (immediately after the header):

```markdown
| `20260208010855` | Phase 3: Options UI & Hot Reload | 2026-02-08 | 2026-02-08 | [Link](./cycles/20260208010855_phase-3-options-ui-hot-reload.md) |
```

**Step 2b: Clear status.md Session History**

Remove Completed entries from Session History section in status.md (since they are now archived).

```markdown
## 📜 Session History

_Archived sessions can be found in [session-history.md](./session-history.md)._
```

**Step 2c: Clear Current Session:**

```markdown
## 🎯 Current Session

_No active session. Create a new plan to start._
```

### Step 4: Confirm Update

Display to user:

```
✅ Status updated!

Cycle: 20260208010855
Phase: 🟡 Planning → 🟡 In Progress
Updated: 2026-02-08 01:45:00

Next: Continue implementation → Commit → Mark as completed
```

Or for completion:

```
✅ Cycle completed!

Cycle: 20260208010855 - Phase 3: Options UI & Hot Reload
Started: 2026-02-08 01:08:55
Completed: 2026-02-08 02:15:30
Duration: ~1 hour

Moved to Session History ✅
Ready for next cycle!
```

## Example: Full Update Flow

### Scenario: User finishes Phase 3-1

**User says:** "Phase 3-1 done, update status"

**Actions:**

1. Read docs/status.md
2. Extract current cycle: `20260208010855`
3. Phase transition: `🟡 In Progress` → `🟢 Completed`
4. Get completion timestamp: `date +"%Y-%m-%d %H:%M:%S"`
5. Update docs/status.md:
   - Move current to history with completion time
   - Add summary of what was accomplished
   - Clear current session
6. Confirm to user

## Tips

- **Auto-infer phase**: If user commits code, likely "In Progress"
- **Ask if unclear**: "Planning done? In progress? Completed?"
- **Keep summaries concise**: 1-2 sentences in Session History
- **Preserve history**: Completed sessions are archived to session-history.md. They can be removed from status.md, but entries in session-history.md must never be deleted
