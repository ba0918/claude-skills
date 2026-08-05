---
name: skill-regression
description: A harness that turns a skill's tuned behavior into fixtures (a scenario plus a requirements checklist) and, when a SKILL.md or a shared contract changes, runs regression evaluation over only the affected skills. It converts the pass criteria measured during empirical tuning into a re-runnable regression asset instead of discarding them. It mechanically prevents the problem where editing a single shared contract silently changes the behavior of a dozen referring skills, using reverse dependency lookup, a verification ledger, and a CI gate. Use when the user says "skill-regression", "regression evaluation", "turn this into a fixture", "retune", "check the impact of the shared contract", or "skill regression". For this repository (the skill collection repository) only.
---

# Skill Regression

Artifact paths follow the [Artifact Store consumer contract](../shared/references/artifact-paths.md). Resolve and validate the store before reading or writing artifacts.

A skill is a program written in prose, and every edit to a SKILL.md, a reference, or a shared contract is a "behavior change".
Yet the acceptance criteria established during empirical tuning vanish with the session, and when the next edit
breaks the tuned behavior nobody can notice. This skill **turns those acceptance criteria into fixtures as assets**,
runs the regression evaluation only against the skills whose behavior surface changed, and records the result in a ledger.

- What **trigger-eval** protects is "does it trigger correctly". What this skill protects is "once triggered, does it execute correctly"
- How a fixture is produced does not matter (a measurement from empirical tuning, the acceptance criteria of a plan document, or manual design are all fine).
  This skill is on the **consuming (re-running)** side and does not depend on any particular producing skill

## Terminology

| Term | Definition |
|------|------|
| behavior surface | The set of files that can affect a skill's runtime behavior. Everything under `skills/<name>/` (excluding test_*.py / __pycache__) plus the files under `skills/` referenced **one hop** away from that skill's own .md files (shared contracts included), picked up from md links and from bare paths in the procedural text alike. Never traverse from files outside the skill: following the "related" links between shared contracts puts skills whose execution paths never meet onto the same surface, and one hop matches the "references go one level deep" principle of [skill-authoring](../shared/references/skill-authoring.md). The worked example of the multi-hop failure is in `scripts/dep_graph.py` |
| fixture | `skills/<name>/fixtures.json`. A set of scenarios plus a requirement checklist marked with [critical]. The schema is [references/fixture-schema.md](references/fixture-schema.md) |
| ledger | `skills/skill-regression/ledger.json`. A record of the verification event "every scenario passed at this behavior surface". It is committed |

## Execution contract

- Always call the scripts by absolute path: `python3 {skill_dir}/scripts/ledger.py <mode> {repo_root}`.
  `{skill_dir}` is the directory containing this SKILL.md, and `{repo_root}` is the root of the skill-collection repository (usually the cwd)
- Only skills that have a fixture are tracked (opt-in). Skills without one are outside the check
- Updating the ledger (`--update`) happens **only after obtaining evidence that every scenario passed**.
  Conforming to [verification-gate.md](../shared/references/verification-gate.md) — never advance the ledger on an evidence-free "it should have passed"
- When judging without running that "this change does not affect behavior", use `--update <skill> --accept`.
  The acceptance is recorded explicitly, so it stays distinguishable from ignoring the drift. **Which value gets recorded
  is decided by the machine, not by the operator**: `accepted-addition` and `accepted-prose` mirror the same-named
  severities under [status](#status--taking-stock) and are reachable only on top of a real run's `pass`; everything else
  is `accepted-without-run`. A self-declared "it was a light change" would leave an unbacked claim in the ledger

## Workflow selection

| Input | Workflow |
|------|-------------|
| "turn this into a fixture" / "make it an asset" (right after tuning, or after a plan completes) | capture |
| "run the regression evaluation" / "check the impact of this change" (after editing a contract or a SKILL.md) | run |
| "show me the status" / "which ones are stale?" | status |
| "which ones have no fixture?" / "what is the coverage?" | status (`--coverage`) |
| CI failed with `[stale]` / `[unverified]` | run (targeting the skills in the failure message) |

## capture — turning acceptance criteria into assets

1. **Identify the material**: confirm where the target skill's acceptance criteria come from. In order of preference:
   (a) The fixture.json of the most recent [empirical tuning](../empirical-prompt-tuning/SKILL.md) session (measured, and therefore best; for the conversion guide see the "Conversion guide by source material" section of [fixture-schema.md](references/fixture-schema.md))
   (b) The acceptance criteria of the corresponding plan under `.agents/artifacts/plans/`
   (c) If neither exists, design new ones following the design guidelines of [references/fixture-schema.md](references/fixture-schema.md)
2. **Create fixtures.json**: write `skills/<skill>/fixtures.json` following the schema.
   2-3 scenarios (1 median + 1-2 edge), 3-7 requirements each, and at least one `critical: true`
3. **First run**: run every scenario with **Steps 2-4 of the run workflow (execute, judge, report)** and
   confirm that all of them pass (use capture's own procedure for Step 1's reverse lookup and Step 5's ledger update).
   Do not turn a failing fixture into an asset as-is (the later regression evaluations would always be red and the ledger would lose its meaning)
4. **Record in the ledger**: `python3 {skill_dir}/scripts/ledger.py --update <skill> {repo_root}`
5. **Append a measurement event**: because the ledger holds only the latest entry, append the history of verification events
   following [measurement-identity.md §4](../shared/references/measurement-identity.md#4-mapping-table-for-the-existing-systems):
   `python3 skills/shared/scripts/measurement_identity.py emit --system skill-regression --event verification --skill <skill> --repo-root {repo_root} --outcome '{"result":"pass","scenarios":N}'` (with `--accept`, use whichever value the ledger actually recorded — `"result":"accepted-addition"`, `"result":"accepted-prose"` or `"result":"accepted-without-run"`)

## run — regression evaluation

1. **Determine the targets**:
   - Use the skill name if one was given. Otherwise reverse-look-up from the changed files:
     take `git diff --name-only HEAD` (uncommitted changes) or a specified commit range, and
     obtain the affected skills with `python3 {skill_dir}/scripts/ledger.py --impact <changed>... {repo_root}`.
     When git is unavailable, or the changed files were stated explicitly in conversation, pass those paths straight to `--impact`
   - **Narrow to scenarios**: `--impact-scenarios <changed>... {repo_root}` prints `skill<TAB>scenario_id` for the
     scenarios a change actually reaches, using the fixtures' `exercises` declarations (scenarios without one stay
     on the safe side and are always listed). Run only those, then advance the ledger with `--partial` in Step 5.
     Rules and fallbacks: [references/partial-rerun.md](references/partial-rerun.md)
   - Only affected skills that have a fixture are evaluated. List the ones that do not as out of scope in the report
   - **Rule of thumb for run vs `--accept`**: a purely prose change (punctuation, phrasing) that touches no
     machine-parsed token, code, command, or frontmatter key is `--accept` territory. Everything else is run.
     When in doubt, run (fail-safe)
   - Even when the ledger is already verified (including either accepted value), you may run if the user asks for a
     regression evaluation. Overwriting an acceptance with a real run's `pass` improves the ledger's quality
2. **Execute** (only the scenarios Step 1 selected): read the target skill's `fixtures.json` and, per scenario, launch a blank-slate executor subagent
   under the contract of [references/executor-contract.md](references/executor-contract.md).
   - **Materialize the isolated area from the declaration**: `python3 {skill_dir}/scripts/fixture_setup.py --materialize
     skills/<skill>/fixtures.json <scenario_id> <dest>`. Do not assemble it by hand —
     premises such as mtimes, git state, and environment variables leak outside the declaration and the run proceeds on different premises each time
   - Use the output's `baseline` to corroborate that nothing was edited, and transcribe `env` into
     the environment-setup section of the executor's prompt
   - Run them in parallel by listing multiple subagent invocations in the same message (conforming to [orchestration-patterns.md](../shared/references/orchestration-patterns.md))
   - The executor's tier follows the fixture's `executor_tier` (the default `standard` = mechanical scenario execution. Raise it to `high` only when accuracy falls short on a judgment-heavy skill, and pin it by recording the reason in `notes`). Do not write a concrete model name into a fixture — keep the expression platform-independent
   - Isolate scenarios that create or edit files in a throwaway git worktree and discard it afterwards
   - **When the subagent launch quota is exhausted, the batch is large, or you want an unattended run**,
     you may take the route of delegating to a separate process instead of a subagent (it consumes no launch quota).
     The procedure and its constraints are in [references/process-queue.md](references/process-queue.md).
     The judging rules stay exactly as executor-contract defines them
3. **Judge**: judge each scenario ○/× with executor-contract's judging rules.
   A skill passes = every `[critical]` requirement is ○ in every scenario
4. **Report**: present a per-scenario result table (pass/fail, which critical items failed, and the executor's self-reported points of ambiguity)
5. **Update the ledger**: only for skills that passed everything, `--update <skill>` (append the measurement event as in capture Step 5).
   After a scenario-granular run, use `--update <skill> --partial --scenario <id>...` instead: it records the ids you ran and
   carries the rest over, refusing (and listing them) if any cannot be carried. Zero ids is legitimate — a declaration-only
   fixture edit advances the ledger with no run at all.
   Because the same stop gets mistaken for a regression when the nature of a run does not reach whoever runs it next, record with `--note "<one line>"` the path the executor took,
   how many times it was asked for status from outside, and any harness constraints it worked around. For a failing skill, do not advance the ledger; instead
   separate the cause (a regression in the skill, or an obsolete fixture) and report it.
   When you judge the fixture obsolete, fix the fixture and redo it from capture —
   but **fixing it in the direction of making the scenario easier is forbidden** (that merely hides the regression)

## status — taking stock

- `python3 {skill_dir}/scripts/ledger.py --status {repo_root}` displays verified / stale / unverified / orphan
  for every tracked skill
- `--check` is the same judgment as CI (exit 1 if there is any issue). Clean up orphans with `--remove <skill>`.
  Each `[stale]` line carries a severity: `[contract-addition]` when the machine could confirm the surface only gained
  files from inside the skill's own directory, `[prose-change]` when it could confirm the only modifications are to the
  prose of existing md files (machine-parsed tokens untouched), and `[contract-change]` in every other case. Read it as
  triage, not as permission — `contract-addition` and `prose-change` still have to be resolved, only with `--accept` as
  a defensible option
- `--coverage` displays **the denominator of what is tracked at all** as covered / exempt / uncovered. The two modes
  answer different questions: `--check` asks whether the verified assets have gone stale, `--coverage` asks how much is
  being verified in the first place. Because `--check` is an opt-in gate that looks only at skills holding a fixture,
  "skills with no fixture written" never enter its count even when everything passes
- Declare exclusions in `ledger.py`'s `COVERAGE_EXEMPT` **with a reason** (not on the skill side —
  otherwise merely touching a skill directory could make it disappear from the count).
  **"Not written yet" is not a reason for exemption.** That is uncovered
- `--coverage --strict` exits 1 if there is even one uncovered skill. Use it as a working gate while
  expanding coverage (the standing CI gate is `--check`)

## The CI gate

`.github/workflows/validate.yml` runs `ledger.py --check`. When the behavior surface (shared contracts included) of a
skill holding a fixture has changed since the last verification, CI fails and demands either a
re-evaluation (run → `--update`) or an explicit judgment that it is unnecessary (`--update --accept`).
The philosophy of this gate is not to stop drift but to **make only ignoring it impossible**.

## Red flags

- The ledger's `result` is nothing but `accepted-without-run` (a sign that run has become a formality). `accepted-addition`
  and `accepted-prose` do not count toward this signal; `accepted-without-run` is a superset of the acceptances a human
  waved through, since whatever the machine could not confirm either way lands there too
- The same skill's fixture is rewritten repeatedly in a short span as "obsolete"
- The run report does not state which critical items failed
- CI's `[stale]` is being piled onto main instead of resolved within the PR

## Scope — reproducing on another runtime is out of scope (a deliberate non-goal)

Computing the behavior surface (`dep_graph.py`) and reproducing a fixture target only what is under `skills/`, and
handle only scenarios reproducible in the current execution environment. The reasons:

1. Reproducing a fixture launches a blank-slate executor as a subagent, so calling another runtime's behavior
   "reproduced" in the current execution environment would be a forgery of verification
2. What this skill protects is "once triggered, does it execute correctly", and runtime-specific behavior cannot be
   verified in principle without a new tool-mapping-aware executor contract that launches on the target runtime
3. Should it become necessary, design a runtime variant of `references/executor-contract.md` first and only then widen
   `dep_graph.py` (extend the means of execution before the detection range, never the reverse)

## Related

- [fixture-schema.md](references/fixture-schema.md) — the schema of fixtures.json and its design guidelines
- [executor-contract.md](references/executor-contract.md) — the launch contract and judging rules for a blank-slate executor
- [partial-rerun.md](references/partial-rerun.md) — the `exercises` declaration, scenario-granular impact, and ledger carry-over
- [process-queue.md](references/process-queue.md) — the route for running a batch via separate-process delegation (it consumes no launch quota)
- [orchestration-patterns.md](../shared/references/orchestration-patterns.md) / [verification-gate.md](../shared/references/verification-gate.md)
