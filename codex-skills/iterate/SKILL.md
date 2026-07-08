---
name: iterate
description: cycle 完了後の追加指示を、サイズ適応型の軽量改善ループで実行する。修正・機能追加どちらにも対応。「iterate」「追加修正」「ここ直して」「これも追加して」「もうちょっと改善して」で起動。cycle よりも軽く、直接作業よりも品質を担保する中間的なワークフロー。
---

# Iterate

Skill that auto-determines task size for additional instructions after a cycle, then runs the appropriate improvement loop.

## Flow Overview

```
Additional instruction → Scope analysis → Size judgment ─→ Small → Implement → Light review → Done
                                                         └→ Large → Propose to user ─→ Continue → Implement → Thorough review → Done
                                                                                       └→ Plan → Suggest $plan
```

## Phase 0: Acquire Context

1. Identify the latest plan file
   ```bash
   ls -t docs/plans/*.md 2>/dev/null | grep -v _result | head -1
   ```
2. Load context using the following fallback chain:
   - **Plan file exists** → Read it to understand what has already been implemented. No warning.
   - **Plan file not found, `docs/status.md` exists** → Read `docs/status.md` to infer current project state. Display:
     ```
     ⚠️ No plan file found. Using docs/status.md as fallback context.
     ```
   - **Neither exists** → Try `git log --oneline -10` and `git diff HEAD~3 --stat`. If `HEAD~3` cannot be resolved (e.g., fresh repo with fewer than 4 commits), degrade stepwise: `HEAD~1` → `HEAD` → `git log --oneline -10` only. Display based on what was retrieved:
     - git log + diff successful:
       ```
       ⚠️ No plan file or status.md found. Using partial context from git history.
       ```
     - git log only (no diff available):
       ```
       ⚠️ No plan file or status.md found. Only git log available — proceeding with minimal context.
       ```
     - git log also fails (non-git dir or empty repo):
       ```
       ⚠️ No plan file, status.md, or git history found. Proceeding with instructions only.
       ```
3. **Detect previous iterate runs**: Check the plan file (if loaded) for existing `## Additional Changes` sections. If found, use **all** sections as cumulative context (not just the latest) so that consecutive iterate calls build on the complete change history rather than only the most recent increment.
4. Get the user's additional instructions from `$ARGUMENTS`

## Phase 1: Scope Analysis

Use `spawn_agent` to investigate:

1. Compare the additional instructions against existing code and estimate the impact scope
2. List files that need to be changed
3. Determine whether new files need to be created
4. Determine whether design decisions are needed

See [references/scope-criteria.md](references/scope-criteria.md) for detailed criteria.

## Phase 2: Size Judgment and Branching

### Pre-check: Consecutive Call Detection

Before size judgment, check if this is a consecutive iterate call within the same session by looking for `## Additional Changes` sections in the plan file (loaded in Phase 0, Step 3).

**If no plan file was loaded in Phase 0** (fallback path was used), skip this pre-check entirely and treat as 1st call. Display a single-line notice so the skipped check is visible in the log:
```
ℹ️ Consecutive call detection skipped (no plan file loaded).
```

Count `N = (number of ## Additional Changes sections found) + 1` (current call included).

- **N = 2 (2nd call)** → Display a notice but proceed normally:
  ```
  ℹ️ This is the 2nd iterate call in this session.
  ```
- **N >= 3 (3rd+ call)** → Present a cumulative Large warning as a conversational-turn question (list the options and ask the user to reply by number). In headless/exec contexts where no reply is available, do not auto-continue — halt on the safe side and suggest `$plan`:
  ```
  ⚠️ Cumulative iterate detected ({N}th call this session)
  Multiple consecutive iterate calls may indicate the task exceeds iterate's scope.

  Options:
  1. Continue with iterate (cumulative changes will be tracked)
  2. Create a plan via $plan (recommended for complex changes)
  ```
  - User selects "1" → Proceed to normal size judgment below
  - User selects "2" → Suggest running `$plan` and exit
  - No reply (headless/exec) → Halt and suggest `$plan` (do not auto-continue)

### If Small

Display:
```
── Scope: Small ──
Affected files: {file_list}
Estimated change size: {estimate}
→ Executing via lightweight loop
```

Proceed to Phase 3.

### If Large

Present the decision as a conversational-turn question (list the options and ask the user to reply by number). In headless/exec where no reply is available, do NOT auto-execute — halt on the safe side and suggest `$plan` (consistent with the Security posture):

```
── Scope: Large ──
Affected files: {file_list}
Estimated change size: {estimate}
Reason for Large judgment: {reasons}

Options:
1. Execute via iterate (with thorough review)
2. Create a plan via $plan (recommended)
```

- User selects "1" → Proceed to Phase 3 (Large mode)
- User selects "2" → Suggest running `$plan` and exit
- No reply (headless/exec) → Halt without implementing and suggest `$plan`

## Phase 3: Implementation

Launch an implementation agent via `spawn_agent`.

Instructions to the agent:
- Implement the additional instructions
- Follow existing code style and conventions
- Comply with AGENTS.md rules
- Reference review-rules.md if it exists (`.codex/review-rules.md` → `.claude/review-rules.md` → `review-rules.md`)
- Follow [tdd-contract.md](../shared/references/tdd-contract.md): write tests FIRST (RED), implement to pass (GREEN), then refactor
- Avoid testing anti-patterns: never assert on mocks' existence, never add test-only methods to production code, never mock without understanding the dependency's side effects
  - **Exception — non-executable changes** (documentation only: README/CHANGELOG/comments/markdown with no behavior change): tests do not apply. Instead, the implementation agent must (a) state explicitly that tests are skipped because the change has no executable behavior, and (b) still run the existing test suite to confirm nothing breaks.
  - **Config files are NOT automatically non-executable**: `tsconfig.json` strict-mode flips, `package.json` dep/script changes, linter rule changes, CI workflow edits all affect runtime or build behavior → tests apply. Only pure content edits (e.g., `description` field in `package.json`) qualify as non-executable.
- Run existing tests after implementation and confirm all pass

## Phase 4: Review

See [references/light-review.md](references/light-review.md) for detailed review perspectives.

### If Small

Launch **1 review agent** via `spawn_agent`:
- Review from 2 perspectives: Security + Implementation Quality
- Use review-rules.md as additional criteria if it exists
- Do NOT issue PASS without test execution evidence
  - **Exception — non-executable changes** (documentation only, as defined in Phase 3): the gate is satisfied by (a) confirming the existing test suite still passes, or (b) explicit declaration that no executable code is affected. The review agent must state which path applies.
- Classify findings as BLOCK / WARN / PASS

### If Large (user chose to continue)

Launch **1 review agent** via `spawn_agent`:
- Review from 4 perspectives: Security + Implementation Quality + Architecture + Completeness
- Use review-rules.md as additional criteria if it exists
- Do NOT issue PASS without test execution evidence
  - **Exception — non-executable changes** (documentation only, as defined in Phase 3): the gate is satisfied by (a) confirming the existing test suite still passes, or (b) explicit declaration that no executable code is affected. The review agent must state which path applies.
- Classify findings as BLOCK / WARN / PASS

### Processing Review Results

- **BLOCK found** → Fix and re-review (max 2 iterations)
  - **If BLOCK remains after 2 iterations**: Halt without completion. Display:
    ```
    ⚠️ BLOCK not resolved after 2 fix iterations. Unresolved findings:
    - {finding 1}
    - {finding 2}
    Recommendation: escalate to user — consider $plan for a broader design pass,
    or address manually before retrying iterate.
    ```
    Exit without executing Phase 5 or Phase 6. **Never complete with unresolved BLOCK.**
- **WARN only** → Apply fixes and complete
- **All PASS** → Complete as-is

## Phase 5: Traceability

1. Append an "Additional Changes" section to the latest plan file.
   - **If no plan file was loaded in Phase 0** (fallback path was used), skip **this step only** (not step 2). Display:
     ```
     ⚠️ Traceability skipped: no plan file found. Changes are recorded in git commits only.
     ```
   - Step 2 (commit) always runs regardless of plan file presence — the commit itself is the minimum traceability record.

   **`{datetime}` format**: Use `YYYY-MM-DD HH:MM` (24h, local time). Example: `2026-04-21 14:30`.

```markdown

## Additional Changes ({datetime})

### Instructions
{User's additional instructions}

### Changes Made
- {Changed files and summary}

### Review Results
- Security: {PASS|WARN}
- Implementation Quality: {PASS|WARN}
```

2. Execute `$commit` to commit changes

## Phase 6: Completion Report

```
══════════════════════════════════════
ITERATE COMPLETE
Scope: {Small|Large}
Files changed: {N}
Review: {PASS|WARN}
Plan updated: {plan_file_path}
══════════════════════════════════════
```

## Important Rules

- **Judge size by actual code impact** — Do not be swayed by the user's expressions like "just a small thing"
- **Large judgment** — In interactive contexts, always present the options as a conversational-turn question. In headless/exec contexts where no reply is available, do not auto-continue to implementation — halt on the safe side and suggest `$plan` (never proceed to a destructive change without confirmation)
- **If unexpected impact is discovered during implementation, halt and report**. Return path when halted in Phase 3:
  1. If the newly discovered impact pushes the scope from Small → Large, re-enter Phase 2 with the updated scope and present the Large options to the user as a conversational-turn question. In headless/exec where no reply is available, halt and suggest `$plan` (do not auto-continue).
  2. If the impact is ambiguous or crosses module boundaries in unforeseen ways, escalate to the user directly (do not auto-resume). Suggest `$plan` as the fallback.
  3. Never silently continue past a halt.
- **Headless operation**: Confirmation branches are presented as conversational-turn questions only when an interactive channel is available. **Codex の `request_user_input` は Plan mode 限定（default/exec 不可）のため使わない。** In headless/exec, do not auto-continue on Large judgment or halt escalations — halt on the safe side and suggest `$plan`
- **BLOCK findings must be resolved** — Never complete with unresolved BLOCK items (see Phase 4 "Processing Review Results" for the 2-iteration cap behavior)
