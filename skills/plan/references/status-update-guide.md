# Status Update Guide

Detailed instructions for updating docs/status.md during implementation cycles.

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
| **Plan** | [docs/cycles/20260208010855_phase-3-options-ui-hot-reload.md](./cycles/20260208010855_phase-3-options-ui-hot-reload.md) |

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
