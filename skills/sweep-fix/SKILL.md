---
name: sweep-fix
description: A find-one-fix-all skill that analyzes code in a user-specified range to detect problems, converts each problem into a searchable pattern, sweeps the whole codebase for it (Grep / ast-grep / LSP), removes false positives through context verification, and then fixes every matching site in one pass. Use when the user says "sweep-fix", "sweep the fix outward", "find and fix the same problem elsewhere", "fix everything wrong in this range", or "clear out the similar problems". Pass the target range as an argument (a file, a directory, a glob, or a function name), plus any dimension you want it to focus on.
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
Phase 5: REPORT  — structured report, then delete intermediate files
```

## Phase 0: SCOPE — Fix the Target Scope

1. Parse from `$ARGUMENTS` the target scope (file / directory / glob / function name) and, if present, the aspect to focus on (e.g. "error handling", "null safety")
2. When no scope is specified:
   - **Interactive mode**: present the user with choices and confirm the target scope
   - **headless / Auto mode**: do not guess a scope and continue. Report that the target scope is unspecified and abort (a whole-codebase scan with no scope is codebase-review's territory)
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
4. **When there are zero problems (the early-exit path)**: report that no problem was detected in the specified range and finish normally. Do not manufacture findings
   - Do not create intermediate files (if you already created them, delete them with `rm -rf .claude/tmp/sweep-fix`)
   - The report is not Phase 5's full version but an abbreviated one — the "problems detected" section plus the basis of the analysis — printed in the conversation
   - No fix happened, so the verification gate (running tests) is unnecessary. "nothing to verify because nothing changed" suffices
5. Save the problem list: **before creating the directory, check whether the intermediate-file location is ignored by the VCS** (`git check-ignore -q .claude/tmp/sweep-fix`. If the check itself cannot be run, treat the state as unknown and handle it the same as not-ignored). Then run `mkdir -p .claude/tmp/sweep-fix` and write `.claude/tmp/sweep-fix/problems.json`
   - **When it is not ignored**: do not move the location, and do not edit the project's ignore settings on your own (rewriting the user's repository setup is outside this skill's scope). Proceed as is and **state in the report that the intermediate files are visible to the VCS at that path**. Whether to add an ignore entry is the user's call
   - The point of the check is not to change where the files go. It is so that Phase 4-3 does not misreport them as an unintended change, and so that leftovers surviving a refused deletion in Phase 5 do not get swept into the user's next commit unnoticed

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
   - **Exclude the intermediate-file location `.claude/tmp/sweep-fix/` from this comparison.** It is this skill's own workspace, not a fix target. When Phase 1 found the location is not ignored, it also shows up in `git status` — do not report it as an unintended change, and do not delete it here (Phase 5 owns the deletion)
4. **Do not commit**. The user commits with `/claude-skills:commit` (this skill's responsibility ends at the fix)

## Phase 5: REPORT — Structured Report

Print a report in the conversation with the structure below, then delete the intermediate files (`rm -rf .claude/tmp/sweep-fix`).

**The order is a requirement, not a preference: delete only after the report has been printed.** `.claude/tmp/sweep-fix/verdicts.json` holds the only record of each verdict's basis, so the FALSE_POSITIVE exclusion reasons (section 4) and the UNCERTAIN decision material (section 5) must already be transcribed into the report before anything is deleted. Delete first and they are unrecoverable.

**When the deletion is refused or fails** (a permission gate, a mount constraint): do not force it through by another route. State the surviving path in the report and finish normally — the run counts as complete. The leftovers are inert intermediate files, not an unfinished fix.

**This exit is open only to a deletion that was actually attempted and refused — it is not a licence to skip the attempt.** Reporting leftovers without having run the deletion violates this phase, however confidently you predict the refusal. When the leftovers survive **and** Phase 1 found the location is not ignored by the VCS, they will surface in the user's `git status` and can be swept into their next commit: state that in the report too, and ask them to delete the path by hand or add an ignore entry.

```
══════════════════════════════════════
SWEEP-FIX REPORT
══════════════════════════════════════

## 1. The problems detected (the specified range: {scope})

| ID | Severity | Problem | The original site |
|----|--------|------|--------|

## 2. The results of the sweep search

| Problem ID | Search tool | Candidates | CONFIRMED | FALSE_POSITIVE | UNCERTAIN |
|--------|-----------|--------|-----------|----------------|-----------|

## 3. The sites fixed

{the list of file:line and a summary of each change}

## 4. The sites excluded (FALSE_POSITIVE)

{the list of file:line and the reason for exclusion — why it looks alike textually yet is not a problem}

## 5. Held for judgment (UNCERTAIN)

{file:line, plus the material the user needs in order to judge}

## 6. Verification evidence

- Tests: {the command run and its result. If not run, state explicitly that no test command was detected}
- diff: {a summary of git diff --stat}
- Intermediate files: {deleted / if deletion was attempted and refused, the remaining path and the reason. If the location was outside the VCS ignore rules, say so and ask for manual deletion or an ignore entry}
```

## Rationalization Guard

| Excuse | Reality |
|--------|------|
| "The candidates are obviously the same problem, so skip verification" | Textual similarity does not imply identical context. No exceptions |
| "I can judge it from the excerpt" | A verdict reached without reading the surrounding context from the file is a guess. The guard condition lives outside the excerpt |
| "Too many UNCERTAIN makes this useless, so promote them to CONFIRMED" | The damage from one wrong fix exceeds ten held-back items. fail-safe is the specification |
| "Narrow the search pattern and verification becomes unnecessary" | A narrowed search only increases false negatives. Searching wide and narrowing by verification is the design |
| "There are no tests, so skip the verification gate" | If no test is detected, state "not detected" in the report. Do not skip it silently |
| "There are many sites to fix, so bulk-replace with sed" | Adapting to each site's context is Phase 4's responsibility. Mechanical replacement destroys context |
| "The intermediate-file deletion was refused, so remove it by another route" | Bypassing a refused deletion is forbidden. Record the surviving path in the report and finish |
| "Delete the intermediate files first to keep the workspace clean, then write the report" | verdicts.json is the only record of the verdict bases. Deleting before transcription destroys the evidence |
| "The deletion gets refused in this environment anyway, so report the leftovers without trying" | The exit for a refusal belongs to a deletion that was attempted. Predicting a refusal is not attempting it |
| "The intermediate files show up in `git status`, so they are an unintended change" | The intermediate-file location is this skill's own workspace and is excluded from the Phase 4-3 comparison. Report it as an ignore-status finding, not as a stray fix |
| "The intermediate files are not ignored, so add them to .gitignore / move the location" | Rewriting the user's repository setup is outside this skill's scope. Report it and leave the decision to them |

## Red Flags — Signs the Skill Is Not Being Followed

- Phase 4 editing has begun without passing through Phase 3
- The FALSE_POSITIVE count stays at 0 while a large number of candidates all become CONFIRMED (verification is suspected of being hollow)
- The exclusion reasons and verdict bases are not recorded
- The report has no UNCERTAIN section (holds are suspected of being swept away)
- `git diff --stat` shows more changed files than the fix-target list
- Parallel agents were launched for a single problem (over-orchestration)
