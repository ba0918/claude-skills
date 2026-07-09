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
- [ ] Execute 7-dimension parallel review + Codex second opinion (UI/UX conditionally)
- [ ] Integrate results and score (including Codex findings)
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

**Missing optional sources**: `.claude/review-rules.md`, `docs/ARCHITECTURE.md`, and `docs/SECURITY.md` are all optional. When absent, continue the review using `CLAUDE.md` + the generic checklists in [review-dimensions.md](references/review-dimensions.md); do not block. Note the absence once in the final report (e.g. `Project-specific review rules: not present (falling back to CLAUDE.md + generic checklist)`).

### Step 2.5: UI/UX Review Trigger Detection

Scan the plan content for UI/UX signals. If ANY of the following are detected, include Review 7 (UI/UX) in the parallel review:

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

最大 **7 レビュー + 1 Codex エージェントを並行起動**する（Review 7: UI/UX は条件付き — Step 2.5 参照）。各レビューは探索型または汎用のサブエージェントとして起動する — レビューには機械的検証ゲートがなく（見落とした指摘はそのまま通過する）、高性能モデルで実行する。Codex エージェントは Codex セカンドオピニオンとして並行起動する。

**Execution fallback**: サブエージェントの並行起動が推奨モード。サブエージェントが利用できない場合（例: 自身がサブエージェントとして実行中でさらなるサブエージェントを生成できない等）、各次元のチェックリストを**同一セッション内で逐次実行**する。逐次実行でも並行実行と同じ出力フォーマットを生成すること。フォールバックをレポートに 1 度記載する（`Execution mode: sequential (subagent unavailable)`）。

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
- ユーザー確認の選択肢設計（Hick's Law、明確なラベル、デフォルト値）
- Output format consistency with existing skills
- Cancel/abort path design
- Information hierarchy (summary first, details on demand)
- Visual grouping for scannability
- No jargon leak in user-facing text

#### Review 8: Codex Second Opinion (always runs)

Codex セカンドオピニオン・エージェントを Reviews 1-7 と**並行で**起動する。

**Prompt to Codex agent:**
```
以下の実装計画を包括的にレビューしてください。

計画ファイル内容:
{plan file contents}

以下の観点で問題点・見落とし・代替案を指摘してください:
1. 設計上の問題点（アーキテクチャ、依存関係、拡張性）
2. 実装の見落とし（エッジケース、エラーハンドリング、セキュリティ）
3. より良い代替アプローチ

出力フォーマット:
各指摘を以下の形式で列挙してください:
- severity: critical / important / minor
- task: 関連するタスク番号（不明なら "general"）
- title: 指摘の要約
- description: 詳細説明
- suggestion: 改善提案
```

**Codex セキュリティ制約**: 計画ファイルの内容のみを渡す。ソースコードは渡さない。

**フォールバック**: Codex エージェントがエラーまたはタイムアウトの場合:
```
⚠️ Codex second opinion unavailable — proceeding with existing review only.
```
既存 7 次元の結果のみで続行する。

共通パターンの詳細: [../shared/references/codex-integration.md](../shared/references/codex-integration.md)

### Step 4: Integrate Results and Score

Aggregate confidence scores (0-100) from each review and determine the overall verdict.

**Codex 結果の統合:**
- Codex エージェントが成功した場合、Codex の指摘を既存 7 次元の結果に追加する
- 重複排除: 既存レビューと同じタスク・同じ問題を指摘している場合はスキップ
- Codex 固有の指摘には `[Codex]` プレフィックスを付与し、severity に応じて WARN/BLOCK 判定に含める
- Codex の指摘は既存 7 次元のスコア計算には影響しない（独立セクションとして表示）

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
