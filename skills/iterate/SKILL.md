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
                                                                                       └→ Plan → Suggest /claude-skills:plan-create
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

Use the Agent tool (subagent_type: Explore) to investigate:

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
- **N >= 3 (3rd+ call)** → Trigger cumulative Large warning via AskUserQuestion:
  ```
  ⚠️ Cumulative iterate detected ({N}th call this session)
  Multiple consecutive iterate calls may indicate the task exceeds iterate's scope.

  Options:
  1. Continue with iterate (cumulative changes will be tracked)
  2. Create a plan via /claude-skills:plan-create (recommended for complex changes)
  ```
  - User selects "1" → Proceed to normal size judgment below
  - User selects "2" → Suggest running `/claude-skills:plan-create` and exit

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

Use AskUserQuestion to let the user decide:

```
── Scope: Large ──
Affected files: {file_list}
Estimated change size: {estimate}
Reason for Large judgment: {reasons}

Options:
1. Execute via iterate (with thorough review)
2. Create a plan via /claude-skills:plan-create (recommended)
```

- User selects "1" → Proceed to Phase 3 (Large mode)
- User selects "2" → Suggest running `/claude-skills:plan-create` and exit

## Phase 3: Implementation

Launch an implementation agent via the Agent tool (general-purpose). Model by Phase 2 size judgment: `model: "sonnet"` if **Small** (small scope + the verification gate make the cheaper tier safe), `model: "opus"` if **Large**. See [orchestration-patterns.md](../shared/references/orchestration-patterns.md) § Model Tiering.

Instructions to the agent:
- Implement the additional instructions
- Follow existing code style and conventions
- Comply with CLAUDE.md rules
- Reference `.claude/review-rules.md` if it exists
- Follow `skills/shared/references/tdd-contract.md`: write tests FIRST (RED), then minimal implementation (GREEN), then refactor (REFACTOR)
  - **Exception — non-executable changes** (documentation only: README/CHANGELOG/comments/markdown with no behavior change): TDD does not apply. Instead, the implementation agent must (a) state explicitly that TDD is skipped because the change has no executable behavior, and (b) still run the existing test suite to confirm nothing breaks.
    - **Config files are NOT automatically non-executable**: `tsconfig.json` strict-mode flips, `package.json` dep/script changes, linter rule changes, CI workflow edits all affect runtime or build behavior → TDD applies (write a test proving the new behavior, or at minimum a regression test confirming build/test pipeline still passes). Only pure content edits (e.g., `description` field in `package.json`) qualify as non-executable.
- Avoid testing anti-patterns defined in `rules/testing-anti-patterns.md`
- Run existing tests after implementation and confirm all pass

## Phase 4: Review + Codex Second Opinion

See [references/light-review.md](references/light-review.md) for detailed review perspectives.

**Before dispatching the review/Codex agents**: the iterate main context captures the diff once so both agents see the same input.
```bash
git diff HEAD           # uncommitted changes, to be committed shortly
# or
git diff <base>..HEAD   # if the implementation agent already committed
```
Store the diff output and inline it into both agent prompts. If the diff exceeds ~50KB, substitute `git diff --stat` + a list of changed files + selected critical hunks instead. Never hand raw source files to Codex — diff only.

### If Small

Launch **2 agents in parallel** (issue both Agent tool calls in a single message):
1. **Review agent** (general-purpose, `model: "opus"`):
   - Review from 2 perspectives: Security + Implementation Quality
   - Use `.claude/review-rules.md` as additional criteria if it exists
   - Apply `skills/shared/references/verification-gate.md` Gate Function: do NOT issue PASS without test execution evidence
     - **Exception — non-executable changes** (documentation only, as defined in Phase 3): Gate Function is satisfied by (a) confirming the existing test suite still passes, or (b) explicit declaration that no executable code is affected. The review agent must state which path applies.
   - Classify findings as BLOCK / WARN / PASS
2. **Codex agent** (`subagent_type: "codex:codex-rescue"`, Bash tool only):
   - Provide the change diff (`git diff`) and the user's instructions directly in the prompt
   - If the diff exceeds ~50KB, pass a summarized diff (file list + `git diff --stat` + key hunks) instead of the full diff to avoid token overflow
   - Ask for design issues, edge cases, and alternative approaches
   - Security constraint: pass diff only, not raw source files

### If Large (user chose to continue)

Launch **2 agents in parallel** (issue both Agent tool calls in a single message):
1. **Review agent** (general-purpose, `model: "opus"`):
   - Review from 4 perspectives: Security + Implementation Quality + Architecture + Completeness
   - Use `.claude/review-rules.md` as additional criteria if it exists
   - Apply `skills/shared/references/verification-gate.md` Gate Function: do NOT issue PASS without test execution evidence
     - **Exception — non-executable changes** (documentation only, as defined in Phase 3): Gate Function is satisfied by (a) confirming the existing test suite still passes, or (b) explicit declaration that no executable code is affected. The review agent must state which path applies.
   - Classify findings as BLOCK / WARN / PASS
2. **Codex agent** (`subagent_type: "codex:codex-rescue"`, Bash tool only):
   - Provide the change diff (`git diff`) and the user's instructions directly in the prompt
   - If the diff exceeds ~50KB, pass a summarized diff (file list + `git diff --stat` + key hunks) instead of the full diff to avoid token overflow
   - Ask for design issues, edge cases, and alternative approaches
   - Security constraint: pass diff only, not raw source files

### Codex Result Integration

- If Codex agent succeeds: merge Codex findings with `[Codex]` prefix into the review results (deduplicate against existing findings)
- If Codex agent fails: display `⚠️ Codex second opinion unavailable — proceeding with existing review only.` and continue with review agent results only
- Codex findings contribute to WARN/BLOCK judgment. Classify Codex findings using [../shared/references/severity-and-verdicts.md](../shared/references/severity-and-verdicts.md):
  - **Critical** severity (exploitable security hole, data loss, contract violation affecting callers) → BLOCK
  - **High** severity (likely bug, wrong output under common inputs) → BLOCK
  - **Medium** (suboptimal but correct) → WARN
  - **Low** (style, naming, minor refactor hints) → informational only

Common patterns: [../shared/references/codex-integration.md](../shared/references/codex-integration.md)

### Processing Review Results

- **BLOCK found** → Fix and re-review (max 2 iterations)
  - **If BLOCK remains after 2 iterations**: Halt without completion. Display:
    ```
    ⚠️ BLOCK not resolved after 2 fix iterations. Unresolved findings:
    - {finding 1}
    - {finding 2}
    Recommendation: escalate to user — consider /claude-skills:plan-create for a broader design pass,
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
- Codex Second Opinion: {PASS|WARN|unavailable}
```

2. Execute `claude-skills:commit` via the Skill tool to commit changes

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
- **Do not block on Large judgment** — Always present options to the user
- **If unexpected impact is discovered during implementation, halt and report**. Return path when halted in Phase 3:
  1. If the newly discovered impact pushes the scope from Small → Large, re-enter Phase 2 with the updated scope and present the Large options to the user via AskUserQuestion.
  2. If the impact is ambiguous or crosses module boundaries in unforeseen ways, escalate to the user directly (do not auto-resume). Suggest `/claude-skills:plan-create` as the fallback.
  3. Never silently continue past a halt.
- **Headless operation**: Do not prompt for confirmation except for user choice on Large judgment and halt escalations
- **BLOCK findings must be resolved** — Never complete with unresolved BLOCK items (see Phase 4 "Processing Review Results" for the 2-iteration cap behavior)
