---
name: sweep-fix
description: ユーザ指定範囲のコードを分析して問題を検出し、各問題を検索可能なパターンに変換してコードベース全体へ横展開検索（Grep / ast-grep / LSP）、文脈検証で偽陽性を除去したうえで該当箇所を一括修正する find-one-fix-all 型スキル。「sweep-fix」「横展開修正」「同様の問題を探して直して」「この範囲の問題を全部直して」「似た問題を一掃して」で起動。引数に対象範囲（ファイル / ディレクトリ / glob / 関数名）と、あれば着目したい観点を指定する。
---

# Sweep Fix

Do not let a problem found in the specified scope end at "fixed in one place". Fix every instance of the same kind across the whole codebase.
A find-one-fix-all workflow: **local discovery → generalize into a pattern → sweep the whole codebase → verify the context → fix in bulk**.

### Differentiation from Other Skills

- **vs investigate**: investigate is read-only and fixes nothing. sweep-fix actually fixes the sites that pass verification
- **vs codebase-review / attack-review**: the review skills have a fixed whole-codebase scope and stop at a report. sweep-fix starts from a local scope the user names and propagates only the problems it found there
- **vs iterate**: iterate assumes the user brings the problem (a fix instruction) with them. sweep-fix includes the discovery phase itself
- **vs systematic-debugging**: debugging chases the root cause of a known symptom. sweep-fix explores a scope for problems with no symptom reported

## Governing Principles

1. **Textual similarity does not imply identical context** — a candidate found by the sweep is not a fix target until it passes context verification (Phase 3)
2. **When in doubt, do not fix (fail-safe)** — leave any site judged UNCERTAIN unfixed and hand it to the user with the material needed to decide
3. **Search wide, fix narrow** — prevent misses (false negatives) with a wide search in Phase 2, and prevent wrong fixes (false positives) with the verification in Phase 3. Do not mix the two responsibilities

## Flow

```
Phase 0: SCOPE   — fix the target scope
Phase 1: ANALYZE — detect problems in the specified scope
Phase 2: SWEEP   — generalize into patterns and sweep the whole codebase (read-only)
Phase 3: VERIFY  — verify context, eliminate false positives ★ where the quality is decided
Phase 4: FIX     — fix CONFIRMED sites only + verification gate
Phase 5: REPORT  — structured report, then delete intermediate files (in that order)
```

## Phase 0: SCOPE — Fix the Target Scope

1. Parse from `$ARGUMENTS` the target scope (file / directory / glob / function name) and, if present, the aspect to focus on (e.g. 「エラーハンドリング」「null 安全性」)
2. When no scope is specified:
   - **Interactive mode**: present the user with choices and confirm the target scope
   - **headless / Auto mode**: do not guess a scope and continue. Report 「対象範囲が未指定」 and abort (a whole-codebase scan with no scope is codebase-review's territory)
3. Confirm that the specified paths exist (`ls` / list the files). Abort with an error immediately if they do not

> Do not create the intermediate-file location `.claude/tmp/sweep-fix/` at this point. Create it at the moment the first file is saved (the problem list in Phase 1) — so that finishing early with zero problems leaves no litter.

## Phase 1: ANALYZE — Detect Problems in the Specified Scope

Analyze the code in the specified scope and build a problem list.

1. **Decide the execution form**:
   - Scope of **10 files or fewer**: analyze directly in the main context
   - Scope of **11 files or more**: delegate to a single subagent (state a high-capability model explicitly. Review and discovery work has no verification gate, so do not put it on a cheap model — see the model tiers in [orchestration-patterns.md](../shared/references/orchestration-patterns.md))
2. **Severity classification**: tag each problem with a severity (BLOCK / WARN / INFO) from [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md)
   - On a borderline case (it reads as either BLOCK or WARN, etc.), **round up** and record the basis for the call in one line. Severity does not change the fix flow (it only affects what triggers the continue-confirmation in Phase 4), so do not spend time on borderline calls
3. **Information every problem must carry**:
   - A description of the problem and the site (`file:line`)
   - Why it is a problem (the basis. If it is a guess, say so)
   - The proposed fix (the direction of the code change)
   - **Generalizability** — is this problem a structure that can occur elsewhere? If it is specific to that site (a spec local to it), drop it from the sweep
4. **When there are zero problems (the early-exit path)**: report 「指定範囲に問題は検出されなかった」 and finish normally. Do not manufacture findings
   - Do not create intermediate files (if you already created them, delete them with `rm -rf .claude/tmp/sweep-fix`)
   - The report is not Phase 5's full version but an abbreviated one — the "problems detected" section plus the basis of the analysis — printed in the conversation
   - No fix happened, so the verification gate (running tests) is unnecessary. 「変更なしのため検証対象なし」 suffices
5. Save the problem list: run `mkdir -p .claude/tmp/sweep-fix`, then write `.claude/tmp/sweep-fix/problems.json`

**When an aspect to focus on is specified**, prioritize that aspect, but still report an obvious BLOCK-class problem even if it falls outside the aspect (whether to fix it is the user's call).

## Phase 2: SWEEP — Generalize Into Patterns and Sweep the Whole Codebase

Convert each Phase 1 problem (the ones marked generalizable) into a searchable signature and collect candidate sites from across the whole codebase. **This phase is read-only. Fix nothing at all.**

1. **Pattern conversion**: following [references/pattern-extraction.md](references/pattern-extraction.md), pick a search strategy per problem:
   - Textual pattern → pattern search (regular expression)
   - Syntactic pattern → **ast-grep** (check it exists with `which ast-grep`. Fall back to pattern search if absent)
   - Symbol reference → the language server (LSP) (every use site of the same function or type. Fall back to pattern search if unavailable)
2. **Design the search wide**: keep the pattern deliberately loose so nothing slips through. Narrowing is Phase 3's responsibility
3. **Decide the execution form**:
   - **One** problem: search in the main context (or a single Agent). Do not over-orchestrate
   - **Multiple** problems: launch one sweep subagent per problem in parallel ([orchestration-patterns.md](../shared/references/orchestration-patterns.md) pattern 2)
     - **Required**: issue the multiple subagent calls **within a single message** (sequential turns serialize them)
     - **Required**: state a high-capability model explicitly for each subagent (prevents inheriting an expensive session model)
     - Each agent writes its results to `.claude/tmp/sweep-fix/{problem_id}_candidates.json` and returns only a summary (candidate count, file paths) to the main context
4. **Structure of the candidate list** (JSON):
   ```json
   {
     "problem_id": "P1",
     "pattern_used": "the pattern used for the search",
     "tool": "grep | ast-grep | lsp",
     "candidates": [
       { "file": "path/to/file", "line": 42, "excerpt": "the matching code fragment" }
     ]
   }
   ```
5. Include the original sites found in Phase 1 in the candidate list too (put them through Phase 3 verification as well. Verification also catches a call that was wrong at analysis time)

## Phase 3: VERIFY — Verify Context, Eliminate False Positives

**This phase decides the quality of this skill. Skipping or abbreviating it is forbidden.**

Judge every candidate site against the checklist in [references/context-verification.md](references/context-verification.md).

1. For each candidate, **actually read the file** to confirm the surrounding context (the whole function, the callers, the guard conditions). Do not judge from the excerpt alone
2. Return a three-way verdict:

   | Verdict | Meaning | Treatment |
   |------|------|------|
   | **CONFIRMED** | The same problem holds for the same reason | A fix target in Phase 4 |
   | **FALSE_POSITIVE** | It looks alike textually but is fine in context | Excluded. **Always record why it was excluded** |
   | **UNCERTAIN** | The context needed to judge is missing, or the validity is context-dependent | Not fixed. Listed in the report with the material to decide |

3. **Always attach the basis for a verdict**: record in one or two sentences "why the problem does or does not hold at this site". A CONFIRMED you cannot write a basis for is demoted to UNCERTAIN
4. **Promoting UNCERTAIN to CONFIRMED is forbidden** (fail-safe). The reverse (conservatively demoting CONFIRMED to UNCERTAIN) is allowed
5. When there are many candidates (more than 20), you may delegate verification to subagents (state a high-capability model explicitly). Even then, inject the criteria from context-verification.md into the subagent's prompt
6. Save the verdicts to `.claude/tmp/sweep-fix/verdicts.json`

## Phase 4: FIX — Apply the Fixes

Fix **CONFIRMED sites only**. Do not create any path by which a change touches a FALSE_POSITIVE or UNCERTAIN site.

1. Apply the Phase 1 proposed fix, adapted to each site's context (surrounding naming, idiom, comment density). Do not break the context with a mechanical bulk replace
2. When the fix is **BLOCK-class and spans more than 10 sites**, present the list of fixes and insert a continue-confirmation (interactive mode only. In headless, continue and emphasize it in the report)
3. **Verification gate** (conforming to [verification-gate.md](../shared/references/verification-gate.md)):
   - When the test command is known (detectable from CLAUDE.md / package.json / Makefile, etc.), run it and check the output
   - On test failure: if your fix caused it, fix it. If it is an unrelated pre-existing failure, distinguish it and state so in the report
   - Get the list of changed files with `git diff --stat` and confirm it matches the fix-target list (that no unintended file was changed)
4. **Do not commit**. The user commits with `/claude-skills:commit` (this skill's responsibility ends at the fix)

## Phase 5: REPORT — Structured Report

Print a report in the conversation with the structure below. **Delete the intermediate files only after the report has been printed** (`rm -rf .claude/tmp/sweep-fix`). The order is a requirement, not a preference: `verdicts.json` holds the only record of the basis for each verdict, so a deletion that runs before the FALSE_POSITIVE exclusion reasons and the UNCERTAIN decision material have been written into the report destroys them irrecoverably.

**When the deletion is refused or fails** (a permission gate, a mount constraint): state the surviving path in the report and finish normally. Do not force it through by another route (a different command, a broader permission). Leftover intermediate files are inert; a bypassed gate is not. This is the fallback for a deletion that was attempted and refused — not a licence to skip the attempt.

```
══════════════════════════════════════
SWEEP-FIX REPORT
══════════════════════════════════════

## 1. 検出した問題（指定範囲: {scope}）

| ID | 重大度 | 問題 | 元箇所 |
|----|--------|------|--------|

## 2. 横展開検索の結果

| 問題ID | 検索ツール | 候補数 | CONFIRMED | FALSE_POSITIVE | UNCERTAIN |
|--------|-----------|--------|-----------|----------------|-----------|

## 3. 修正した箇所

{file:line と変更概要の一覧}

## 4. 除外した箇所（FALSE_POSITIVE）

{file:line と除外理由の一覧 — なぜ字面が似ていて問題にならないのか}

## 5. 判断保留（UNCERTAIN）

{file:line と、ユーザが判断するために必要な材料}

## 6. 検証エビデンス

- テスト: {実行コマンドと結果。未実行なら「テストコマンド未検出」と明記}
- diff: {git diff --stat の要約}
```

## Rationalization Guard

| Excuse | Reality |
|--------|------|
| "The candidates are obviously the same problem, so skip verification" | Textual similarity does not imply identical context. No exceptions |
| "I can judge it from the excerpt" | A verdict reached without reading the surrounding context from the file is a guess. The guard condition lives outside the excerpt |
| "Too many UNCERTAIN makes this useless, so promote them to CONFIRMED" | The damage from one wrong fix exceeds ten held-back items. fail-safe is the specification |
| "Narrow the search pattern and verification becomes unnecessary" | A narrowed search only increases false negatives. Searching wide and narrowing by verification is the design |
| "There are no tests, so skip the verification gate" | If no test is detected, state 「未検出」 in the report. Do not skip it silently |
| "There are many sites to fix, so bulk-replace with sed" | Adapting to each site's context is Phase 4's responsibility. Mechanical replacement destroys context |
| "The intermediate-file deletion was refused, so remove it another way" | Leftover intermediate files are not a defect. Bypassing a permission gate is. Record the surviving path in the report and finish |

## Red Flags — Signs the Skill Is Not Being Followed

- Phase 4 editing has begun without passing through Phase 3
- The FALSE_POSITIVE count stays at 0 while a large number of candidates all become CONFIRMED (verification is suspected of being hollow)
- The exclusion reasons and verdict bases are not recorded
- The report has no UNCERTAIN section (holds are suspected of being swept away)
- `git diff --stat` shows more changed files than the fix-target list
- Parallel agents were launched for a single problem (over-orchestration)
