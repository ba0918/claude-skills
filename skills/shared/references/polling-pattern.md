# Polling Pattern — Shared Contract

> **⚠️ Warning:** A change to this contract affects every state adapter implementation that references it (`skills/issue/`, the future `skills/github-issue/`, and so on). When changing the states, the transitions, the interface, or the pure-function signatures, update the references and SKILL.md of every adapter in sync.
>
> **Drift Prevention Rule:** each adapter's `SKILL.md` and `references/polling-*.md` must **link directly** to the section headings of this contract, and describe in their local references only the parts specific to them (the FS layout, label names, rollback procedures, and so on). The shared specification must never be duplicated into local references.

---

## 1. Overview

This contract defines the shared specification for Ralph-loop-style polling, in which "a single process keeps consuming the ready queue endlessly until it is killed". The responsibility boundaries are:

| Layer | Responsibility | Pure? |
|---|---|---|
| Pure Functions | State transitions, classification, decisions | ✅ |
| State Adapter | Persistence involving I/O (FS / Label / DB) | ❌ |
| Tick Orchestrator | Composes the adapter and the pure functions to run one tick | ❌ |
| Loop Controller | Repetition under `--loop`, and monitoring the safety brakes | ❌ |
| Command | Flag parsing + starting the orchestrator | ❌ |

**tick is not a pure function.** The only genuinely pure functions are the four in §4.

### Roots: state_root and runtime_root

A polling adapter has two persistence roots. The separation keeps control and session files out of the artifact store:

| Root | What it holds | Shareability |
|---|---|---|
| `<state_root>` | The queue itself (`ready` / `running` / `done` / `failed` / `archives` and their index) | Adapter-dependent. In the FS adapter it is a project artifact (an artifact — it can become the subject of sharing and migration) |
| `<runtime_root>` | Machine-specific control and session files: the kill files (`.STOP` / `.STOP.hard`), the first-run policy marker (`.polling-initialized`), the monthly cache (`.last_archive_month`), the tick session (`session.json`) | Always machine-specific. **Never the subject of sharing or migration, at any visibility** |

- **An adapter whose state_root contains artifacts must separate `runtime_root` out of state_root.**
  In the FS adapter the queue itself is a project artifact (under the Artifact Store), so the control and session
  files are not mixed in and `runtime_root` is placed outside the artifact store (in this repository,
  [`.agents/runtime/`](artifact-store.md#runtime-area)).
- **An adapter whose state_root is itself machine-specific and unshared may set `runtime_root == state_root`.**
  Example: the XDG-based Label adapter already places all control files in its state_root (FS), so no
  separation is needed and `<state_root>` = `<runtime_root>`.
- Both roots **must be resolved to absolute paths** (no dependence on cwd). Wherever §6.1 / §6.5 / §9 / §10 below write
  `<runtime_root>`, adapters of the latter kind may read it as state_root.

---

## 2. Lifecycle State Machine

### States

| State | Meaning |
|---|---|
| `ready` | Claimable |
| `running` | Claimed, cycle in progress |
| `done` | Cycle succeeded, awaiting archival |
| `failed/transient` | A temporary error (retryable) |
| `failed/permanent` | A permanent error (awaiting human judgment) |
| `archives` | Archived monthly |

### Transition Table

| Current \ Event | `claim` | `cycle_success` | `cycle_fail_transient` | `cycle_fail_permanent` | `sigint` | `retry_under_limit` | `retry_over_limit` | `month_boundary` |
|---|---|---|---|---|---|---|---|---|
| `ready` | `running` | — | — | — | — | — | — | — |
| `running` | ❌ | `done` | `failed/transient` | `failed/permanent` | `ready` (rollback) | — | — | — |
| `done` | — | — | — | — | — | — | — | `archives` |
| `failed/transient` | — | — | — | — | — | `ready` | `failed/permanent` | — |
| `failed/permanent` | — | — | — | — | — | — | — | — |
| `archives` | — | — | — | — | — | — | — | — |

**An undefined cell returns an `InvalidTransition` error.** `—` marks a transition that cannot be reached; `❌` marks a contract violation.

---

## 3. Interface Table (the State Adapter contract)

Every state adapter must implement the following methods. The return types are at the declaration level.

| Method | Signature | Notes |
|---|---|---|
| `list_ready(limit)` | `(int) -> list[Slug]` | **Early termination is required.** Scanning everything is forbidden; return as soon as `limit` entries are found |
| `claim(slug)` | `(Slug) -> ClaimResult` | Atomic. Failure is `ClaimFailed{reason}` |
| `release(slug)` | `(Slug) -> None` | running → ready rollback |
| `mark_done(slug)` | `(Slug) -> None` | running → done |
| `mark_failed(slug, kind)` | `(Slug, FailureKind) -> None` | kind ∈ {transient, permanent}. The only things saved into the failed state are the `error_kind` enum, `retry_count` (int), `run_id` (the UUID of the tick/loop session), and `failed_at` (ISO8601) — a structured form. Free-form error messages, stack traces, and standard output **must not be saved** (to prevent context bloat and PII). `run_id` + `failed_at` make it possible to correlate with the cycle logs (in separate storage) after the fact |
| `retry_count(slug)` | `(Slug) -> int` | Gets the transient retry counter |
| `increment_retry(slug)` | `(Slug) -> int` | Returns the new count |
| `kill_file_path()` | `() -> (AbsPath, AbsPath)` | The absolute `(.STOP.hard, .STOP)` paths relative to `<runtime_root>`. **The return order = the check order** (hard first. The old specification, which returned graceful first, was abolished because misreading it risked missing a hard kill) |
| `load_session()` | `() -> Session \| None` | Reads `<runtime_root>/session.json` (the tick session of §6.5). `None` if absent |
| `save_session(session)` | `(Session) -> None` | Persists `<runtime_root>/session.json` (the tick session of §6.5) by atomic write (tmp → rename) |
| `archive_month_boundary()` | `() -> ArchivedCount` | An O(1) check via the `<runtime_root>/.last_archive_month` cache; the move is performed inside `<state_root>` only when a boundary is crossed |
| `rollback_orphans(now)` | `(Timestamp) -> list[Slug]` | Checks whether the pid in `running/{slug}/.claim` is alive → returns the slug to ready |
| `sanitize_slug(raw)` | `(str) -> Slug` | The pure function of §5 (the adapter merely calls the pure function) |

---

## 4. Pure Function Signatures

Only the following four functions are "genuinely pure" in this contract. All are free of side effects and use no time / random / I/O (`now` is injected as an argument).

| Function | Signature |
|---|---|
| `transition(state, event) -> NextState \| InvalidTransition` | A match based on the Transition Table of §2 |
| `classify_failure(error_kind) -> Transient \| Permanent` | network/timeout/lock/rate_limit → Transient; test/compile/abort → Permanent |
| `should_promote_to_permanent(retry_count, limit) -> bool` | `retry_count >= limit` |
| `month_boundary_crossed(now, last_check) -> bool` | Compares year and month only |

**Auxiliary pure functions (shared across adapters):**

| Function | Signature | Notes |
|---|---|---|
| `sanitize_slug(raw) -> Slug` | `(str) -> str` | Anything outside the whitelist `[a-zA-Z0-9._-]` becomes `_`, `..` becomes `__`, an empty string is rejected, and strings suggesting a symbolic link are rejected |
| `session_resume_action(prev, now, config) -> Resume \| StartNew \| Halt{reason}` | `(Session \| None, Timestamp, Config) -> Action` | The resume decision for the §6.5 tick session. A `failed_streak` halt is sticky (it never resumes automatically) |
| `next_session_state(session, tick_result) -> Session` | `(Session, TickResult) -> Session` | Updates the counters of the §6.5 tick session (iter_count / failed_streak) |

---

## 5. Tick Orchestration Pseudocode (declaration level)

> **Note:** this pseudocode illustrates the type flow; implementation differences are left to the adapter. Read control structures such as the `for` loop and counter increments as a conceptual diagram (they may be replaced with language-specific idioms).
>
> **Invariant:** the field set of `TickResult` is invariant (conforming to the §7 Schema). Only the control flow (`for` / `while` / counter increments and the like) may be replaced with a language-specific expression by the adapter; adding, removing, or renaming a field is a contract violation.

```
tick(adapter: StateAdapter, config: Config, now: Timestamp) -> TickResult:
    # 1. Safety brakes (the kill file takes top priority)
    (stop_hard, stop) = adapter.kill_file_path()   # return order = check order (hard first, §3)
    if exists(stop_hard): return TickResult(halt_reason="stop.hard")
    if exists(stop):      return TickResult(halt_reason="stop.graceful")

    # 2. Orphan recovery (recovery from a crash)
    adapter.rollback_orphans(now)

    # 3. Archive (O(1) via the month-boundary cache)
    adapter.archive_month_boundary()

    # 4. List ready (limit = max_parallel, early termination)
    ready_slugs = adapter.list_ready(config.max_parallel)
    if empty(ready_slugs): return TickResult()

    # 5. Atomic claim (skip the ones that fail)
    claimed = [s for s in ready_slugs if adapter.claim(s).ok]

    # 6. Dry run: return the claims without calling cycle
    if config.dry_run:
        for s in claimed: adapter.release(s)
        return TickResult(claimed=len(claimed), halt_reason="dry_run")

    # 7. Delegate to parallel-cycle (parallel worktrees)
    results = parallel_cycle_delegate(claimed)

    # 8. Classify & persist
    counter = {done:0, failed_transient:0, failed_permanent:0}
    for (slug, outcome) in results:
        kind = classify_failure(outcome.error_kind) if outcome.failed else None
        if outcome.success:
            adapter.mark_done(slug); counter.done += 1
        elif kind == Transient:
            n = adapter.increment_retry(slug)
            if should_promote_to_permanent(n, config.transient_retry_limit):
                adapter.mark_failed(slug, Permanent); counter.failed_permanent += 1
            else:
                adapter.mark_failed(slug, Transient); counter.failed_transient += 1
        else:
            adapter.mark_failed(slug, Permanent); counter.failed_permanent += 1

    return TickResult(claimed=len(claimed), **counter)
```

**`tick` performs I/O and is therefore not a pure function.** Only `transition` / `classify_failure` / `should_promote_to_permanent` / `month_boundary_crossed` are pure.

---

## 6. Safety Brakes

### 6.1 Kill File (the two-file scheme)

| File | Behavior | Purpose |
|---|---|---|
| `<runtime_root>/.STOP` | graceful: stops only new claims; a cycle already running finishes | An ordinary stop request |
| `<runtime_root>/.STOP.hard` | hard: sends SIGTERM to the running cycle as well, and rolls the claim back | Emergency stop |

- The paths **must be resolved as absolute paths under `<runtime_root>`** (no dependence on cwd. runtime_root is defined in §1 "Roots")
- Check them at the very start of the tick, in the order `.STOP.hard` → `.STOP`

### 6.2 Bounded Execution (a triple guard)

| Config | Default | Meaning |
|---|---|---|
| `max_iter` | 10 | The maximum number of ticks under `--loop` |
| `max_wallclock` | 1h | The maximum elapsed time of the whole loop |
| `failed_streak` | 3 | The maximum consecutive failures. Halt once exceeded |

### 6.2.1 A note on the responsibility boundary

The counters of the §6.2 triple guard (tick count / loop start time / consecutive failures) live in the Loop Controller's **process memory**.
That is valid only under the premise that "a single process keeps running under `--loop`". In stateless execution started from cron or a scheduler as
**one invocation = one tick**, the process dies every time, so the counters reset every time and
the triple guard is effectively disabled. In stateless execution, always use the Tick Session of §6.5.

### 6.3 SIGINT / SIGTERM Trap

- The loop controller installs a trap, rolls the current claim back with adapter.release, and then exits
- If the trap does not fire (SIGKILL / crash), the claim is recovered by `rollback_orphans(now)` at the start of the next tick

### 6.4 Orphan Recovery

- The adapter records **pid + started_at** in `running/{slug}/.claim` (FS) or in the claim metadata (Label and others)
- The FS adapter **SHOULD** create the `.claim` file with **permission mode `0600`**, assuming a multi-user environment (to prevent pid leakage). Where the mode is not fully honored on WSL / macOS / Linux (e.g. a noexec/DrvFs mount, a filesystem with ACLs), the adapter continues on a best-effort basis, emitting a warn log rather than stopping
- `rollback_orphans(now)` detects a dead pid and returns the corresponding slug to ready

### 6.5 Tick Session (persisting the safety brakes for stateless execution)

A persistent session that maintains the same triple-guard guarantee as §6.2 even when started from cron or a scheduler
(one invocation = one tick, with the process dying each tick). Used by ticks in `--stateless` mode.
**`--loop` and `--stateless` are mutually exclusive** (double bookkeeping of an in-process counter and a persistent counter is forbidden).

#### Session Schema

`<runtime_root>/session.json` (atomic write: tmp → rename. The mode follows the adapter's state-file convention):

```
Session {
  session_id:     UUID      # issued exactly once, when the session starts
  started_at:     ISO8601   # the session start time (the origin for max_wallclock)
  iter_count:     int       # the number of ticks completed in this session
  failed_streak:  int       # the number of consecutive failed ticks
  last_tick_at:   ISO8601
  halt_reason:    "max_iter" | "max_wallclock" | "failed_streak" | null
}
```

#### Pure functions (the §4 auxiliary pure functions)

**`session_resume_action(prev, now, config) -> Resume | StartNew | Halt{reason}`**

| State of `prev` | Action |
|---|---|
| `None` (no session) | `StartNew` |
| `halt_reason == "failed_streak"` | `Halt{failed_streak}` — **sticky**. It does not resume automatically even once the deadline passes; it refuses ticks until a human deletes `session.json` (consecutive failures await human judgment; fail-safe) |
| `halt_reason ∈ {max_iter, max_wallclock}` and `now - started_at <= max_wallclock` | `Halt{halt_reason}` — no resumption within the window (preventing an effectively infinite loop from cron firing repeatedly) |
| `halt_reason ∈ {max_iter, max_wallclock}` and the window has passed | `StartNew` |
| `halt_reason == null` and `now - started_at > max_wallclock` | `StartNew` (the previous session expired naturally) |
| `halt_reason == null` and within the window | `Resume` |

**`next_session_state(session, tick_result) -> Session`**

| Result of the tick | `failed_streak` | `iter_count` |
|---|---|---|
| A failed tick (`failed_transient + failed_permanent > 0` and `done == 0`) | `+1` | `+1` |
| A successful tick (`done > 0`) | Reset to `0` | `+1` |
| A no-op tick (`claimed == 0` or `halt_reason == "dry_run"`) | **Unchanged** (if an empty queue reset the streak, the brake would never fire) | `+1` |

> Adapter-specific non-counting conventions (e.g. the Label adapter's `error_kind = "lock"`) are handled before they
> reach the TickResult counters. These pure functions take only a TickResult as input and know nothing of adapter specifics.

#### Incorporation into the tick

A `--stateless` tick adds the following to the procedure of §5:

1. **Immediately after** Step 1 (the kill file check), evaluate `load_session()` → `session_resume_action(prev, now, config)`
   - `Halt{reason}` → finish immediately with `TickResult(halt_reason=reason)` (claiming nothing)
   - `StartNew` → issue a new session and continue / `Resume` → continue
2. After the tick completes (once the TickResult is settled), compute `next_session_state(session, tick_result)`,
   write the `session_halt` decision (`iter_count >= max_iter` → `"max_iter"`, `now - started_at > max_wallclock` → `"max_wallclock"`,
   `failed_streak >= failed_streak_limit` → `"failed_streak"`, in the precedence `failed_streak` > `max_wallclock` > `max_iter`) into
   `halt_reason`, and then `save_session()`

The kill file always takes precedence over the session (Step 1 comes first). The single-host premise is invariant, as in §6.4.

---

## 7. Tick Result Schema

**Structured counters only.** Free-form text, logs, and detailed messages are forbidden (to prevent context bloat).

```
TickResult {
  run_id:             UUID  # the unique ID of the tick or loop session (matching the value recorded in the frontmatter of a failed issue)
  tick_started_at:    ISO8601
  claimed:            int   # how many were claimed successfully in this tick
  done:               int   # how many succeeded
  failed_transient:   int   # how many were classified as transient
  failed_permanent:   int   # how many were classified as permanent
  halt_reason?:       "stop.graceful" | "stop.hard" | "max_iter" | "max_wallclock" | "failed_streak" | "dry_run"
}
```

`run_id` is identical to the value that `mark_failed` saves into the frontmatter of a failed issue, and is the only key by which the two can be correlated in a postmortem.

**`run_id` on an early halt**: for a tick that halted before the run_id generation step because of the kill file (§6.1) or the tick session (§6.5), `run_id` may remain ungenerated and be `null` (no claim occurred, so there is nothing to correlate with).

The loop controller aggregates only these counters, and assembles the human-facing summary at final output time.

Under `--stateless` (§6.5), the halt_reason for `max_iter` / `max_wallclock` / `failed_streak` is reported from
`session.json` rather than from process memory. The field set is invariant.

---

## 8. Retry Policy

| Failure Kind | Policy |
|---|---|
| `transient` (general) | Re-enqueued to ready on the next tick after **a fixed 30s** |
| `transient` (rate_limit) | **Exponential backoff** (30s → 60s → 120s → cap 10 min) |
| `permanent` | No retry. Awaits human judgment |

At `retry_count >= transient_retry_limit` it is promoted to `failed/permanent` (§4 `should_promote_to_permanent`).

---

## 9. Cleanup / Archive

- `done/{slug}` is moved to `archives/YYYY-MM/{slug}` when a month boundary is crossed
- The month-boundary decision is the pure function `month_boundary_crossed(now, last_check)`
- **When the cache is absent (the first run), create the cache only and perform no move** (the past month to move into cannot be determined. This structurally prevents an invalid path such as `archives/{empty string}/`)
- The adapter caches `YYYY-MM` in `<runtime_root>/.last_archive_month` (or an equivalent) and returns early in **O(1)** for ticks within the same month
- Only when a boundary is crossed does it scan `done/` and move entries

---

## 10. Default Config (conservative initial values)

```yaml
max_parallel: 4
max_iter: 10
max_wallclock: 1h
failed_streak_limit: 3
transient_retry_limit: 3
tick_interval_loop_mode: 30s
rate_limit_backoff: exponential  # 30s, 60s, 120s, cap=10m
dry_run: false                    # forced to true on the first run
```

**First-run policy**: when `<runtime_root>/.polling-initialized` does not exist, `--dry-run` is forced (so that the user understands the polling pattern once before entering real operation).

---

## 11. Drift Prevention Rules

1. Each adapter's SKILL.md **links directly** to the § numbers of this file (duplicating the body is forbidden)
2. The Transition Table, the Interface Table, and the pure-function signatures **must not be redefined** in local references
3. Only the specific parts go in local references:
   - FS: the directory layout, the atomic rename procedure, the implementation details of sanitize
   - Label: label names, GraphQL queries, the three-stage defense
4. A PR that changes this contract must include the synchronized update of every adapter's references in the same PR
