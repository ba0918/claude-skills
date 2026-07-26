# Convergence Pattern — Shared Contract (condition-convergent loops)

> **⚠️ Warning:** This contract is the sister of [polling-pattern.md](polling-pattern.md)
> (queue-consuming) and defines the common specification for the family of loops that
> "keep running until a machine-verifiable condition becomes true". Changes to oracle
> integrity, convergence detection, or the safety brakes affect every implementing skill
> (`skills/goal-loop/` and others). Update them in sync within the same PR.

---

## 1. Overview — the 2 loop families

| Family | Contract | Stop condition | Example |
|---|---|---|---|
| Queue-consuming | polling-pattern.md | Queue empty / kill / brake | issue polling / github-issue polling |
| **Condition-convergent** | This contract | **Oracle verifiably true** / kill / brake / non-convergence detected | goal-loop ("run until all tests are green") |

The biggest threat to the condition-convergent family is **oracle-gaming (Goodhart's law)**:
the moment the goal becomes the measure, "weakening the test" is always cheaper than "fixing
the test". Under autonomy pressure an implementer slides down that path without any malice.
This contract blocks it **mechanically**.

---

## 2. Oracle

```
Oracle {
  command:       str        # judgement command (e.g. "python3 -m unittest discover")
  expected_exit: int = 0    # exit code treated as success
  oracle_files:  [str]      # files that define the meaning of the oracle (tests, verification scripts, expected values)
}
```

- `command` must be **machine-executable**. Do not make an LLM judgement such as "once it
  gets better" the oracle (a goal the judge can move is not a goal)
- `oracle_files` is fixed at loop start. Including the entire test directory is the default
  (the narrower it is, the more gaming loopholes open up)

---

## 3. Oracle Integrity (hash lock — the core of Goodhart blocking)

1. **Lock**: at loop start, record the sha256 of each file in `oracle_files` as a manifest
2. **Verify**: re-verify the manifest **immediately before every iteration's oracle run**
3. On detecting a mismatch (modification, deletion, or a rewrite such as adding a new test
   skip inside `oracle_files`), halt immediately with `halt_reason="oracle_tampered"` and
   report the altered paths. **Do not roll back the implementation** (so a human can see what
   happened; whether the alteration was implementer runaway or a legitimate spec change is a
   human judgement)

**Invariants:**

- State explicitly in the prompt that the implementer has **no permission to edit**
  `oracle_files`, and have Verify detect it even if they do (defense in depth that does not
  rely on prompt discipline)
- Legitimate oracle changes (spec changes, added tests) are made by a human **outside the
  loop**, restarting the loop from the beginning. A manifest-update API inside the loop
  **must not exist** (if it exists, it will be used)
- The controller **runs** the oracle. Do not accept an implementer's self-report of "the tests
  passed" (maker/checker separation; conforms to
  [verification-gate.md](verification-gate.md))

---

## 4. Convergence Detection (stop conditions finer than failed_streak)

Continuing to fail may still be progress if the failures are **different**. Stop only the
repetition of the same failure and oscillation between failures.

### 4.1 Failure Signature

Normalize the oracle failure output (trim lines; strip timestamps, elapsed times, and
hexadecimal addresses) and take the leading 16 hex characters of its sha256. Push it onto the
history each iteration.

### 4.2 Pure Functions

| Function | Signature | Judgement |
|---|---|---|
| `oracle_manifest(contents)` | `(dict[path, bytes]) -> dict[path, hex64]` | Generate the manifest for locking |
| `verify_oracle_integrity(manifest, current)` | `(dict, dict) -> Ok \| Tampered{paths}` | Detect modification, deletion, and addition alike |
| `failure_signature(output)` | `(str) -> hex16` | §4.1 normalization + hash |
| `detect_convergence_halt(history, config)` | `(list[hex16], Config) -> None \| "stall" \| "oscillation"` | stall: the last `stall_limit` entries share one signature. oscillation: the last `window` entries repeat a pattern with period 2 to `max_period` |

All are side-effect free and use no time / random / I/O. Implementing skills must verify them
with unittest.

---

## 5. Iteration Loop

```
goal_loop(oracle, config) -> LoopResult:
    manifest = lock(oracle.oracle_files)                     # §3
    history = []
    for i in 1..config.max_iter:
        if kill_file_exists(): return halt("stop.graceful" | "stop.hard")   # polling-pattern §6.1
        if wallclock_exceeded(): return halt("max_wallclock")
        if verify_oracle_integrity(manifest, rehash()) is Tampered:
            return halt("oracle_tampered", paths)            # §3
        result = run(oracle.command)                         # the controller runs it
        if result.exit == oracle.expected_exit:
            return success(i, evidence=result.output_tail)   # evidence per verification-gate
        sig = failure_signature(result.output)
        history.append(sig)
        if (h := detect_convergence_halt(history, config)):
            return halt(h)                                   # stall / oscillation
        implementer_fix(result.output)                        # maker: hand over the failure output to be fixed
    return halt("max_iter")
```

- The safety brakes (2 kill-file channels / max_iter / max_wallclock) reuse the values and
  semantics of polling-pattern §6. **Do not add an autonomous loop without brakes to this
  repository** ([orchestration-patterns.md](orchestration-patterns.md) governing principle 3)
- IterationResult / LoopResult carry structured fields only (no free text; the philosophy of
  polling-pattern §7):
  `LoopResult {iterations, converged: bool, halt_reason?, tampered_paths?, final_signature?}`

---

## 6. Default Config

```yaml
max_iter: 8
max_wallclock: 30m
stall_limit: 3        # stall after 3 consecutive identical signatures
window: 6             # observation window for oscillation detection
max_period: 3         # upper bound on the oscillation period to detect
```

## 7. When to Use Which

| Skill | Loop | Suited for |
|---|---|---|
| test-driven-development | Human-interactive RED-GREEN-REFACTOR | New implementation |
| iterate | Instruction-driven single-pass improvement | Follow-up fixes after cycle |
| **goal-loop (this contract)** | Autonomous repetition until the oracle converges | Explicit conditions of the form "until all tests are green", "until lint is zero" |
| issue polling | Queue consumption | Working through a volume of tasks |

## 8. References

- [polling-pattern.md](polling-pattern.md) — where the safety brakes / kill file / structured results are defined
- [verification-gate.md](verification-gate.md) — preventing completion claims without evidence (the oracle run log is the evidence)
- [orchestration-patterns.md](orchestration-patterns.md) — governing principles for autonomous loops
