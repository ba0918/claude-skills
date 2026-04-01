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
   - **Plan file exists** → Read it to understand what has already been implemented
   - **Plan file not found, `docs/status.md` exists** → Read `docs/status.md` to infer current project state
   - **Neither exists** → Run `git log --oneline -10` and `git diff HEAD~3 --stat` to derive context from recent commits
   - If all fallbacks fail, proceed with the user's instructions only (no prior context). Display:
     ```
     ⚠️ No plan file or status found. Proceeding with instructions only.
     ```
3. **Detect previous iterate runs**: Check the plan file (if loaded) for existing `## Additional Changes` sections. If found, use the latest one as cumulative context so that consecutive iterate calls build on prior changes rather than starting from scratch.
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

**If no plan file was loaded in Phase 0** (fallback path was used), skip this pre-check entirely and treat as 1st call.

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

Launch an implementation agent via the Agent tool (general-purpose).

Instructions to the agent:
- Implement the additional instructions
- Follow existing code style and conventions
- Comply with CLAUDE.md rules
- Reference `.claude/review-rules.md` if it exists
- Add tests for changes that require testing
- Run existing tests after implementation and confirm all pass

## Phase 4: Review + Codex Second Opinion

See [references/light-review.md](references/light-review.md) for detailed review perspectives.

### If Small

Launch **2 agents in parallel** (issue both Agent tool calls in a single message):
1. **Review agent** (general-purpose):
   - Review from 2 perspectives: Security + Implementation Quality
   - Use `.claude/review-rules.md` as additional criteria if it exists
   - Classify findings as BLOCK / WARN / PASS
2. **Codex agent** (`subagent_type: "codex:rescue"`, Bash tool only):
   - Provide the change diff (`git diff`) and the user's instructions directly in the prompt
   - Ask for design issues, edge cases, and alternative approaches
   - Security constraint: pass diff only, not raw source files

### If Large (user chose to continue)

Launch **2 agents in parallel** (issue both Agent tool calls in a single message):
1. **Review agent** (general-purpose):
   - Review from 4 perspectives: Security + Implementation Quality + Architecture + Completeness
   - Use `.claude/review-rules.md` as additional criteria if it exists
   - Classify findings as BLOCK / WARN / PASS
2. **Codex agent** (`subagent_type: "codex:rescue"`, Bash tool only):
   - Provide the change diff (`git diff`) and the user's instructions directly in the prompt
   - Ask for design issues, edge cases, and alternative approaches
   - Security constraint: pass diff only, not raw source files

### Codex Result Integration

- If Codex agent succeeds: merge Codex findings with `[Codex]` prefix into the review results (deduplicate against existing findings)
- If Codex agent fails: display `⚠️ Codex second opinion unavailable — proceeding with existing review only.` and continue with review agent results only
- Codex findings contribute to WARN/BLOCK judgment (e.g., a critical Codex finding triggers BLOCK)

Common patterns: [../shared/references/codex-integration.md](../shared/references/codex-integration.md)

### Processing Review Results

- **BLOCK found** → Fix and re-review (max 2 iterations)
- **WARN only** → Apply fixes and complete
- **All PASS** → Complete as-is

## Phase 5: Traceability

1. Append an "Additional Changes" section to the latest plan file.
   - **If no plan file was loaded in Phase 0** (fallback path was used), skip this step and display:
     ```
     ⚠️ Traceability skipped: no plan file found. Changes are recorded in git commits only.
     ```

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
- **If unexpected impact is discovered during implementation, halt and report**
- **Headless operation**: Do not prompt for confirmation except for user choice on Large judgment
- **BLOCK findings must be resolved** — Never complete with unresolved BLOCK items
