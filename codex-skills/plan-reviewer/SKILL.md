---
name: plan-reviewer
description: 実装計画を7観点で徹底レビューし信頼スコアで判定する。「plan review」「計画をレビュー」「計画を確認」で起動。引数に「refine」を含むと review → fix ループで計画を自動改善する。「plan refine」「計画を改善」で起動。
---

# Plan Reviewer

Quality gate that deeply reviews implementation plans from 7 expert perspectives before implementation begins.

## Workflow Selection

The first keyword in the argument determines the workflow:

- `refine` → **Refine Workflow** (review → fix loop)
- Other / None → **Review Workflow** (single review, default)

## Progress Checklist

```
plan-review Progress:
- [ ] Identify and load latest plan file
- [ ] Gather project context
- [ ] Execute 6-7 dimension parallel review (UI/UX conditionally)
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
- `AGENTS.md` (project root — project rules)
- review-rules.md (project-specific review rules — search `.codex/review-rules.md` → `.claude/review-rules.md` → `review-rules.md`)
- `docs/ARCHITECTURE.md` (architecture principles, if present)
- `docs/SECURITY.md` (security requirements, if present)

**Important**: Always verify that line numbers and code snippets in the plan match the actual code. Any discrepancies should be flagged as Feasibility issues.

### Step 2.5: UI/UX Review Trigger Detection

Scan the plan content for UI/UX signals. If ANY of the following are detected, include Review 7 (UI/UX) in the parallel review:

**Strong signals (any one triggers):**
- Keywords: "UI", "UX", "component", "screen", "page", "button", "form", "modal", "frontend", "request_user_input", "accessibility", "a11y"
- File extensions in affected files: `.tsx`, `.jsx`, `.vue`, `.svelte`, `.css`, `.scss`, `.html`

**Weak signals (2+ required to trigger):**
- Keywords: "display", "layout", "style", "output", "format", "message", "error message", "progress"

**Override:** If review-rules.md contains `ui_ux_review: always`, always include. If `ui_ux_review: never`, always skip. Invalid values fall back to default `auto`.

If no signals detected and no override, skip Review 7.

### Step 3: Execute 6-7 Dimension Parallel Review

Launch up to **7 reviews in parallel** (Review 7: UI/UX is conditional — see Step 2.5). Each review runs as a `spawn_agent`.

Each review applies perspectives in the following priority order:
1. Project-specific rules from review-rules.md (highest priority)
2. Design Principles from `AGENTS.md`
3. Generic checklists from [review-dimensions.md](references/review-dimensions.md)

#### Review 1: Feasibility

- Verify affected files exist, check line number accuracy
- Verify APIs/libraries used actually exist
- Implementation environment constraints (runtime limitations, platform compatibility, etc.)
- Estimate validity
- Implementation order dependencies

#### Review 2: Security

- External input validation and sanitization
- Safe handling of sensitive data (no logging, no plaintext storage)
- Defense against injection attacks (command, SQL, path, etc.)
- SSRF, information leakage risks
- Security section from review-rules.md (if present)

#### Review 3: Performance & Memory

- O(n^2)+ algorithms, unnecessary copies/allocations
- Resource leaks (file handles, listeners, timers not being released)
- Minimize memory retention duration
- Serialization of parallelizable operations
- Runtime-specific resource constraints

#### Review 4: Architecture & Design

- Violations of layer structure defined in AGENTS.md
- Violations of dependency direction rules defined in AGENTS.md
- Project-specific design rules defined in review-rules.md
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
- request_user_input option design (Hick's Law, clear labels, defaults)
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

---

## Refine Workflow

Review → fix loop that iteratively improves the plan until all dimensions PASS or the max iteration count is reached.

### Parameters

- First number in `$ARGUMENTS` (after `refine`): Max iterations (default: 3)
- File path in `$ARGUMENTS`: Target plan file (omit to auto-select latest from `docs/plans/`)

### Iteration 1 (Full Review)

1. Execute the **Review Workflow** above (Steps 1-6, full 6-7 dimension review)
   - Record the target file path for reuse in subsequent iterations
2. Result is all PASS → Done (go to Completion Report)
3. WARN/BLOCK found:
   a. Examine each finding and directly edit the plan file with `apply_patch` to fix
   b. Show diff of changes made
   c. Proceed to next iteration

### Iteration 2+ (Delta Review)

1. Re-review **only dimensions that were WARN/BLOCK** in the previous iteration
   - Pass the same target file path explicitly (do not rely on auto-selection)
   - Skip dimensions that already PASS (save context)
2. Result is all PASS → Done
3. Still WARN/BLOCK → Fix and continue

### Termination Conditions

- All dimensions PASS
- Max iteration count reached → Display remaining WARN/BLOCK list and exit

### Completion Report

Display to user:
- Number of iterations executed
- Summary of improvements made per iteration
- Final score and verdict for each dimension
- Remaining WARN/BLOCK list (if any)

---

## Prohibited Actions

- Implementing code (only provide review perspectives)
- Making findings based on non-existent files or APIs (always verify against actual code)

## Important Notes

- In **Review Workflow**: do not directly edit the plan file (only present review results)
- In **Refine Workflow**: directly edit the plan file to fix WARN/BLOCK findings

## References

- Checklist details: [review-dimensions.md](references/review-dimensions.md)
- Output format: [output-format.md](references/output-format.md)
