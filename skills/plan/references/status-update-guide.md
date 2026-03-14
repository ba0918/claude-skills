# Status Update Guide

Detailed instructions for updating docs/status.md during implementation cycles.

## When to Update Status

### Trigger Phrases
- "状態更新して" / "update status"
- "planning終わった" / "planning done"
- "実装開始" / "start implementation"
- "実装完了" / "implementation done"
- "このサイクル完了" / "cycle complete"

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
- User says: "planning終わった", "実装開始", "start implementation"
- Trigger: User starts writing code/tests

**In Progress → Completed**
- User says: "実装完了", "cycle complete", "done"
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

Completed セッションを `docs/session-history.md` にアーカイブする。

1. `docs/session-history.md` が存在しない場合、以下のヘッダーで新規作成する:

```markdown
# Session History

| Cycle ID | Feature | Started | Completed | Plan |
|----------|---------|---------|-----------|------|
```

2. テーブルの先頭行（ヘッダー直後）に新しいエントリを追加する:

```markdown
| `20260208010855` | Phase 3: Options UI & Hot Reload | 2026-02-08 | 2026-02-08 | [Link](./cycles/20260208010855_phase-3-options-ui-hot-reload.md) |
```

**Step 2b: Clear status.md Session History**

status.md の Session History セクションから Completed エントリを削除する（アーカイブ済みのため）。

```markdown
## 📜 Session History

_アーカイブ済みセッションは [session-history.md](./session-history.md) を参照。_
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

**User says:** "Phase 3-1完了したよ、status更新して"

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
- **Ask if unclear**: "Planning終わった？実装中？完了した？"
- **Keep summaries concise**: 1-2 sentences in Session History
- **Preserve history**: Completed セッションは session-history.md にアーカイブされる。status.md からは削除してよいが、session-history.md のエントリは削除しない
