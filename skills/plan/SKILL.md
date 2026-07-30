---
name: plan
description: Create timestamped implementation plans from brainstorm agreements. A plan is the record of agreed implementation steps — not a proposal document. Use when user requests (1) "make a plan", "create a plan", "design this feature" for creating new plans, or (2) "update status", "planning done", "implementation complete", "cycle done" for updating implementation progress, or (3) "resume", "continue from last time", "pick up where we left off" for loading the current session state.
---

# Plan

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Create implementation plans with timestamp-based filenames and automatic project status tracking. A plan is the record of agreed-upon implementation steps — not a proposal or approval document. Design and specification decisions are made in brainstorm; the plan captures how to implement them.

Both spec and plan are human-readable. The plan uses structured Markdown (numbered steps, file lists, test lists) that is readable by humans and consumable by LLMs. This ensures the human can verify "is that how you intend to implement it?" before cycle runs.

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

### Caller-supplied mode

When a caller passes **both** of the following parameters, the skill runs in
caller-supplied mode. Both must be present; a partial set is an error.

| Parameter | Meaning |
|-----------|---------|
| `output_path` | The exact repository-relative path for the plan file (e.g. `.agents/artifacts/plans/20260729_A_feature.md`) |
| `skip_status` | When true, do not read, create, migrate, or update `status.md` or `session-history.md` |

In caller-supplied mode:

- **Phase 1**: skip timestamp generation (the caller already embedded it in the path)
- **Phase 3**: write the plan to `output_path` exactly as given. Do not generate a
  timestamp, a slug, or a filename of your own. The `CRITICAL` constraint on the
  `.agents/artifacts/plans/` directory still applies — reject an `output_path` that
  points elsewhere
- **Phase 4**: skip entirely (no status.md or session-history.md updates)
- **Phase 5**: report the path the caller supplied, not a self-generated one

All other phases (requirements gathering, plan content, template) run unchanged.

When neither parameter is passed, every phase runs as specified below (the default
standalone mode). This is the existing behavior and is not affected.

### Phase 2: Gather Requirements

Determine the [execution context](../shared/references/execution-context.md) (interactive
or headless) if not already determined.

A feature name, a summary, and a type (new feature / modification / bug fix / refactor) are required. If they can be read clearly from the user input, proceed without asking. When something is missing, ask briefly in interactive mode; in Auto mode (headless), do not block — infer it from context.

State every inferred item explicitly in the final response, in a form the user can correct.

### Phase 3: Create Plan Document

**File path:** `.agents/artifacts/plans/{timestamp}_{feature-slug}.md`

**CRITICAL**: Plan files MUST be created under `.agents/artifacts/plans/` directory. Do NOT use `docs/cycles/` or any other directory. This constraint applies regardless of how this skill is invoked (directly, via issue-cycle, or any other caller).

**Feature slug**: `[a-z0-9-]+` only (standard URL slugification). For non-ASCII input (Japanese and the like), prefer a meaning-based translation and align it with related existing naming inside the project (skills, existing plans). Romanize (Hepburn) only proper nouns that resist translation, and ask the user when the meaning is ambiguous (falling back to an empty or garbled slug is forbidden). Keep the original feature name verbatim in the plan header `# {Feature Name}` and in the `Feature` column of status.md.

**Template:** See [references/plan-template.md](references/plan-template.md) for the full plan document structure.

**Key sections:**
- Overview and goals
- Architecture design (layer analysis, file structure)
- Implementation steps (numbered, with affected files)
- Test list (organized by layer)
- Security checklist
- Implementation steps with affected files

**Optional `Issue` field:**
When creating a plan from an issue (via `issue-plan` or `issue-cycle`), add `**Issue:** {issue_slug}` to the plan header. This field is used by `cycle` to auto-close the issue upon completion. If the plan is not issue-originated, omit this line.

**Optional `Spec` field:**
When a domain spec exists in `docs/spec/`, add `**Spec:** {path}` to the plan header. The plan references the spec but does not copy its content. The spec is the human-readable source of truth for what to build; the plan is the LLM-consumable instruction for how to build it. If no spec exists yet, omit this line.

**Spec auto-detection:** When `docs/spec/` exists and contains files, scan each file's content and match it against the plan's feature description. If a relevant spec is found, populate the `**Spec:**` field automatically. When called via `brainstorm-plan` with a CONVERGED exit contract, the spec path generated during wrap is available in the idea memo — use it directly instead of scanning. State the detected spec path in the plan creation output so the human can verify the link.

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
2. **Headless mode** (per the [execution context](../shared/references/execution-context.md)): default to **(b) archive as abandoned** without prompting. Log the archival action in the "Next Steps" output so the user can correct it if needed.

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

1. Run the cycle - `/claude-skills:cycle`
2. Or implement manually - "実装して" or "implement this"
3. Commit - "コミットして" (commit will handle it)

Design decisions are made in brainstorm, not here. Fast tempo! 🚀
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
   - Branch on the verdict per the contract §The restore decision. **plan resume caller-side asymmetry**: warn about `conflict` and then ignore it, continuing the normal resume (a broken auxiliary file must not stop a healthy resume). An orphan checkpoint (no matching cycle_id in status.md) is treated as equivalent to `stale`.
   - Resume is read-only — never delete the checkpoint. Only for `superseded` do you **propose** deletion with user confirmation (auto-delete is forbidden).

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

   - If the session ends on a clean commit, do not write one.
   - If the session ends with `git status --porcelain=v1` non-empty, generate the skeleton as the **last write of the session** (after every other tracked-file edit is finalized — an edit made after generation leaves the fingerprint stale):
     `python3 skills/shared/scripts/checkpoint.py skeleton --repo . --cycle-id {cycle_id} --owner manual-session --written-at $(date -Iseconds) --output`
   - After generation, the LLM fills in `## decision` (one sentence on the deviation from the plan, or "none") and `## next` (a single next move). `## evidence` requires an observed command plus a timestamp. The machine fields and the details belong to the contract.

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
- A plan is not a proposal — it records agreed implementation steps. Specification and design decisions belong in brainstorm, not in the plan
- A plan is human-readable. Write implementation steps, file lists, and test lists in structured Markdown that a human can scan to confirm the implementation approach before cycle runs
