---
name: review-testing
description: テストスイート自体の欠陥検出力・契約検証・安定性と testing-anti-patterns 違反を評価する focused read-only レビュー。「テスト品質レビュー」「テストの品質を見て」「テストアンチパターン検出」「このテストは意味があるか」「テストの欠陥検出力」「安全網として機能しているか」「review-testing」で起動。依存やセキュリティではなくテスト自体の健全性が対象。
---

# Review: Testing Quality

A focused review that evaluates a test suite from the viewpoint of "does it function as a safety net in its own right".
Given that the codebase's design principles put Testability first, test quality is the most important thing to verify, yet
`codebase-review` structurally excludes `*.test.*` from its scope. This skill fills that gap.

**In scope**: test files and their correspondence to the production code they are supposed to protect. Test code is read as first-class input.
**Out of scope**: the health of dependency libraries (→ `review-deps`), attack scenarios (→ `attack-review`),
quality scoring of the production code itself (→ `codebase-review`).

**Scope boundary**: production code is read in order to extract "which contracts the tests ought to protect".
Even when you find an implementation bug there, do not switch to a standalone production-code finding or to a code-review verdict such as `CHANGES_REQUESTED`.
Report it only when no test captures that bug, and then as a hole in contract verification / defect-detection power.

## Contract (declare this first)

- **read-only**: never edit files, rewrite tests, or apply automatic fixes. Emit the findings as findings and
  hand the fixing over to an existing fix-oriented workflow (tdd / iterate / sweep-fix, etc.).
  **Writing into the directory under review is also forbidden.** When a test, coverage, or mutation runner may create a cache,
  snapshots, coverage output, a DB, or logs under the target, run it only against a throwaway copy outside the target or in an
  isolated environment whose write destination can be pinned outside the target. If isolation is impossible, do not run the dynamic
  evaluation and fall back to `unsupported`. Compliance is judged by mechanically confirming that the target tree is unchanged before and after the run.
- **Do not produce an overall score**: never emit a score of the "test quality: 82 points" kind. The deliverables are findings and a
  [coverage ledger](../shared/references/coverage-ledger.md). An overall score hides what could not be measured.
- **Three-way verdict**: verify every finding with the
  CONFIRMED / FALSE_POSITIVE / UNCERTAIN values of
  [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md). Demote to UNCERTAIN any CONFIRMED whose grounds you cannot write down.
- **Always record the evaluated range in a ledger**: report the areas you looked at as `reviewed`, the areas you deliberately left out as `skipped`,
  the areas you cannot see because tooling does not support them as `unsupported`, and the areas where the evidence is too thin to conclude as `inconclusive`,
  in the form defined by [coverage-ledger.md](../shared/references/coverage-ledger.md).
  Even with zero findings, do not conflate "no problems" with "not looked at".

## Three-layer evaluation (plus an auxiliary layer)

Evaluate test quality in three independent core layers (1-3), with readability (4) as an auxiliary layer.
For the detailed criteria of each layer, see
[references/evaluation-criteria.md](references/evaluation-criteria.md).

1. **Defect-detection power (P0)**: do the tests react to a change that breaks an important contract?
   If a meaningful mutant (a modification that changes a contract) survives, that is a finding. Do not turn the mutation score into a number.
2. **Contract verification (P0)**: is there a corresponding test for each public API, state transition, permission boundary, and failure path?
   Coverage percentage does not enter the score; use it only as an aid for exploring unreached areas.
3. **Stability of the safety net (P1)**: evidence implicit dependencies on time, randomness, ordering, and the network (the seeds of flakiness).
4. **Readability (P2)**: can the specification (the What) be read from the test names (the information-placement principle)?

## Anti-pattern enforcement

The enforcement specification that converts the five iron laws of [testing-anti-patterns.md](../shared/references/testing-anti-patterns.md) into detection predicates, evidence requirements, and three-way verdicts is owned by
[references/anti-pattern-detection.md](references/anti-pattern-detection.md).
It runs in the order candidate extraction (grep / AST) → data-flow confirmation → three-way verdict, and each predicate is paired with
positive / negative [fixtures](references/fixtures/) so that regressions can be checked.

## Handling retrofitted TDD (avoiding false positives)

"Was TDD followed this time" and "are the tests effective now" are separate axes. Inferring retrofitted TDD from git history alone is weak evidence that
collapses under squash / rebase, so cap it at UNCERTAIN. With a RED/GREEN execution log from cycle it can be promoted to
CONFIRMED. Do not penalize a regression test added later for an existing bug (that would discourage adding to the safety net).

## Workflow

1. **Determine the target**: from the arguments (a directory / glob / diff), identify the set of test files and their corresponding production code.
   If there is not a single test, record the searched range as `reviewed` in the ledger and check against the production code's public contracts whether
   "absence of tests" should become a finding of the contract-verification layer. Do not fabricate quality findings for tests that do not exist.
2. **Extract candidates**: gather candidates mechanically with the detection predicates of anti-pattern-detection.md (searching with shell commands, AST traversal).
3. **Context verification**: verify each candidate through its data flow and call sites, and assign CONFIRMED / FALSE_POSITIVE / UNCERTAIN.
   At larger scale, delegate the per-layer analysis (defect-detection power / contract verification / stability) to subagents and aggregate,
   saving only the result files to a **scratch area outside the target tree** (this conserves the main context).
4. **Three-layer evaluation**: evaluate each layer along evaluation-criteria.md and keep only the meaningful findings.
5. **Report**: emit findings plus the coverage ledger in the form defined by [references/report-template.md](references/report-template.md).

### Completion gate

Do not declare the review complete until all of the following hold.

- The findings in the report take test quality (or the absence of tests) as their subject, and are not standalone production-bug reports.
- Even with zero tests, there is a Coverage Ledger marking the searched range as `reviewed`, together with the result of checking against the public contracts.
- No code-review pass/fail verdict (`CHANGES_REQUESTED` and the like) and no overall score has been emitted.
- The target tree has been mechanically confirmed unchanged before and after the run.

## Security

- Adhere strictly to read-only (rewriting tests, updating snapshots, and running `--update`-style commands are forbidden).
- Do not transcribe secret values contained in test fixtures (tokens, keys, credentials) directly into the evidence for a finding.
- Even when running the tests is necessary, do so only where side effects on external APIs, persistent DBs, and the like can be cut off and the environment is a throwaway one outside the target.
  If safety cannot be confirmed, do not run them and mark the corresponding dynamic-evaluation area as `unsupported`.
