---
name: refactor
description: Refactor finished code while preserving its behavior exactly, and sweep the improvement outward to similar code with context verification. It fully understands the user-specified scope (a file, a directory, a class name, or "the last N commits") and improves only the expression, presenting a proposal to file an issue rather than fixing any bug it happens to find. Use when the user says "refactor", "refactor this", "clean this up", "simplify this", "make it more readable", or "fix the similar code too". When the goal is fixing a bug, a defect, or a vulnerability, use sweep-fix instead, since this skill assumes behavior is preserved.
---

# Refactor

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Fully understand the code in the specified scope, then improve its expression **while preserving behavior completely**,
and propagate the improvement to similar code across the codebase with context verification.
The workflow: **understand → extract improvement candidates → sweep for similar code → verify context → behavior-preserving refactor → report**.

Where sweep-fix is a find-one-fix-all driven by a problem (a bug), refactor is driven by
behavior-preserving improvement of expression. A bug you find is **not fixed** — you present a proposed issue-creation command and leave it to the user.

## Iron Laws

```
1. Preserve behavior completely — only the expression changes. Inputs/outputs, side effects, error behavior, and ordering stay identical
2. Do not refactor code you do not understand — Chesterton's Fence
3. Do not fix a bug even when you find one — present a proposed issue-creation command and leave it to the user (do not mix it into the diff, do not create it automatically)
4. Do nothing if it is already clean — a no-op is a legitimate result
5. When in doubt, do not touch it — hand UNCERTAIN to the user. Do not APPLY where there is no means of proof (test / type check / probe)
```

## Differentiation from Other Skills

- **sweep-fix**: a find-one-fix-all driven by a problem (a bug, an anti-pattern), on the premise that **behavior changes**. refactor is premised on **behavior preservation**, and both its improvement catalog and its verification viewpoints are different (verifying a bug holds vs verifying behavior is preserved). Candidates rooted in correctness / security are not handled by refactor — send them to sweep-fix / issue
- **iterate**: a post-cycle improvement loop where the user brings the fix instructions. refactor performs the discovery of improvement candidates itself, from an analysis of the specified scope
- **investigate**: read-only analysis only. refactor goes as far as carrying out the improvement, in Phase 5
- **systematic-debugging**: aims at identifying and fixing the root cause of a bug. refactor does not lay a hand on bugs
- **simplify (a Claude Code built-in)**: a quality-only tidy-up of the most recent change diff. refactor targets a user-specified scope (existing code in general) and goes as far as sweeping, three-way verdicts, and proposing issue creation
- **codebase-review**: a fixed whole-codebase scan that stops at a report. refactor starts from a user-specified scope and goes as far as making the fix

## Conformance to Shared Contracts

- [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md): reference **only the definitions** of the three-way verdict (CONFIRMED / FALSE_POSITIVE / UNCERTAIN). refactor does not use severity (BLOCK / WARN / INFO)
- [verification-gate.md](../shared/references/verification-gate.md): pre-completion verification and the demand for evidence (the basis for the Phase 1 gate securing a means of verification and for the Phase 5 test evidence)
- [orchestration-patterns.md](../shared/references/orchestration-patterns.md): the basis for the subagent delegation thresholds in the read-only phases (pattern 7: research isolation)

> **Own your verification viewpoints**: sweep-fix's `context-verification.md` is a question list aimed at verifying that a bug holds, and behavior-preservation verification asks different questions. A lateral dependency on a sibling skill's private reference also creates coupling, so do not reference it. Use refactor's own [references/behavior-preservation-checks.md](references/behavior-preservation-checks.md). The **definitions** of the three-way verdict conform to the shared contract severity-and-verdicts.md.

## Flow

```
Phase 0: SCOPE      — interpret the scope and fix the targets (with a safety cap)
Phase 1: UNDERSTAND — fully understand the target code (Chesterton's Fence + secure a means of verification)
Phase 2: IDENTIFY   — enumerate and classify improvement candidates, and judge the gates
Phase 3: SWEEP      — sweep for similar code (read-only, range-limited)
Phase 4: VERIFY     — verify context, three-way verdict ★ where the quality is decided
Phase 5: APPLY      — behavior-preserving refactor, one improvement at a time + tests (outside the scope it is opt-in)
Phase 6: REPORT     — report the results + present proposed issue-creation commands for the bugs found
```

## Phase 0: SCOPE — Interpret the Scope and Fix the Targets

1. Interpret the scope from `$ARGUMENTS`:
   - File path / directory / glob / class name / function name
   - A git period expression ("the last 5 commits", "this week's changes" → expand to the set of target files with `git log --since=...` / `git diff HEAD~N --name-only`)
2. **Quote rigorously**: when a path or argument contains whitespace or shell metacharacters, always wrap it in quotes when assembling the command (`git diff HEAD~5 --name-only -- "src/my dir"`)
3. **With no argument**: present the changed files of the most recent commit (`git diff HEAD~1 --name-only`) as the default scope and confirm it
4. **Existence check**: confirm that the expanded target paths exist with `ls` / by listing files. If they do not exist, jump directly to the Report Phase with exit point "Phase 0 abort"
5. **Handling of test files**: even when scope expansion (a git period specification, etc.) includes test files, treat the tests **not as improvement targets but as the means of verification** (immutable. Same root as the Phase 5 rule "do not modify the tests")
6. **Safety cap**: when the expanded targets exceed **50 files**, do not press on — present a proposal for splitting the scope and confirm it with the user (preventing a runaway in total scope volume. Phase 5's Rule of 500 controls the size of a single improvement and is a separate layer)
7. **Gate: temporary-code judgment** — prototypes, throwaway scripts, and code slated for deletion (signals such as `TODO: remove` / `experimental` / `scratch` + confirmation with the user) are **excluded from the improvement targets** and reported as such (spending effort on temporary code is a waste of time). Because there is code that looks temporary but has become specified (a migration shim, etc.), **deletion and consolidation transformations are out of scope for the first version** — limit yourself to highly reversible transformations such as tidying names, extraction, and removing duplication

## Phase 1: UNDERSTAND — Fully Understand the Target Code

**Chesterton's Fence: do not break it until you understand why it was written this way.**

1. Read off the target code's responsibilities, inputs and outputs, side effects, error behavior, and edge cases
2. Confirm the callers and callees with pattern search / the language server (LSP) (grasping the behavioral contract)
3. Confirm the history with `git log --follow` / `git blame` ("why was it written this way" — possibly a performance measure, a platform constraint, or a past bug fix)
4. **Gate: insufficient understanding** — exclude anything you cannot answer for from the improvement targets, and record the reason for exclusion as `unknown_reason`:
   `no_history` / `dynamic_dispatch` / `public_api` / `generated_or_vendor` / `unclear_tests` (tests exist but their range and intent cannot be read) / `semantic_dependency` / `no_verification_means` (the means of verification itself — test, type check, probe, etc. — is absent. Use this term too for the exclusion and UNCERTAIN demotion by the next gate). **Do not simplify code you do not understand**
5. **Gate: securing a means of verification (provability of behavior preservation)** — confirm whether existing tests are present and what they cover:
   - When no test exists, propose adding a characterization test (a test that pins the current behavior), and if the user agrees, create and run it before proceeding
   - **In a headless run, agreement cannot be obtained, so do not generate a characterization test / probe on your own — drop those sites to UNCERTAIN / no-op** (test and probe are always treated alike by this gate). headless means any context where a confirmation or question to the user gets no response — via cycle, a subagent, an automation pipeline, and so on (the headless in Phase 5 is the same)
   - **Do not make a site an APPLY target when you can prepare none of** an existing test, a build, a type check, a lint, or a runnable characterization probe (drop it to UNCERTAIN or no-op). Claiming "behavior fully preserved" without a means of proof violates the verification-gate contract
   - A characterization test / probe created in Phase 1 is **immutable** from then on (include it in the Phase 5 rule "do not modify the tests")
6. **Delegation judgment**: when the scope exceeds **10 files**, delegate the UNDERSTAND read-only investigation to a read-only exploration subagent (orchestration-patterns.md pattern 7: research isolation. Preventing bloat of the main context)

## Phase 2: IDENTIFY — Enumerate and Classify Improvement Candidates

1. List candidates against the pattern table in [references/refactoring-catalog.md](references/refactoring-catalog.md) (deep nesting / overlong functions / nested ternaries / boolean flag arguments / generic names / what-comments / duplicated logic / dead code / worthless wrappers, etc.)
2. Classify each candidate into **four values**:

   | Class | Meaning | Treatment |
   |------|------|------|
   | `REFACTOR_CANDIDATE` | The expression can be improved while preserving behavior | A target from Phase 3 onward |
   | `BUG_FOUND` | Grounded in correctness / security / data loss / behavior mismatch | Presented as a proposed issue in Phase 6 (**not put into the improvement candidates**) |
   | `OUT_OF_SCOPE` | Temporary code, insufficient understanding, outside the scope | Excluded and reported |
   | `ALREADY_CLEAN` | Already simple and highly readable | Do nothing |

3. **The boundary rule with sweep-fix**: when a candidate's improvement value is grounded in correctness / security / data loss / behavior mismatch, it is not a refactor candidate but a `BUG_FOUND`. If fixing the bug is the goal, use sweep-fix
4. Apply the test "**can a new team member understand it faster than before?**" to each `REFACTOR_CANDIDATE`
5. **Gate: already-clean** — zero improvement candidates, or every candidate is "low value" → **finish with a no-op**. Report "already simple and highly readable" as a legitimate result (do not force an application). In this case no change occurs, so the verification gate (running tests) is **not mandatory** (running the existing tests once, read-only, to grasp the behavioral contract is not precluded). Skip Phases 3-5 and jump directly to the Report Phase with exit point "Early exit (no findings)"
6. **Gate: performance-critical** — a two-stage check:
   1. **Does the transformation change performance characteristics?** — determine whether evaluation order, call count, allocation, or computational complexity change. If none of these change (e.g. a rename, comment cleanup), the transformation is **performance-neutral** and passes the gate regardless of hot-path status
   2. **Hot-path check** (only when stage 1 answered "yes" or "indeterminate"): for a hot path, a benchmark target, or a site with a measurement comment, state that the "simpler version" may be slower, and do not rewrite it without measurement → **UNCERTAIN**. **When it is unclear whether it is a hot path, fall to UNCERTAIN as well** (completing the fail-safe)
   3. **When stage 1 itself is indeterminate** (cannot tell whether the transformation changes performance characteristics), fall to **UNCERTAIN** as well

## Phase 3: SWEEP — Sweep for Similar Code

**Read-only and range-limited. Fix nothing at all.**

1. Turn each `REFACTOR_CANDIDATE` from Phase 2 into a pattern and search for similar cases. Each improvement has an `improvement_id`, and records `origin` (the original site inside the Phase 0 scope) separately from `sweep_candidates` (similar sites outside the scope)
2. **Limit the search range**: **limit it to the same language and related directories** as the Phase 0 scope (a whole-repository similarity-* pass is heavy in a huge monorepo. Do not scan "the whole codebase" unconditionally)
3. **Choosing between detection tools** (details in [references/similarity-detection.md](references/similarity-detection.md)). The tools have different roles, so choose by the nature of the candidate and the language (this is not a pure staged fallback):
   - `similarity-ts` / `similarity-rs` (check existence with `which`): structural detection of duplicated blocks and code clones. **TS/JS/Rust only**
   - `ast-grep` (check existence with `which`): enumerate every instance of a known syntactic pattern
   - Pattern search (always available): a wide textual search. The fallback when the above are unusable
4. **Asymmetry in language coverage**: in languages similarity-* does not support (Python / Go / PHP / Dart, etc.) you fall back to textual search, which raises the false-positive risk. In unsupported languages, run the sweep conservatively. Record the tool used and the `fallback_reason` and put them in the REPORT
5. Search wide (preventing false negatives), and leave the fix decision to Phase 4 (separating the responsibilities of searching and verifying)
6. **Delegation judgment**: when the scope exceeds **10 files**, delegate SWEEP to a read-only subagent (state a high-capability model explicitly)

## Phase 4: VERIFY — Verify Context, Three-Way Verdict

**This phase decides the quality of this skill. Skipping or abbreviating it is forbidden.**

The definitions of the verdict values conform to the shared contract [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md) (CONFIRMED / FALSE_POSITIVE / UNCERTAIN).
For the verification viewpoints, use the question list in refactor's own [references/behavior-preservation-checks.md](references/behavior-preservation-checks.md).

1. Put **both** `origin` and `sweep_candidates` through verification. For each candidate, **actually read the file** to confirm the surrounding context (do not judge from the excerpt alone)
2. Judge with the questions in behavior-preservation-checks.md:
   - "Can the same transformation be applied safely to this site **while preserving behavior**?"
   - "Can the behavioral contract (inputs/outputs, side effects, error behavior, ordering) be kept identical?"
   - "Is the calling context of the same nature as the origin's?"
   - "Is there any trace of a deliberate difference (a comment, the history, a planned future branch)?"
   - "Is there any chance this is a hot path (UNCERTAIN if unclear)?"
3. Return a three-way verdict:

   | Verdict | Meaning | Treatment |
   |------|------|------|
   | **CONFIRMED** | The same transformation can be applied safely while preserving behavior | An APPLY candidate |
   | **FALSE_POSITIVE** | It resembles it on the surface but the context differs (inapplicable or unnecessary) | Excluded. **Always record why it was excluded** |
   | **UNCERTAIN** | The context needed to judge is missing, or applicability is context-dependent | Not fixed. Reported with the material to decide |

4. **Always attach the basis for a verdict**. A CONFIRMED you cannot write a basis for is demoted to UNCERTAIN
5. **fail-safe: when in doubt, do not touch it**. Drop "it looks the same on the surface but the context differs" (e.g. identically shaped duplicated code where one side has a comment about a planned future branch / one side is a hot path) to FALSE_POSITIVE or UNCERTAIN. **Promoting UNCERTAIN → CONFIRMED is forbidden** (the reverse demotion is always allowed)
6. **Delegation judgment**: when candidates exceed **20**, delegate VERIFY to a subagent (state a high-capability model explicitly. Inject the criteria from behavior-preservation-checks.md into the subagent's prompt)

## Phase 5: APPLY — Behavior-Preserving Refactor (Outside the Scope It Is Opt-In)

1. **Application policy**:
   - A CONFIRMED in `origin` (inside the Phase 0 scope) is APPLYed
   - A `sweep_candidates` entry (a sweep candidate outside the scope) is **report-only by default** even when CONFIRMED — present the count, the targets, and the transformation, and apply it only after obtaining the user's **opt-in confirmation**
   - **In a headless run (via cycle, etc., a context where confirmation cannot be obtained), report-only is fixed**. "Clean up this file" does not necessarily mean "rewrite the 20 similar sites too"
2. Apply **one improvement (`improvement_id`) at a time** → run the tests → move on when they pass (revert and reconsider on failure). Do not fix multiple candidates in parallel. **Cap the improvements APPLYed in one run at 10**, and defer the rest to the report (this 10 is the application batch cap. It is a different axis from the "10 files" delegation threshold in Phase 1/3)
3. **Verifying behavior is maintained**: make the existing tests (and any characterization test / probe made in Phase 1) all pass **without modifying them**. The moment a test needs modifying, suspect a behavior change → **revert**
4. **Optimizing test runs (optional)**: a structure of a targeted test for the affected module on each change, plus one whole-suite run after every improvement has been applied, is acceptable (avoiding N full runs on a large suite)
5. **Verification gate** (conforming to [verification-gate.md](../shared/references/verification-gate.md)): record the test command and its result as evidence. Claiming completion without evidence is forbidden
6. **Rule of 500**: when a single improvement's diff **exceeds 500 lines** (measured with `git diff --stat`), hand editing is forbidden — use a mechanical transformation:
   - The first choice is **ast-grep rewrite** (safe because it works in syntactic units)
   - `sed` is textual replacement and rewrites identically shaped text inside string literals and comments too, so it is a **last resort**; when you use it, these three conditions are mandatory: **(a) secure a revert point (a commit or a stash) before the transformation (b) review every diff after the transformation (c) all tests pass**

## Phase 6: REPORT — Report the Results + Proposed Issue-Creation Commands

**Gate early-exit rule**: when a Gate in any Phase triggers an early exit, skip all subsequent Phases and jump directly to this Report Phase. Do not pass through empty intermediate Phases.

### Exit Point × Report Format

| Exit point | Trigger | Format |
|---|---|---|
| **Phase 0 abort** | Scope unresolvable or path not found | Abort format |
| **Early exit (no findings)** | Phase 2 Gate: already-clean (zero candidates or all low-value) | Early-exit format |
| **Normal completion** | Phase 5 complete | Full structure (§1-§7 below). Even with 0 APPLYs, use this if there is any item to present (UNCERTAIN / BUG_FOUND / report-only sweep_candidates). Sections with nothing to report may be omitted |

**Abort format** — required sections:
1. Scope status (what was specified, or that nothing was specified)
2. Abort reason

**Early-exit format** — required sections:
1. Scope (the specified range)
2. Verdict summary (ALREADY_CLEAN / OUT_OF_SCOPE per candidate)
3. Reasons for the judgment

### Full Structure (Normal Completion)

Print the full structure in the conversation in the following form:

```
══════════════════════════════════════
REFACTOR REPORT
══════════════════════════════════════

## 1. The improvements carried out (scope: {scope})

| improvement_id | Target | The gist of before/after | Test result |
|----------------|------|-------------------|-----------|

## 2. The results of the sweep

| improvement_id | Detection tool | origin | Sweep candidates | CONFIRMED | FALSE_POSITIVE | UNCERTAIN | fallback_reason |
|----------------|-----------|--------|-------------|-----------|----------------|-----------|-----------------|

## 3. no-op / skipped / excluded

{the list of OUT_OF_SCOPE / ALREADY_CLEAN with their unknown_reason}

## 4. Held for judgment (UNCERTAIN)

{file:line, plus the material the user needs in order to judge}

## 5. The sweep_candidates kept report-only (outside the scope, opt-in required)

{file:line and the transformation. Awaiting the user's confirmation}

## 6. The bugs found (BUG_FOUND) — not fixed

For each bug, present a proposed issue-creation command (running it is the user's call):

  /claude-skills:issue-create "{a proposed title}"
  A proposed body: {the symptom / the site file:line / a draft of the reproduction conditions}

## 7. Verification evidence

- Tests: {the command run and its result. If not run, state the reason}
- diff: {a summary of git diff --stat}
```

**The rule for section attribution**: a `sweep_candidates` entry judged UNCERTAIN is recorded primarily in §4 (held for judgment). §5 carries only the candidates that are **CONFIRMED and awaiting the user's opt-in**. When one candidate falls under several reasons for non-application (e.g. no means of verification + outside the scope), give priority to the more fundamental reason, UNCERTAIN (§4), and **note the other reasons on the same line in §4** (no duplicate listing in §5. One candidate always appears in exactly one section).

**Important**: do not create or edit repository documents such as `.agents/artifacts/issues` while running refactor. Issue creation is limited to presenting a proposed command (no automatic issue creation). Lay a hand on neither the refactor diff nor an issue file.

## Rationalization Guard

| Excuse | Reality |
|--------|------|
| "Fewer lines, so it got simpler" | The measure of concision is speed of understanding, not line count. A one-line nested ternary is more complex than a five-line if/else |
| "While I'm here, let me fix this bug too" | That is a behavior change. It contaminates the refactor diff and makes it unreviewable. Presenting a proposed issue is the correct path |
| "It passes with a small tweak to the test" | Needing to modify a test = evidence that behavior changed. revert |
| "There is no test, but the change is obvious on sight" | Claiming behavior preservation without a means of proof violates verification-gate. Build a probe or drop to a no-op |
| "This helper is pointless, inline it" | An abstraction that gives a concept a name, or that exists for testability, is not complexity |
| "They look alike, so the same fix will do" | Textual similarity does not imply identical context. It is not a fix target until it passes the Phase 4 verification |
| "The sweep found them, so let us fix them all" | Application outside the scope is the user's opt-in. A huge diff outside the specified range surprises the user and makes review impossible |
| "It is working code, understanding can come later" | A refactor without understanding is degradation. Return to Phase 1 |
| "This style is better than the project's convention" | A "simplification" that breaks convention is churn. Consistency with the surrounding code comes first |

## Red Flags — Signs the Skill Is Not Being Followed

- Tests are being modified to make things GREEN
- A logic change (a condition added or removed, a changed return value) is mixed into the refactor diff
- Files are being edited while the Phase 1 understanding checks remain unanswered
- APPLY is happening on code that has neither a test, a type check, nor a probe
- Sites judged UNCERTAIN are being fixed
- `sweep_candidates` outside the scope are being APPLYed without the user's confirmation
- Files under .agents/artifacts/issues are being created or edited while running refactor
- Error handling is being removed "to make things clean"
- Low-value improvements are being forced into a list to avoid a no-op verdict
