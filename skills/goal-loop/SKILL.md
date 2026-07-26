---
name: goal-loop
description: 機械検証可能な条件（oracle コマンド）が真になるまで「oracle 実行 → 失敗出力を implementer に渡して修正」を自律反復する条件収束型ループ。「全テスト green まで回して」「lint エラーゼロまで直して」「ビルドが通るまで」で起動。oracle ファイル群をハッシュロックし、テストを弱めて合格する oracle-gaming を機械的に遮断（oracle_tampered で即 halt）。同一失敗の stall・往復の oscillation を検出して無限ループを防ぐ。「goal-loop」「ゴールループ」「収束するまで」「〜が通るまで繰り返して」でも起動。
---

# Goal Loop

**Shared contract (required reading, direct link):** [../shared/references/convergence-pattern.md](../shared/references/convergence-pattern.md)

Autonomously iterate fixes until the oracle (the deciding command) becomes true. This SKILL.md is a thin orchestrator;
the specifications for oracle integrity, convergence judgment, and the safety brakes live in the contract (do not duplicate them).

## Invariants (contract §3 / §5)

1. **The controller (you) runs the oracle.** Never accept the implementer's "it passed"
2. **oracle_files are hash-locked**, and verified immediately before every iteration's oracle run.
   Detected tampering = `oracle_tampered`, halt immediately (do not roll the implementation back; report to a human)
3. Never update the manifest inside the loop. Changing the oracle is something a human does outside the loop
4. Never run without the safety brakes (max_iter=8 / max_wallclock=30m / two kinds of kill file).
   The semantics of the kill files (`.STOP` graceful / `.STOP.hard` hard, resolved as absolute paths) follow
   [polling-pattern.md §6](../shared/references/polling-pattern.md#6-safety-brakes)

## Argument Format

```
goal-loop "<goal の自然言語記述>" [--oracle "COMMAND"] [--oracle-files PATH...]
          [--max-iter N] [--max-wallclock DURATION]
```

## Steps

### Step 1: Fix the oracle

1. Use `--oracle` if given. Otherwise infer the deciding command from the goal description and the project layout.
   The inference **prefers the entry point the project officially advertises** (a command documented in the README >
   a test target in a Makefile / package.json scripts > invoking the raw test runner directly)
2. Use `--oracle-files` if given. Otherwise enumerate the verification definitions the oracle reads (the whole test directory,
   lint configuration, verification scripts). **Do not narrow this** — including the entire test directory is the default (contract §2).
   Including the files that **define** the oracle command (a Makefile test target, etc.) is recommended
   (that also blocks gaming by rewriting the command). However, files the implementer may legitimately touch
   (package.json as a whole, etc.) are a source of false halts, so you may judge them out.
   Build products (`__pycache__` / `*.pyc`) are excluded automatically by the locking script
3. Confirm with the user and get the oracle (command + files + expected_exit) approved exactly once.
   In a headless context (inside cycle, etc.), adopt the inferred values as-is and state them explicitly in the report

### Step 2: Lock

```bash
TS=$(date +%Y%m%d%H%M%S); WORK=$(pwd)/.claude/tmp/goal-loop/$TS; mkdir -p $WORK
python3 {skill_dir}/scripts/goal_loop.py lock {oracle_files...} --out $WORK/manifest.json
```

**Fix `$WORK` as an absolute path and keep using that same value in every later step** (shell invocations are
stateless, so keep the settled absolute path of WORK in your own context.
Do not build a mechanism to re-derive it — trying to resolve it across a different TS shifts the lock targets).

The paths in the manifest are recorded and resolved **relative to the cwd at lock time**. Always run lock / verify
**at the project root (the same cwd)** — invoking verify from another directory fails to find the files and produces a
false tamper (exit 2).

### Step 3: Iteration loop (conforms to the pseudocode of contract §5)

For each iteration i = 1..max_iter:

1. **Kill file check**: check `$WORK/.STOP` (graceful) / `$WORK/.STOP.hard`, and halt immediately if either exists.
   The base directory for kill files is **the absolute `$WORK`** (this is how "absolute path resolution" of polling-pattern §6 is
   satisfied — do not look at a different location via a relative path)
2. **Wallclock check**: if the time elapsed since the start exceeds max_wallclock (30m by default), finish with
   `halt_reason="max_wallclock"`
3. **Integrity verify**: `python3 {skill_dir}/scripts/goal_loop.py verify $WORK/manifest.json`
   - On exit 2, `halt_reason="oracle_tampered"`. Report the tampered paths and **finish immediately** (do not fix and do not roll back)
4. **Run the oracle**: run the oracle command in a shell and save its output to `$WORK/iter-{i}.log`
   - Matches `expected_exit` → **converged**. Go to Step 4 (do not accumulate a signature for the converged iteration)
5. **Record the signature and judge non-convergence** (run both mechanically through the CLI — no mental arithmetic, no eyeballing):
   ```bash
   python3 {skill_dir}/scripts/goal_loop.py signature < $WORK/iter-{i}.log >> $WORK/history.txt
   python3 {skill_dir}/scripts/goal_loop.py halt $WORK/history.txt
   ```
   halt exit codes: 0 = continue / 3 = stall / 4 = oscillation. On 3 or 4, adopt it as the halt_reason
   verbatim and finish
6. **Delegate to the implementer**: hand the following to a subagent (a lightweight model; a high-capability model only for large fixes) and have it fix the code.
   **Treat the delegation as synchronous** — do not end the controller's turn until the implementer's result is received
   (ending the turn while still waiting loses the loop). Even when the implementer returns a no-op,
   **run the oracle again, record the signature, and judge halting on every iteration** (this is what makes the repetition
   that stall detection needs; do not manually break the loop on the grounds of a no-op):
   - The oracle's failure output (that iteration's log)
   - An explicit instruction that **editing oracle_files ({enumeration}) is forbidden**, and that passing by changing tests or verification definitions is equivalent to failure
   - An explicit instruction not to cross approval gates or constraints stated in the code (comments / fences such as "changes require approval")
     without permission. **If the fix is impossible without crossing them, change nothing, report that, and return (a no-op)**
   - The fix targets production code only
7. Move on to the next iteration

> **Design intent of non-convergence**: when a test expectation and a production constraint (an approval gate) collide so that autonomous
> fixing is impossible in principle, do not invent a dedicated halt_reason. The regular path is: the implementer returns a no-op →
> the same failure repeats → **it stops mechanically as a stall**. Include in the report, as a handover, the options that a human must
> decide outside the loop (obtain approval and change it / redefine the oracle, re-lock, and restart).

### Step 4: Completion report (conforms to verification-gate)

```
## Goal Loop 結果
- converged: true/false（halt_reason: ...）
- iterations: N / max N
- oracle: {command}（exit {code}）
- 証拠: 最終 oracle 実行出力の末尾（$WORK/iter-{last}.log）
- oracle integrity: 全イテレーションで verify 合格 / oracle_tampered（改変パス列挙）
```

`converged: true` is allowed only when **the actual output of the final oracle run** can be presented as evidence
([verification-gate.md](../shared/references/verification-gate.md) — claiming completion without evidence is forbidden).

## Preventing rationalization

| Excuse | Reality |
|--------|------|
| "This test contradicts the specification, so fixing it is faster" | That is a change to the oracle, and it is a human's job outside the loop. Inside the loop it is `oracle_tampered` = failure |
| "It would converge if I just skipped the flaky test" | Adding a skip modifies oracle_files. It will be detected and halt. Excluding flakiness comes after a human redefines the oracle |
| "The implementer says the tests passed" | Self-reports are not accepted. Only the result of the controller re-running the oracle is true |
| "It looks like one more round would pass, so let us raise max_iter" | stall / oscillation detection is the machine's judgment that "more rounds will not converge". Raise it only on an explicit human instruction |

## Choosing between skills

Condition-convergent (this skill) vs interactive TDD vs instruction-driven iterate vs queue-consuming polling —
see [the comparison table in contract §7](../shared/references/convergence-pattern.md#7-使い分け).
