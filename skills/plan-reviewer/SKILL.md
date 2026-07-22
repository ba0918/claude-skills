---
name: plan-reviewer
description: 実装計画を7観点（実現可能性・セキュリティ・パフォーマンス/メモリ・アーキテクチャ・網羅性・代替手法・UI/UX）で徹底レビューし、信頼スコアで判定する。「計画をレビュー」「plan review」「計画を確認」「実装計画をチェック」「プランレビュー」で起動。計画作成後の品質ゲートとして使用。
---

# Plan Reviewer

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Quality gate that deeply reviews implementation plans from 7 expert perspectives before implementation begins.

## Progress Checklist

```
plan-review Progress:
- [ ] Identify and load latest plan file
- [ ] Gather project context
- [ ] Execute 7-dimension review (UI/UX conditionally; parallel mode adds Codex second opinion)
- [ ] Integrate results and score (including Codex findings)
- [ ] Output review report
- [ ] Branch decision (PASS/WARN/BLOCK)
```

## Workflow

### Step 1: Identify Latest Plan File

Find the most recent plan file from `.agents/artifacts/plans/`. If a specific file is provided as an argument, use that instead.

```bash
ls -t .agents/artifacts/plans/*.md 2>/dev/null | head -1
```

Read the full contents of the plan file. If the status is anything other than Planning, display a warning (reviewing an in-progress or completed plan is of limited value).

### Step 2: Gather Project Context

**Read the actual files** mentioned in the plan to verify consistency between the plan's descriptions and the real codebase.

Sources to collect:
- Files planned for modification (verify existence + understand current contents)
- `CLAUDE.md` (project root — project rules)
- `.claude/review-rules.md` (project-specific review rules, if present)
- `docs/ARCHITECTURE.md` (architecture principles, if present)
- `docs/SECURITY.md` (security requirements, if present)

**Important**: Always verify that line numbers and code snippets in the plan match the actual code. Any discrepancies should be flagged as Feasibility issues.

**Missing optional sources**: `.claude/review-rules.md`, `docs/ARCHITECTURE.md`, and `docs/SECURITY.md` are all optional. When absent, continue the review using `CLAUDE.md` + the generic checklists in [review-dimensions.md](references/review-dimensions.md); do not block. Note the absence once in the final report (e.g. `Project-specific review rules: not present (falling back to CLAUDE.md + generic checklist)`).

### Step 2.5: UI/UX Review Trigger Detection

Scan the plan content for UI/UX signals. If ANY of the following are detected, include Review 7 (UI/UX) in the parallel review:

Match keywords by meaning, not by surface form: when the plan is written in Japanese or another language, treat equivalent terms and translations (e.g. "component" ⇔ 「コンポーネント」, "button" ⇔ 「ボタン」) as the same signal.

**Strong signals (any one triggers):**
- Keywords: "UI", "UX", "component", "screen", "page", "button", "form", "modal", "frontend", "ユーザー確認", "accessibility", "a11y"
- File extensions in affected files: `.tsx`, `.jsx`, `.vue`, `.svelte`, `.css`, `.scss`, `.html`

**Weak signals (2+ required to trigger):**
- Keywords: "display", "layout", "style", "output", "format", "message", "error message", "progress"

**Override:** If `.claude/review-rules.md` contains `ui_ux_review: always`, always include. If `ui_ux_review: never`, always skip. Invalid values fall back to default `auto`.

If no signals detected and no override, skip Review 7.

**When Review 7 is skipped**, the final dimension table must omit the UI/UX row entirely (do not render it as N/A). Note the skip once near the top of the report (e.g. `UI/UX Review: SKIPPED (no UI/UX signals detected)`). See [output-format.md](references/output-format.md) for the canonical rule.

**When Review 7 is triggered**, note the activation once near the top of the report in the symmetric form: `UI/UX Review: TRIGGERED (detected: <list of signals>)`. List up to 4 representative signals (keywords or file extensions); do not dump every match. The dimension table includes the UI/UX row as normal.

### Step 3: Execute 7-Dimension Parallel Review + Codex Second Opinion

Launch up to **7 reviews + 1 Codex agent in parallel** (Review 7: UI/UX is conditional — see Step 2.5). Launch each review as an exploratory or general-purpose subagent — reviews have no mechanical verification gate (a missed finding passes through silently), so run them on a high-capability model. Launch the Codex agent in parallel as the Codex second opinion.

**Result file relay**: Each parallel review agent (and the Codex agent) must write its result to a file per the [delegation result relay](../shared/references/orchestration-patterns.md), not return it in a conversational reply. This is because a measured reachability problem exists where verdicts from reviews launched downstream never reach the aggregator and the flow stalls.

- **`{run_id}`**: identifier of the target plan. Use the Cycle ID at the top of the plan file (or the timestamp in the plan file name if absent)
- **`{dim}`**: short dimension name (`feasibility` / `security` / `performance` / `architecture` / `completeness` / `alternatives` / `uiux` / `codex`)
- Each review agent's delegation prompt must instruct it to write its verdict (score, verdict, findings as JSON or structured text) to `.agents/runtime/delegation/{run_id}_review-{dim}.md` **before sending its completion report**. The report message is merely a notification that the file was written
- The aggregator (this skill itself, Step 4) waits for all launched dimensions' result files per the [wait discipline](../shared/references/orchestration-patterns.md). On receiving a dimension's report or a wait notification, read that file. **Role-specific parameters**: if no new file arrives for 10 minutes after the last arrival, stop waiting and branch by optional/required — **optional = Codex** (`review-codex`): treat as unavailable and continue with what arrived; **required = launched Claude dimensions** (including UI/UX when triggered by Step 2.5; a triggered dimension counts as part of the core review): re-delegate once per dimension, and if still missing, record the gap and continue. In standalone launches (not under cycle, no parent watchdog), use the wait discipline's bounded re-check as the trigger path
- Delete result files after reading (single-use semantics)

**Execution fallback**: Parallel subagent launch is the recommended mode. Choose sequential mode when either holds: (a) you are running as a subagent yourself (regardless of whether you technically can spawn children), or (b) parallel subagent launch is unavailable in the environment. In sequential mode, run each dimension's checklist **inline in the same session**; the result file relay and wait discipline do not apply (the relay instructions in Step 3 and Step 4 are parallel-mode only); aggregate each dimension's verdict directly from the session context. Do not launch the Codex second opinion either — note the exact warning `⚠️ Codex second opinion unavailable — proceeding with existing review only.` (same as the Codex fallback in Step 3) and continue. Sequential execution must produce the same output format as parallel execution. Note the fallback once in the report (`Execution mode: sequential (<reason>)` — reason is `nested execution context` for (a), `subagent unavailable` for (b)).

Each review applies perspectives in the following priority order:
1. Project-specific rules from `.claude/review-rules.md` (highest priority)
2. Project-specific instructions from `AGENTS.md` / `CLAUDE.md`, plus the shared [Design Principles](../shared/references/design-principles.md)
3. Generic checklists from [review-dimensions.md](references/review-dimensions.md)

#### Reviews 1-7: Dimension Definitions

[review-dimensions.md](references/review-dimensions.md) is the canonical source for the full checklists and scoring criteria. Pass the relevant section (checklist + Confidence Score Criteria) into each dimension's delegation prompt. When reviewing inline, consult the same section per dimension.

| # | Dimension | Focus |
|---|-----------|-------|
| 1 | Feasibility | Existence of target files, line numbers, and APIs; environment constraints; estimate validity; implementation order |
| 2 | Security | Input validation, sensitive data handling, injection, SSRF and information leakage |
| 3 | Performance & Memory | Algorithmic complexity, resource leaks, memory retention, parallelization opportunities |
| 4 | Architecture & Design | Layer/dependency-direction rule violations; DRY, single responsibility, type safety; error-handling consistency |
| 5 | Completeness | Failure-path coverage, edge cases, backward compatibility, test plan, cleanup |
| 6 | Alternatives | Simpler alternatives, standard library / existing assets, complexity tradeoffs |
| 7 | UI/UX (conditional — see Step 2.5) | Actionable error messages, progress feedback, confirmation UI design, output consistency, information hierarchy, visual grouping, jargon leaks |

#### Review 8: Codex Second Opinion (always runs in parallel mode)

In parallel mode, launch the Codex second-opinion agent **in parallel** with Reviews 1-7 (do not launch it in sequential mode — see Execution fallback).

**Prompt to Codex agent:**
```
Review the following implementation plan comprehensively.

Plan file contents:
{plan file contents}

Point out problems, oversights, and alternatives from these angles:
1. Design issues (architecture, dependencies, extensibility)
2. Implementation oversights (edge cases, error handling, security)
3. Better alternative approaches

Output format — list each finding as:
- severity: critical / important / minor
- task: related task number ("general" if unclear)
- title: one-line summary
- description: details
- suggestion: proposed fix

Respond in the language the plan is written in.
```

Like the other dimensions, the Codex agent must write the findings list to `.agents/runtime/delegation/{run_id}_review-codex.md` **before sending its completion report** (the report is merely the notification).

**Codex security constraint**: Pass only the plan file contents. Never pass source code.

**Fallback**: If the Codex agent errors or times out:
```
⚠️ Codex second opinion unavailable — proceeding with existing review only.
```
Continue with the existing 7-dimension results only.

Common patterns: [../shared/references/codex-integration.md](../shared/references/codex-integration.md)

### Step 4: Integrate Results and Score

In parallel mode, collect and read every dimension's result file `.agents/runtime/delegation/{run_id}_review-{dim}.md` following the wait discipline and role-specific parameters defined in Step 3 (10-minute cutoff, optional/required branching, single re-delegation). In sequential mode, aggregate each dimension's verdict directly from the session context.

Aggregate confidence scores (0-100) from each review and determine the overall verdict.

**Integrating Codex results:**
- If the Codex agent succeeded, add its findings to the 7-dimension results
- Deduplicate: skip findings that point at the same task and same problem as an existing review
- Prefix Codex-specific findings with `[Codex]` and include them in WARN/BLOCK decisions according to severity
- Codex findings do not affect the 7 dimensions' score calculation (display as an independent section)

Output format: [output-format.md](references/output-format.md)

| Max Score | Verdict | Action |
|-----------|---------|--------|
| 80-100 | BLOCK | Modify plan before starting implementation |
| 50-79 | WARN | Review warnings, modify plan if necessary |
| 0-49 | PASS | OK to start implementation |

> BLOCK / WARN / PASS here are the score-band dialect of the shared severity scale —
> see [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md)
> §スコアバンド用法（plan-reviewer 方言）. Do not introduce a separate severity system.

### Step 5: Output Review Report

Output the final summary containing:

1. Table showing each dimension's score and verdict
2. Details of BLOCK/WARN items (task number, issue, fix suggestion)
3. List of positives (good points)
4. Recommended actions

### Step 6: Branch Decision

#### PASS (max score 49 or below)
→ Display "No major issues found in the plan. OK to start implementation"

#### WARN (max score 50-79)
→ Display warning list and confirm with user:
  1. Acknowledge warnings and start implementation
  2. Modify the plan

#### BLOCK (max score 80 or above)
→ Display BLOCK item details and fix suggestions:
  "Critical issues detected. The plan should be modified before starting implementation"

## Prohibited Actions

- Implementing code (only provide review perspectives)
- Making findings based on non-existent files or APIs (always verify against actual code)

## Important Notes

- When called standalone, do not directly edit the plan file (only present review results)
- When called from `claude-skills:plan-refine`, the refine side is responsible for edits

## References

- Checklist details: [review-dimensions.md](references/review-dimensions.md)
- Output format: [output-format.md](references/output-format.md)
