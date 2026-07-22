---
name: plan
description: Create timestamped implementation plans with automatic .agents/artifacts/status.md management and progress tracking. Use when user requests (1) "make a plan", "create a plan", "design this feature" for creating new plans, or (2) "update status", "planning done", "implementation complete", "cycle done" for updating implementation progress, or (3) "resume", "continue from last time", "前回の続き", "前回の続きから" for loading the current session state. Alternative to Claude Code's standard plan mode with timestamp-based file naming and status tracking.
---

# Plan

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Create implementation plans with timestamp-based filenames and automatic project status tracking.

## Quick Start

When the user requests a plan:

1. Generate timestamp: `yyyymmddhhmmss` format
2. Create plan document: `.agents/artifacts/plans/{timestamp}_{feature-slug}.md`
3. Update status tracker: `.agents/artifacts/status.md`
4. Guide user to next steps (typically `tdd-red`)

## Workflow

### Phase 1: Initialize

Create necessary directories and generate timestamp.

```bash
# Generate timestamp
date +%Y%m%d%H%M%S

# Ensure directories exist
mkdir -p .agents/artifacts/plans
```

### Phase 2: Gather Requirements

Feature 名 / 概要 / type（新機能 / 改修 / bug fix / refactor）が必要。ユーザー入力から明確に取れるなら聞かずに進む。不足があれば interactive では簡潔に聞く、Auto mode（`cycle` / `issue-cycle` 等の headless 呼び出し）ではブロックせず文脈から推論する。

推論した項目は最終応答で明示し、ユーザーが訂正できる形にする。

### Phase 3: Create Plan Document

**File path:** `.agents/artifacts/plans/{timestamp}_{feature-slug}.md`

**CRITICAL**: Plan files MUST be created under `.agents/artifacts/plans/` directory. Do NOT use `docs/cycles/` or any other directory. This constraint applies regardless of how this skill is invoked (directly, via issue-cycle, or any other caller).

**Feature slug**: `[a-z0-9-]+` のみ（標準的な URL slug 化）。非 ASCII 入力（日本語等）は意味翻訳を優先し、プロジェクト内の既存関連命名（skills や既存 plan）と揃える。翻訳が困難な固有名詞のみ Hepburn 式ローマ字化、意味が曖昧なら user に確認する（空 / garbled slug に落ちるのは禁止）。原文の feature 名は plan header `# {Feature Name}` と status.md `Feature` 列に verbatim で保持する。

**Template:** See [references/plan-template.md](references/plan-template.md) for the full plan document structure.

**Key sections:**
- Overview and goals
- Architecture design (layer analysis, file structure)
- Implementation steps (numbered, with affected files)
- Test list (organized by layer)
- Security checklist
- Progress tracking table

**Optional `Issue` field:**
When creating a plan from an issue (via `issue-plan` or `issue-cycle`), add `**Issue:** {issue_slug}` to the plan header. This field is used by `cycle` to auto-close the issue upon completion. If the plan is not issue-originated, omit this line.

### Phase 4: Update Status Tracker

Read existing `.agents/artifacts/status.md` if it exists.

**Legacy format auto-migration:**

If `.agents/artifacts/status.md` exists, check for legacy format (inline session history without `session-history.md` link). If detected, run the migration steps defined in [references/status-update-guide.md](references/status-update-guide.md) § "Legacy Format Auto-Migration" **before** writing new session data. This transparently converts old-style status files to the new separated format.

**Update logic:**

- **If status.md exists:** (After migration if needed) Move current session to history, add new session to current
- **If status.md doesn't exist:** Create new file using [references/status-template.md](references/status-template.md)

**Handling an unfinished Current Session:**

If the existing Current Session is still `🟡 Planning` or `🟡 In Progress` when a new plan is being created, the previous session must be resolved before overwriting Current Session. Apply in order:

1. **Interactive mode**: ask the user which to do:
   - (a) Resume the previous session (suggest `/claude-skills:plan-resume` and abort the new plan creation)
   - (b) Archive the previous session as **abandoned** (move to `session-history.md` with `Completed` = current timestamp and append `(abandoned)` suffix to the Feature column so it's visually distinguishable). Follow `session-history.md`'s existing convention for the Started / Completed columns: date only (`YYYY-MM-DD`), no time-of-day, even though the source status.md session used a full timestamp.
   - (c) Archive the previous session as **completed** (if the user confirms it was actually finished but status wasn't updated)
2. **Auto mode / headless invocation** (e.g. called from `cycle`, `issue-cycle`, `parallel-cycle`): default to **(b) archive as abandoned** without prompting. Log the archival action in the "Next Steps" output so the user can correct it if needed.

In all cases, after the previous session is resolved, proceed with adding the new session as Current Session.

**Status structure:**
- Current Session (table format with Cycle ID, feature, started time, phase, plan link)
- Session History (previous sessions with completion status)
- Quick Links (to project documentation)

### Phase 5: Confirm and Next Steps

Display to user:

```
✅ Implementation plan created!

📄 Plan: .agents/artifacts/plans/{timestamp}_{feature-slug}.md
📊 Status: .agents/artifacts/status.md

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
   cat .agents/artifacts/status.md
   ```

2. **Display current session**
   - Show Cycle ID, feature name, phase, plan link
   - Show current focus description
   - Guide user on next steps based on phase

2.5. **Restore execution-state checkpoint (if any)** — auxiliary during resume; follow the shared contract [../shared/references/checkpoint-pattern.md](../shared/references/checkpoint-pattern.md).

   - If `.agents/artifacts/plans/checkpoints/{cycle_id}.md` exists, classify:
     `python3 skills/shared/scripts/checkpoint.py classify --repo . --file <path>`
     (contract §CLI invocation for path / `--repo` conventions). If it does not exist, skip.
   - Branch on verdict per contract §restore 判定. **plan resume caller-side asymmetry**: `conflict` は警告して無視し通常 resume を続行（壊れた補助ファイルが正常 resume を止めない）。Orphan checkpoint（status.md に cycle_id 一致なし）は `stale` 相当扱い。
   - Resume は read-only — checkpoint は削除しない。`superseded` のみ user 確認付きで削除**提案**する（auto-delete は禁止）。

3. **Confirm readiness**
   ```
   📋 Current Session Loaded!

   Cycle: {cycle-id}
   Feature: {feature-name}
   Phase: {phase}
   Plan: .agents/artifacts/plans/{cycle-id}_{feature-slug}.md

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
   cat .agents/artifacts/status.md
   ```

2. **Determine new phase**
   - 🟡 Planning → 🟡 In Progress (when starting implementation)
   - 🟡 In Progress → 🟢 Completed (when cycle done)
   - Work interrupted mid-way (user pausing, not done): keep the current phase as-is (no transition, no archive)

3. **Update .agents/artifacts/status.md**
   - Update Current Session phase
   - If completed:
     1. Archive the session to `.agents/artifacts/session-history.md` (add as first row in table format)
     2. If `.agents/artifacts/session-history.md` does not exist, create it with headers
     3. Remove Completed entries from Session History in status.md
     4. Clear Current Session
   - Update "Last Updated" timestamp
   - The "Completed" timestamp is the current time at the moment this update is executed (obtained via the `date` command) — never estimate or backdate it to when the user believes they finished

4. **Exit condition — checkpoint if leaving work dirty** (secondary trigger; primary is handoff save). Per shared contract [../shared/references/checkpoint-pattern.md](../shared/references/checkpoint-pattern.md).

   - Clean commit で終わるなら書かない。
   - `git status --porcelain=v1` が non-empty で終わるなら、**セッション最後の書き込み**として skeleton を生成する（他の tracked file 編集を全部確定させた後 — 生成後の編集は fingerprint を stale にする）:
     `python3 skills/shared/scripts/checkpoint.py skeleton --repo . --cycle-id {cycle_id} --owner manual-session --written-at $(date -Iseconds) --output`
   - 生成後、LLM が `## decision`（plan からの逸脱 1 文, なければ "none"）と `## next`（次の一手 1 個）を埋める。`## evidence` は観測コマンド + タイムスタンプ必須。機械フィールドと詳細は契約側。

5. **Confirm update**
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
4. **Commit** - Use `claude-skills:commit` to commit changes

No heavy review processes. Keep the tempo fast and development flow smooth.

## File Organization

```
.agents/artifacts/
├── status.md                           # Auto-managed status tracker
├── session-history.md                  # Completed sessions archive (auto-managed)
└── plans/                              # All implementation plans
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
- If you discover out-of-scope issues during investigation, record them with `/claude-skills:issue-create` and continue with the plan
- If the problem's root cause is unclear before planning, suggest running `/claude-skills:investigate` first for a read-only, lightweight investigation
