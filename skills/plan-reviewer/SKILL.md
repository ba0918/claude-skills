---
name: plan-reviewer
description: 実装計画を7観点（実現可能性・セキュリティ・パフォーマンス/メモリ・アーキテクチャ・網羅性・代替手法・UI/UX）で徹底レビューし、信頼スコアで判定する。「計画をレビュー」「plan review」「計画を確認」「実装計画をチェック」「プランレビュー」で起動。計画作成後の品質ゲートとして使用。
---

# Plan Reviewer

Quality gate that deeply reviews implementation plans from 7 expert perspectives before implementation begins.

## Progress Checklist

```
plan-review Progress:
- [ ] Identify and load latest plan file
- [ ] Gather project context
- [ ] Execute 7-dimension parallel review (UI/UX conditionally)
- [ ] Integrate results and score
- [ ] Output review report
- [ ] Branch decision (PASS/WARN/BLOCK)
```

## Workflow

### Step 1: Identify Latest Plan File

Find the most recent plan file from `docs/plans/`. If a specific file is provided as an argument, use that instead.

```bash
ls -t docs/plans/*.md 2>/dev/null | head -1
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

### Step 2.5: UI/UX Review Trigger Detection

Scan the plan content for UI/UX signals. If ANY of the following are detected, include Review 7 (UI/UX) in the parallel review:

**Strong signals (any one triggers):**
- Keywords: "UI", "UX", "component", "screen", "page", "button", "form", "modal", "frontend", "AskUserQuestion", "accessibility", "a11y"
- File extensions in affected files: `.tsx`, `.jsx`, `.vue`, `.svelte`, `.css`, `.scss`, `.html`

**Weak signals (2+ required to trigger):**
- Keywords: "display", "layout", "style", "output", "format", "message", "error message", "progress"

**Override:** If `.claude/review-rules.md` contains `ui_ux_review: always`, always include. If `ui_ux_review: never`, always skip. Invalid values fall back to default `auto`.

If no signals detected and no override, skip Review 7.

### Step 3: Execute 7-Dimension Parallel Review

Launch up to **7 reviews in parallel** (Review 7: UI/UX is conditional — see Step 2.5). Each review runs as an Explore agent or general-purpose agent.

Each review applies perspectives in the following priority order:
1. Project-specific rules from `.claude/review-rules.md` (highest priority)
2. Design Principles from `CLAUDE.md`
3. Generic checklists from [review-dimensions.md](references/review-dimensions.md)

#### Review 1: Feasibility

- Verify affected files exist, check line number accuracy
- Verify APIs/libraries used actually exist (recommend checking latest docs via Context7)
- Implementation environment constraints (runtime limitations, platform compatibility, etc.)
- Estimate validity
- Implementation order dependencies

#### Review 2: Security

- External input validation and sanitization
- Safe handling of sensitive data (no logging, no plaintext storage)
- Defense against injection attacks (command, SQL, path, etc.)
- SSRF, information leakage risks
- Security section from `.claude/review-rules.md` (if present)

#### Review 3: Performance & Memory

- O(n^2)+ algorithms, unnecessary copies/allocations
- Resource leaks (file handles, listeners, timers not being released)
- Minimize memory retention duration
- Serialization of parallelizable operations
- Runtime-specific resource constraints

#### Review 4: Architecture & Design

- Violations of layer structure defined in CLAUDE.md
- Violations of dependency direction rules defined in CLAUDE.md
- Project-specific design rules defined in `.claude/review-rules.md`
- DRY principle, single responsibility, type safety
- Error handling consistency

#### Review 5: Completeness

- Error handling for all failure paths
- Edge cases (empty input, large input, Unicode, multibyte)
- Backward compatibility, rollback capability
- Test plan existence and coverage
- Resource cleanup, documentation updates

#### Review 6: Alternatives

- Existence of simpler approaches to achieve the same goal
- Possibility of using standard library alternatives
- Leveraging existing libraries/utilities
- Future extensibility
- Performance vs. code complexity tradeoffs

#### Review 7: UI/UX (conditional — only if Step 2.5 detected UI/UX signals)

- Error messages are actionable (what happened, why, how to fix)
- Progress feedback for long operations
- AskUserQuestion option design (Hick's Law, clear labels, defaults)
- Output format consistency with existing skills
- Cancel/abort path design
- Information hierarchy (summary first, details on demand)
- Visual grouping for scannability
- No jargon leak in user-facing text

### Step 4: Integrate Results and Score

Aggregate confidence scores (0-100) from each review and determine the overall verdict.

Output format: [output-format.md](references/output-format.md)

| Max Score | Verdict | Action |
|-----------|---------|--------|
| 80-100 | BLOCK | Modify plan before starting implementation |
| 50-79 | WARN | Review warnings, modify plan if necessary |
| 0-49 | PASS | OK to start implementation |

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
