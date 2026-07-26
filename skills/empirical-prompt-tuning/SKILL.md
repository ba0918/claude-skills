---
name: empirical-prompt-tuning
description: agent 向けテキスト指示（skill / slash command / task プロンプト / CLAUDE.md 節 / rules / コード生成プロンプト）を、バイアスを排した 3 役分離（チューナー / 実行者 / checker）で評価し、摩擦の固定タクソノミと統計的採択ゲートで反復改善する。収束した検証資産は可搬 fixture として資産化する。「empirical-prompt-tuning」「プロンプトチューニング」「指示の品質を測りたい」「skill を堅牢化したい」「このプロンプトが分かりにくい原因を知りたい」「rule が守られているか確認したい」で起動。`trigger-eval`（選択層 = description→発火の精度）の姉妹スキル（本文層 = 実行の質）。
---

# Empirical Prompt Tuning

The quality of a prompt is invisible to the person who wrote it. The very passages the author considers "clear" are where another agent gets stuck. The core of this skill is to **actually run it under an unbiased 3-role separation, evaluate with a fixed taxonomy and pure functions, and iterate**. Do not stop until improvement plateaus.
## When to Use

- Right after newly creating or substantially revising a skill / slash command / task prompt
- When an agent does not behave as expected and you want to trace the cause to ambiguity on the instruction side
- When you want to harden a high-importance instruction (a frequently used skill, a prompt at the core of automation)
- When you want to confirm that a CLAUDE.md section / rules are actually being followed

When not to use:
- A one-off throwaway prompt (the evaluation cost does not pay off)
- When the goal is not improving the success rate but merely reflecting the author's subjective taste

## Determining the Target Type (do this first)

| Nature of the target | eval_strategy | Evaluation method |
|-----------|---------------|----------|
| Running it produces an artifact (skill / command / task) | `task_scenario` | run task scenarios |
| It constrains behavior (rules / CLAUDE.md sections / guidelines) | `compliance_probe` | measure the compliance rate with violation-tempting scenarios |

When in doubt, use `task_scenario`. Details in [references/compliance-probe.md](references/compliance-probe.md).

## Workflow

### Iteration 0 — description/body consistency check (static, no dispatch)

- Cross-check the triggers / use cases the frontmatter `description` claims against the range the body covers
- If they diverge, align either the description or the body before moving on to iter 1
- Skip this and the executor "reinterprets" the body to match the description, producing false positives

### Phase 1 — Baseline preparation

1. **Fix the target prompt** and record its fingerprint with `compute_instruction_fingerprint()`
2. **Design 2-3 evaluation scenarios**:
   - `task_scenario`: 1 median task + 1-2 edge cases
   - `compliance_probe`: 1-2 violation-tempting scenarios + 1 normal-compliance scenario (details in [compliance-probe.md](references/compliance-probe.md))
3. **Design a requirement checklist** of 3-7 items per scenario:
   - Include at least one `[critical]` (with zero, the success verdict becomes vacuous)
   - Write each requirement in observable form (not "works correctly" but a concrete verification condition)
   - **Fix them in advance and never move them afterwards**
4. **Verify reachability** (3 axes: process / environment / contract consistency; details in [requirement-reachability.md](references/requirement-reachability.md)):
   - Before the requirement table, enumerate the stop conditions that could halt the workflow in this environment
   - Leaving an unreachable requirement penalizes an executor that behaved exactly as instructed, invalidating the measurement
5. Normalize the scenarios + checklist to JSON and **lock the sha256** (`verify_checklist_integrity()`).
   If the design releases reachability on the prompt side, include the prompt in the hash target as well

### Phase 2 — Execution (3-role separation)

**2a. Dispatch the executor subagent**

Create a new subagent every time (never reuse an agent that has learned the previous improvement). To run multiple scenarios in parallel, line up multiple subagent invocations inside a single message.

```
You are an executor reading <target prompt name> with fresh eyes.

## Target prompt
<paste the full body of the target prompt, or give a file path to read>

## Scenario
<the situational setup of the scenario>

## Task
1. Follow the target prompt to execute the scenario and produce the artifact.
2. Return the report below when you finish.

## Friction report
Report the places where the instructions tripped you up, using these categories:
- ambiguous_term: wording open to multiple interpretations
- missing_premise: implicit background knowledge is required
- contradictory: contradiction between instructions
- over_specified: unnecessarily strict
- rationalization_hook: an instruction that can be dodged by rationalizing
- self_containment_gap: does not stand alone without external references

## Report structure
- artifact: <the produced output or a summary of the execution result>
- friction: [{ "category": "<category>", "detail": "<detail>" }, ...]
- discretionary fills: places the instructions left undecided that you filled in with your own judgment (bulleted)
- retries: how many times you redid the same decision, and why
```

> **Note**: do not hand the requirement checklist to the executor. This removes self-scoring bias.

**2b. Dispatch the checker subagent**

A new subagent, separate from the executor. Details in [references/checker-protocol.md](references/checker-protocol.md).

```
You are an independent grader. Judge whether the artifact satisfies the requirement checklist.

## Artifact
<the executor's artifact>

## Requirement checklist
<the list of requirements>

## Task
Grade each requirement as pass/fail/partial, attach a one-line rationale, and return JSON.
```

> **Note**: do not hand the target prompt body to the checker. This removes lenient interpretation of the prompt.

### Phase 3 — Two-sided evaluation

Record the following from the returned results (append to `iterations.jsonl`):

**Checker grading (quantitative):**
- success/failure: success when every `[critical]` requirement passes
- precision: computed as `pass=1.0, partial=0.5, fail=0.0`, divided by the requirement count
- on failure, record which [critical] requirement was dropped

**Executor self-report (qualitative):**
- the friction report (already classified with the fixed taxonomy; details in [friction-taxonomy.md](references/friction-taxonomy.md))
- the discretionary fills
- the retry count

**Execution metrics:**
- step count (tool invocation count, `tool_uses`)
- elapsed time (`duration_ms`)

**Convergence verdict:**
- Call `resolve_exit_verdict()` in `convergence.py` and record the verdict

**Weighting**: the friction report (qualitative) is primary, the metrics (quantitative) are supporting. Chasing time reduction alone starves the prompt.

### Phase 4 — Applying the diff

Put the minimal fix that removes the ambiguity into the prompt. One theme per iteration (multiple related fixes are fine; unrelated fixes wait for the next round).

Before fixing:
1. State **which checklist item this fix acts on**
2. Verify with `verify_checklist_integrity()` that **the checklist sha256 has not changed**

### Phase 5 — Re-evaluation

Repeat Phase 2-4 with a new subagent. Keep going until `exit_verdict` is anything other than `continue`.

## k-run Statistical Acceptance Gate

The default is k=1 (compatible with the original, minimal cost). When a precise evaluation is needed:

```
--k-run 2   # run each scenario twice in parallel
```

- With k≥2, measure each scenario's precision k times and take the median
- Improvement verdict: count it as "improved" only when the gap between the previous and current medians exceeds the noise_band (half the run-to-run difference)
- Mechanically rules out false acceptance on a "lucky run"

**Write the gate for non-degradation A/B (baseline and candidate side by side) in differential form.**

```
NG: the critical requirement passes in the candidate arm
OK: the candidate does not drop a critical that the baseline was passing
```

Written as an absolute predicate, it never holds when the baseline itself drops that critical, whatever the
candidate is — **it returns constant false and stops discriminating between candidates**. Do not make the
baseline's defect the candidate's responsibility (measurements and the discrimination criteria are in
[requirement-reachability.md](references/requirement-reachability.md), section "An error in the verdict rule is not loosening").

## Separating Protocol Failure from Candidate Failure

Deviations on the checker/harness side (malformed output, inconsistency between requirement and grade,
an isolation_violation where something other than the artifact was read, an input_range_violation where
the input range was missing in an integration fixture, ...) **must not be confused with candidate failure**.

- On detecting a deviation, record the type and detail in `scenarios[].harness_error` and
  exclude that iteration from the precision aggregate and the convergence/divergence verdict
- `resolve_exit_verdict()` returns `halt`, and `halt_reason` becomes
  `checker_protocol_failure`
- Verification pure functions, in [scripts/convergence.py](scripts/convergence.py):
  `validate_input_range()` (just before dispatch) / `validate_checker_output()` (after the reply) /
  `has_protocol_failure()` (after recording). Every classification is emitted by the pure functions, so
  do not write your own detection in the harness
- For details and the classification, see [references/checker-protocol.md](references/checker-protocol.md),
  section "Separating protocol failure from candidate failure"

When handling an integration fixture (a handoff evaluation spanning multiple artifacts, etc.), declare
`input_range_required` on the fixture side, and have the harness cross-check it with `validate_input_range()`
just before dispatch. If anything is missing, halt with `input_range_violation` rather than treating it as
a candidate failure. Pass `fixture_kind="integration"` when validating the checker reply, which makes
stating `isolation_note` mandatory.

## Convergence Verdict (pure functions — `scripts/convergence.py`)

Every verdict is produced by the pure functions in `convergence.py`. The tuner's subjective judgment never intervenes.

| Verdict | Condition | Priority |
|------|------|----------|
| `halt` | max_iter / max_wallclock / kill_file / checklist_tampered | highest |
| `diverged` | the same friction category recurs threshold times in a row | high |
| `bloat_advisory` | prompt_bytes exceeds max_growth_pct over the previous round | medium (advisory) |
| `converged` | zero new friction for window consecutive rounds + metrics saturated | low |
| `continue` | none of the above | lowest |

Parameters:
- `window`: 2 (number of consecutive clears required; 3 for high-importance targets)
- `precision_delta_eps`: 0.03 (threshold for precision saturation)
- `steps_tolerance_pct`: 0.10 (tolerance for step-count saturation)
- `duration_tolerance_pct`: 0.15 (tolerance for elapsed-time saturation)
- `max_iter`: 10 (default; can be raised to 15 for high-importance targets)
- `max_wallclock`: 3600s (1 hour)

## Hash-locking the Checklist

When the baseline is fixed, normalize scenarios + requirements to JSON and record the sha256. At the start of every iteration, verify with `verify_checklist_integrity()`; a hash mismatch is a `checklist_tampered` halt.

To change the checklist intentionally, treat it as a "baseline reset" and start over from iteration 0. This puts an explicit cost (discarding every iteration) on the move of "loosening the checklist because the fix will not pass".

## Turning the Acceptance Fixture into an Asset

On convergence (`exit_verdict == "converged"`), emit the final iteration's scenarios + [critical] requirements + instruction fingerprint as portable JSON:

```json
{
  "source_skill": "<対象スキル名 or null>",
  "instruction_fingerprint": "abc123...",
  "eval_strategy": "task_scenario",
  "converged_at": "2026-07-09T13:42:00Z",
  "scenarios": [
    {
      "id": "A",
      "title": "...",
      "prompt": "...",
      "requirements": [
        { "text": "...", "critical": true }
      ]
    }
  ],
  "convergence_summary": {
    "iterations": 5,
    "final_precision": 0.93,
    "k_runs": 1
  }
}
```

Output: `.claude/tmp/empirical/{ts}/fixture.json`

This fixture:
- can be re-run for regression detection when the prompt is edited later
- can be transferred by hand into `skill-regression`'s `fixtures.json` in this repository (see the conversion guide in [fixture-schema.md](../skill-regression/references/fixture-schema.md))

## Qualitative Interpretation of `tool_uses`

Looking at precision alone hides structural problems in the instructions. Using `tool_uses` as a **relative value across scenarios** makes the defects visible:

- **3-5x or more** than the other scenarios is a sign that instruction has low self-containment
- Typical case: every scenario has `tool_uses` of 1-3 but one is 15+ → there is no inline recipe for that scenario
- Remedy: in iter 2, add a "minimal complete example inline" or guidance on when to read the references

Even at 100% precision, a skew in `tool_uses` is grounds for triggering iter 2.

## Environment Constraints

**Do not apply** this skill in an environment where new subagents cannot be launched.
- If the target is high-importance and the user has explicitly permitted launching another session or delegating to another agent, ask the user in the parent session to launch a separate session
- Otherwise, or when the evaluation cannot be completed in this turn, give up on the evaluation and report explicitly: "empirical evaluation skipped: dispatch unavailable"
- In either case, do not produce evaluation results, grades, convergence verdicts, or fixtures
- **NG**: substituting a self-reread (bias creeps in, so the results must not be trusted)

When the subagent launch cap is hit (counted cumulatively per session; a slot is not returned when one finishes), the executor / checker can be moved out into a separate process. What the 3-role separation requires is "a model invocation in an independent context", not a subagent as such, so the runner in [process-delegation.md](../shared/references/process-delegation.md) can substitute — but only for units whose pass/fail can be judged from the existence and validity of artifact files alone. Generating the work queue and the prompts (the producer side) is each harness's own responsibility and is not part of the shared assets.

**Structural review mode**: when you want to check only textual consistency rather than execution, state "structural review mode: text consistency check, not execution" explicitly in the request to the subagent. Structural review is a supplement to the empirical run, not a substitute (it cannot be used for the convergence clear verdict).

## Presentation Format

```
## Iteration N

### 変更点（前回差分）
- <修正内容 1 行>

### 実行結果（シナリオ別）
| シナリオ | 成功 | 精度 | steps | duration | retries |
|---|---|---|---|---|---|
| A | ○ | 90% | 4 | 20s | 0 |
| B | × | 60% | 9 | 41s | 2 |

### 摩擦報告（今回新出）
- <シナリオ B>: [critical] 要件 N が × — <落ちた理由 1 行>
- <シナリオ B>: [missing_premise] <詳細>

### 裁量補完（今回新出）
- <シナリオ B>: <補完内容>

### 次の修正案
- <最小修正 1 行>
- 対象要件: #N

（exit_verdict: continue | 収束まであと X 回クリア必要）
```

## Red Flags (watch for rationalizations)

| The rationalization that shows up | The reality |
|---|---|
| "Rereading it myself has the same effect" | You cannot see text you just wrote objectively. Always launch a new subagent |
| "One scenario is enough" | One scenario overfits. Two at minimum, three if you can |
| "Zero ambiguities came up once, so we are done" | It can be luck. The verdict is settled by two consecutive rounds (`is_converged` controls this) |
| "Let's crush several ambiguities at once" | You lose track of what worked. One theme per iteration |
| "Then split even the related micro-fixes strictly one per iter" | The opposite trap. "One theme" is a unit of meaning. 2-3 related micro-fixes may share one iter |
| "The metrics look good, so ignore the friction report" | A shorter runtime can also be a sign of starvation. Keep the qualitative side primary |
| "Rewriting from scratch would be faster" | Correct only when the same friction category has not shrunk for 3+ rounds (`is_diverged`). Before that, it is an escape |
| "Let's reuse the same subagent" | It has learned the previous improvement. Launch a new one every time |
| "The checklist is too strict, let's loosen it" | That requires a baseline reset (start over from iteration 0). The hash lock enforces it |
| "The checker's grading is wrong" | If you object to the checker, improve how the requirement is written (in the next baseline). For the current iteration the checker's verdict is final |

## Common Failures

- **Scenarios too easy / too hard**: neither produces a signal. One median + one edge is the baseline
- **Watching only the metrics**: chasing runtime alone starves the prompt
- **Too many changes per iteration**: you cannot trace which fix worked. One theme, one iter
- **Tuning the scenario to fit the fix**: the checklist sha256 changes and it halts (by design)
- **Showing the target prompt to the checker**: lenient interpretation bias comes back. Never hand it over
- **Locking an unreachable requirement**: grading a step that stops earlier for environmental reasons penalizes an
  executor that behaved correctly, and shows up as an identical failure in both arms. Observed recurring 3 times ([requirement-reachability.md](references/requirement-reachability.md))

## Related

- [trigger-eval](../trigger-eval/SKILL.md) — the sister skill for the selection layer (description→firing). This skill measures the quality of body execution; trigger-eval measures firing accuracy
- [skill-regression](../skill-regression/SKILL.md) — this skill's convergence output (fixture.json) can be converted into a regression asset
- [skill-improve](../skill-improve/SKILL.md) — passive analysis (past JSONL). This skill is active testing
- [references/checker-protocol.md](references/checker-protocol.md) — the checker subagent launch contract
- [references/requirement-reachability.md](references/requirement-reachability.md) — pre-lock reachability verification (process / environment / contract consistency)
- [references/iteration-schema.md](references/iteration-schema.md) — the iteration JSON record schema
- [references/friction-taxonomy.md](references/friction-taxonomy.md) — the 6 friction categories
- [references/compliance-probe.md](references/compliance-probe.md) — the evaluation method for passive constraints
