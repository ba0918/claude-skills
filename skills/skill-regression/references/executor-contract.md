# The launch contract for a blank-slate executor, and the verdict rules

The contract for the subagent that runs a fixture's scenarios in the run workflow.
The reliability of the evaluation depends entirely on the executor being a blank slate.

## Principles

- **Dispatch fresh every time**: reusing the same agent means it has learned the previous context and is not a blank slate.
  Self-rereading (the caller reads SKILL.md and decides "this is fine") is forbidden for the same reason
- **Concurrent execution**: line up multiple scenarios as multiple subagent invocations inside a single message
- **State the tier**: state the fixture's `executor_tier` (`standard` when omitted) explicitly in the subagent invocation
- **Isolation**: for a scenario with `isolation: worktree`, create a disposable git worktree,
  place `setup.files`, and then launch the executor. Discard the worktree afterwards.
  - The boundary of "do not let it edit": **inside the isolated area (the worktree), editing and committing freely is allowed**
    (this is what makes fixtures for skills like commit work). What is forbidden is editing the repository proper (outside the worktree)
  - **Fallback in a non-git environment**: when git worktree is unavailable in the target repository, isolation may be
    substituted by placing `setup.files` into a disposable directory
    (keep the `isolation: worktree` notation in fixtures.json as it is)
  - **Corroborating zero edits**: record a sha256 baseline of `setup.files` before the run and compare afterwards.
    Base the verdict for read-only critical requirements on this hash comparison, not on self-report
  - **Cleanup**: when discarding (deregister + delete) is refused by a permission or mount constraint,
    **do not route around the deletion with another tool**. Record it in the report as inert debris in a
    git-ignored area, and offer the human a cleanup command (e.g. `git worktree prune && rm -rf <path>`)

## The structure of the executor prompt

```
You are an executor reading the SKILL.md of the <skill name> skill for the first time.

## Target skill
<the absolute path to skills/<skill>/SKILL.md. State that references may be followed from there>

## Working directory
<the absolute path of the isolated area where setup.files were placed. State that the executor works only inside it>

## Situation
<scenario.prompt verbatim>

## Task
1. Follow the target skill's instructions to handle the situation above and produce the artifact.
2. On completion, always reply with nothing but the report structure below.

## Report structure
- Artifact: <a summary of what was produced, or the execution result>
- Execution path: <multi-stage delegation skills only. One line on whether each phase ran by delegation or by inline substitution>
- Requirement table: ○ / × / partial for each item below, plus a one-line rationale
  <enumerate the requirements with numbers. Never show the critical tags to the executor>
- Ambiguities: places in SKILL.md where the interpretation was unclear (bulleted; "none" if there are none)
- Discretionary fills: places not in the instructions that you filled in with your own judgment (bulleted; "none" if there are none)
```

**The execution path is reported** because, with the same fixture and the same premises, the path forks depending on how the
executor perceives its environment, and only one of them runs to completion without external intervention (measured: cycle
made 4 status queries on the delegation path and 0 with inline substitution). Leaving only `pass` in the ledger hides that
difference from whoever runs it next.

**The critical tags are hidden from the executor** to avoid the bias of the executor prioritizing and papering over just the
critical items. The verdict is made by the caller.

Workarounds for environment constraints (the sandbox refusing to read gitconfig, and so on) may be injected into the prompt as
an "environment setup" section. But **it must contain no hint about how to solve the scenario** (state that explicitly in the injected text).

### Environment constraints found by measurement (2026-07-25, 10 skills / 21 scenarios)

None of these are defects of a fixture or a skill; they are properties of the execution platform. Running without knowing them
gets misread as "the skill failed", so build the workarounds in before launching.

- **Results cannot be collected unless the reporting path is stated**: the ordinary text output of an executor launched in the
  background does not reach the caller. In the task section of the prompt, write the concrete invocation form: "on completion,
  report via the message-sending mechanism (ordinary output does not reach us)".
  In the first batch, where this was not stated, 4 of 9 entered a waiting state with no result body
- **An executor cannot do named nested delegation**: when an executor launches a further subagent, a named launch may be
  refused. Launch it anonymously and then **the completion notification does not come back to the executor**. Because of this
  double constraint, fixtures for multi-stage delegation skills such as cycle stall at every phase boundary
  - Workaround: the caller acts as **the upper watchdog**. When the executor stalls, inspect the artifacts
    (result files, commits, generated output) directly to judge the progress, and send a status query conveying **facts only**.
    A query is not a re-delegation, so it does not consume the retry budget
    (the wait discipline of [orchestration-patterns.md](../../shared/references/orchestration-patterns.md))
  - **Give no hint about the solution**: not "read the result file" but only the fact that "the delegate has already finished
    and the notification will not arrive". Recovering from a stall is itself part of what the skill is measured on
  - In the measurements, one cycle scenario needed 4 queries to run to completion. The skill's decision logic worked correctly
    every time (transitioning by reading the result file, avoiding re-implementation on retry, tolerating partial failure)
  - **Record the number of queries in the ledger** (`ledger.py --update <skill> --note "..."`).
    Leaving a bare `pass` makes the next person in the same environment mistake the same stall for a regression and re-dig the cause
- **Cleanup is sometimes refused by permissions**: deleting the delegation result file is refused by the sandbox and the shared
  contract's cleanup cannot run. As the principle says, **do not route around the deletion by another means** — record it in the report as inert debris
- **Files with sensitive-looking names are not materialized as declared**: the sandbox sometimes overlays a device file
  (`/dev/null`) onto `.env` and the like, and the `setup.files` write is silently discarded. If the `unmaterialized` output of
  `fixture_setup.py --materialize` is non-empty, the declaration and the reality diverge for those paths. **Do not put a
  requirement that depends on the contents into such a scenario** (a requirement judged by name or kind still holds). Record it
  in the report, and if a requirement assumed the contents, fix the fixture side
- **Platform-derived files leak into the isolated area**: unreadable files and entries that are not regular files appear in the
  working directory and dirty `git status`. In a scenario that leaves commit to auto-detection, the executor risks sweeping them
  in. For a scenario whose requirement is "a clean working tree", create an initial commit in the isolated area during the run
  procedure to fix the reference state

## Verdict rules

- Scenario pass = every `critical: true` requirement is **○** (partial counts as ×)
- Skill pass = every scenario passes. `--update` on the ledger happens only on a skill pass
- A × on a non-critical requirement does not affect the verdict, but always put it in the report (an early signal of degradation)
- When the executor's self-reported requirement table contradicts the artifact (it wrote ○ but the artifact gives no grounds),
  do not take the self-report — the caller re-judges from the artifact.
  Only when judgment splits, or the artifact cannot settle it, additionally launch a dedicated judging subagent
  (tier: high, handed only the artifact and the requirements, never the execution process)
- When in doubt about a requirement, fall to × (fail-safe. Making passes lenient empties the ledger of meaning)

## Report format

```
## skill-regression run — <対象スキル>

| シナリオ | 合否 | critical | 非critical | 落ちた項目 |
|---------|------|----------|-----------|-----------|
| sf-001 <title> | ○ | 3/3 | 1/1 | - |
| sf-002 <title> | × | 2/3 | 1/1 | R2: <要件 1 行> — <落ちた根拠 1 行> |

- 実行者の不明瞭点（新出のみ = 台帳に記録がある前回 run の報告に無かったもの。前回 run が無ければ全件）: <箇条書き>
- 台帳: <更新した / 不合格のため未更新>
- fixture を持たない影響スキル: <名前列挙。capture 推奨として提示>
```

On a failure, attach the separation of "a regression on the skill side" versus "the fixture going stale (the spec changed
deliberately)", with grounds (which commit or which edit caused it).
