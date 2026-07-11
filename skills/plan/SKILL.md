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

Required information:

1. **Feature name** - What are we implementing?
2. **Brief description** - What is the goal?
3. **Type** - New feature / Enhancement / Bug fix / Refactoring

**When to skip asking:**

- If the user's initial request already contains all three (explicitly or unambiguously inferable), extract them and skip asking.
- Under Auto mode / headless invocation (e.g. called from `issue-cycle`, `cycle`), never block on questions — infer from available context and proceed.
- Otherwise, ask the user. Keep questions concise; avoid overwhelming with too many at once.

Record what was inferred vs. what was asked so the user can correct it.

### Phase 3: Create Plan Document

**File path:** `.agents/artifacts/plans/{timestamp}_{feature-slug}.md`

**CRITICAL**: Plan files MUST be created under `.agents/artifacts/plans/` directory. Do NOT use `docs/cycles/` or any other directory. This constraint applies regardless of how this skill is invoked (directly, via issue-cycle, or any other caller).

**Feature slug rules:**
- Convert spaces to hyphens
- Lowercase
- Remove non-alphanumeric characters except hyphens
- Collapse repeated hyphens; trim leading/trailing hyphens
- Example: "Markdown Hot Reload" → "markdown-hot-reload"

**Non-ASCII input (Japanese, Chinese, Korean, etc.):**

The slug MUST end up as `[a-z0-9-]+` only. For non-ASCII feature names, convert to English before applying the rules above:

1. **Translate by meaning** (preferred): extract the core concept from the feature name and user's description. Align with existing naming in the project if there is a related term.
   - Example: 「モックアップ比較ツール」 → `mockup-diff-tool` (aligned with existing `mockup-diff` skill)
   - Example: 「ユーザー認証機能」 → `user-authentication`
2. **Romanize** (fallback): if the term is a proper noun or brand with no English equivalent, use Hepburn-style romanization.
   - Example: 「あずき餡」 → `azuki-an`
3. **Ask the user** (last resort): if neither translation nor romanization yields a clear slug (ambiguous meaning, multiple valid translations), ask the user for a preferred English slug. Do NOT fall through to an empty or garbled slug.

Apply the ASCII rules above to the converted string. Record the original name verbatim in the plan document's `# {Feature Name}` header and the status.md `Feature` column so meaning is preserved.

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

2.5. **Restore execution-state checkpoint (if any)**

   Checkpoints are **auxiliary information** during plan resume. Follow the shared contract
   [../shared/references/checkpoint-pattern.md](../shared/references/checkpoint-pattern.md)
   (the contract is authoritative for verdict tables, priorities, and security rules — no duplication here):

   - If `.agents/artifacts/plans/checkpoints/{cycle_id}.md` **exists**, run:
     `python3 {checkpoint.py path} classify --repo {project root} --file .agents/artifacts/plans/checkpoints/{cycle_id}.md`
     and branch on the output verdict and exit code. If it does not exist, skip and continue normal resume.
     `{checkpoint.py path}` is relative to the skill distribution location (in this repo: `skills/shared/scripts/checkpoint.py`;
     use an absolute path if outside the target project). Always specify `--repo` explicitly (`--repo .` if cwd is the project root).
     See the contract's "CLI invocation rules" for details.
   - **Branching**:
     - `valid` (exit 0): Present the checkpoint's `decision` / `next` as the starting point for restoration. Label
       `evidence` as **historical (past observation)** and present `verify_on_restore` as **display-only**
       (do not auto-execute). The verification-gate is never skipped, even when valid.
     - `stale` (exit 10): Treat narrative as reference only. Prompt to reconstruct state from the current diff.
     - `superseded` (exit 11): HEAD has advanced. **Propose deletion** of the checkpoint (with user confirmation —
       **never auto-delete**). If the output contains a `dirty_overlap:` line, note "overlap with current dirty set"
       (absence of the line means no overlap — do not recompute).
     - `degraded` (exit 12): Present that nothing beyond dirty set and HEAD should be trusted (not normally emitted in v1).
     - `conflict` (exit 13, parse / semantic): **Warn and ignore, then continue normal resume**
       (a broken auxiliary file must never block a normal resume — caller-side asymmetry).
   - **Edge cases**:
     - **No active session** / no matching Current Session in status.md: if the cycle_id is known,
       the checkpoint path can still be computed. Classify if the file exists.
     - **Orphan checkpoint** (checkpoint file exists but no matching cycle_id in status.md): warn and
       treat as `stale` equivalent (narrative is reference only).
   - Checkpoints are **never deleted** during resume (read-only). Deletion is only proposed for `superseded`.

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

4. **Exit condition — write an execution-state checkpoint if leaving work dirty**

   Status Update is a **secondary trigger** for checkpoint writing (the primary trigger is handoff save).
   Follow the shared contract [../shared/references/checkpoint-pattern.md](../shared/references/checkpoint-pattern.md)
   and evaluate the following after the update:

   - If `git status --porcelain=v1` is **non-empty** when ending the session (i.e., not finishing with a clean commit),
     generate a checkpoint skeleton:
     `python3 {checkpoint.py path} skeleton --repo {project root} --cycle-id {cycle_id} --owner manual-session --written-at $(date -Iseconds) --output`
     (see the contract's "CLI invocation rules" for path and `--repo` conventions — in this repo:
     `skills/shared/scripts/checkpoint.py` + `--repo .`)
   - **Checkpoint generation must be the last write of the session**: finalize all tracked file edits
     (status.md, etc.) **before** running skeleton. Editing files after generation immediately
     stales the fingerprint (only files under checkpoints/ are excluded).
   - After skeleton generation, the LLM fills in only 2 narrative sentences (`## decision` = 1 sentence on
     deviation from plan / `## next` = 1 next action). `## evidence` requires observed commands + timestamps
     (e.g., `Observed 01:25: <cmd> exited 0`).
   - Machine fields (`dirty_files` / `dirty_fingerprint` / `base_head`) are generated by the script from git.
     Never write them manually. `dirty_files` has passed through `secret_detect.mask_secrets`.
   - If the session ends with a clean commit, **do not write** a checkpoint (no checkpoint on success). Existing
     checkpoints naturally expire when HEAD advances (do not delete them).
   - **v1 limitation**: checkpoints are not written for sessions that end without going through an explicit
     workflow (sudden interruption / /clear). See the contract's v2 scope.

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
