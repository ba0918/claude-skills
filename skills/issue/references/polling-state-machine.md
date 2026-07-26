# Issue Polling — Pure Function Specifications

> **The positioning of this file:** the implementation specification, on the issue adapter side, of the pure functions declared in `skills/shared/references/polling-pattern.md` §4 (including the exhaustive match tables).

The shared contract: [../../shared/references/polling-pattern.md](../../shared/references/polling-pattern.md)

---

## 1. `transition(state, event) -> NextState | InvalidTransition`

**A pure function.** No side effects. It returns a match agreeing exactly with the Transition Table of shared contract §2.

### Full Match Table

| Input (state, event) | Output |
|---|---|
| (`ready`, `claim`) | `running` |
| (`running`, `cycle_success`) | `done` |
| (`running`, `cycle_fail_transient`) | `failed/transient` |
| (`running`, `cycle_fail_permanent`) | `failed/permanent` |
| (`running`, `sigint`) | `ready` |
| (`done`, `month_boundary`) | `archives` |
| (`failed/transient`, `retry_under_limit`) | `ready` |
| (`failed/transient`, `retry_over_limit`) | `failed/permanent` |
| **Any other (state, event)** | `InvalidTransition{state, event}` |

### Examples

- `transition(ready, claim)` → `running`
- `transition(done, claim)` → `InvalidTransition` (done is not a claim target)
- `transition(failed/permanent, retry_under_limit)` → `InvalidTransition` (permanent is never retried, contract §8)

---

## 2. `classify_failure(error_kind) -> Transient | Permanent`

**A pure function.** It takes the error-kind string and sorts it into 2 classes.

| `error_kind` | Classification |
|---|---|
| `network_error` | `Transient` |
| `timeout` | `Transient` |
| `file_lock` | `Transient` |
| `rate_limit` | `Transient` (the backoff is exponential, contract §8) |
| `test_failure` | `Permanent` |
| `compile_error` | `Permanent` |
| `cycle_abort` | `Permanent` |
| `invalid_input` | `Permanent` |
| **Unknown** | `Permanent` (fail-closed) |

**Falling to `Permanent`** for the unknown is the fail-closed principle (preferring a stop over a runaway).

---

## 3. `should_promote_to_permanent(retry_count, limit) -> bool`

**A pure function.** A pure comparison and nothing else.

```
should_promote_to_permanent(retry_count, limit) = (retry_count >= limit)
```

### Boundary Examples

| retry_count | limit | Result |
|---|---|---|
| 0 | 3 | `false` |
| 2 | 3 | `false` |
| 3 | 3 | `true` (the boundary) |
| 5 | 3 | `true` |

---

## 4. `month_boundary_crossed(now, last_check) -> bool`

**A pure function.** True when the `YYYY-MM` of `now` differs from that of `last_check`.

```
month_boundary_crossed(now, last_check) = (now.year_month != last_check.year_month)
```

### Examples

| now | last_check | Result |
|---|---|---|
| 2026-04-08 | 2026-04-01 | `false` |
| 2026-05-01 | 2026-04-30 | `true` |
| 2026-04-08 | `""` (unset) | `true` (the first time counts as crossed) |

The contract is that the caller normalizes the time and timezone before passing them (the pure function never obtains local time).

---

## 5. `session_resume_action(prev, now, config) -> Resume | StartNew | Halt{reason}`

**A pure function.** The resume judgment for a `--stateless` tick (contract §6.5). `now` is injected as an argument.

### Full Match Table

| `prev` | Condition | Output |
|---|---|---|
| `None` | — | `StartNew` |
| `halt_reason == "failed_streak"` | Always (even when expired) | `Halt{failed_streak}` (**sticky**, refused until `session.json` is deleted) |
| `halt_reason ∈ {max_iter, max_wallclock}` | `now - started_at <= max_wallclock` | `Halt{halt_reason}` |
| `halt_reason ∈ {max_iter, max_wallclock}` | `now - started_at > max_wallclock` | `StartNew` |
| `halt_reason == null` | `now - started_at > max_wallclock` | `StartNew` |
| `halt_reason == null` | `now - started_at <= max_wallclock` | `Resume` |

---

## 6. `next_session_state(session, tick_result) -> Session`

**A pure function.** The counter update after a tick completes (contract §6.5). The only input is the TickResult (it knows nothing of the adapter's circumstances).

| The tick's result | `failed_streak` | `iter_count` |
|---|---|---|
| `failed_transient + failed_permanent > 0` and `done == 0` | `+1` | `+1` |
| `done > 0` | Reset to `0` | `+1` |
| `claimed == 0` or `halt_reason == "dry_run"` | Unchanged | `+1` |

After updating the counters, write the halt judgment (`failed_streak >= limit` → `"failed_streak"`, `now - started_at > max_wallclock` → `"max_wallclock"`, `iter_count >= max_iter` → `"max_iter"`, in that order of priority) into `halt_reason` and return.

---

## 7. The properties of the pure functions (verification checklist)

- [ ] Never calls `now` / `random` / file I/O / network I/O
- [ ] Always returns the same output for the same input
- [ ] Expresses failure with a Result / union type rather than an exception (`InvalidTransition` and the like)
- [ ] `tick` is not on this list (it is an orchestrator and performs I/O; see contract §1 / §5)

---

## 8. References

- Shared contract §2 Transition Table (the `transition` in this file agrees exactly with the §2 table)
- Shared contract §4 Pure Function Signatures
- The FS adapter implementation: [./polling-state.md](./polling-state.md)
