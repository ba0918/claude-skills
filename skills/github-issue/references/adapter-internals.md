## claim() 3 Layers of Defense

Execute the following 3 layers **in this order**. If even one fails, quietly abort with `ClaimFailed{reason}` (no retry).

Input validation comes first: `polling_adapter.py validate-slug SLUG` — the part after
`issue-` must match `^[1-9][0-9]*$` **as a raw string** (validating after `int()` would
silently normalize `007` to `7`); anything else is fail-closed.

- **① Local lockfile**: `polling_adapter.py claim-lock N --state-root DIR --owner-pid PID`.
  On `LockBusy`, quiet abort (no retry). The script uses flock(2) as the read-modify-write
  guard and records the owner pid as the lease — the original "hold the flock until process
  exit" presumed a long-lived adapter process that does not exist in CLI-driven execution,
  so cross-tick exclusivity rests on the recorded pid's liveness instead (the script
  carries this Why-not in its comments)
- **② Transport update**: add the current actor + `claude-running` through the selected
  transport. On failure, `release-lock` and `ClaimFailed`
- **③ Re-verify** (detecting a post-claim race): `get_issue` for assignees/labels; when the
  current actor or `claude-running` is missing, roll the partial claim back (remove label,
  remove actor, then `release-lock N --state-root DIR --owner-pid PID` — it unlinks only when
  the recorded pid matches the owner or is dead) and return `ClaimFailed("post-claim verify failed")`

- A **stale lockfile** (mtime at least 5 minutes old + dead pid) is deleted by
  `polling_adapter.py stale-locks --state-root DIR` (rollback step ②); a live pid always
  means LockBusy regardless of age

The SKILL.md side does not know the internal structure of the 3 layers and only needs to call `claim(slug)` (Layer Separation).

---

## rollback_orphans Sub-Steps

`rollback_orphans(now)` executes in 5 stages. Each stage has **no early return and runs to completion**. Each stage is decomposed into an internal private submethod, guaranteeing that each stage is unit-testable.

```
rollback_orphans(now) -> list[Slug]:
  recovered = []
  recovered += _check_worktree_orphans(now)      # ①
  recovered += _check_stale_locks(now)           # ②
  recovered += _check_long_running(now)          # ③
  recovered += _check_recovery_markers(now)      # ④
  recovered += _check_closed_with_labels(now)    # ⑤
  return recovered
```

### ① `_check_worktree_orphans(now)`

Delete orphaned worktrees following the 24h + merged conditions of the existing [`cleanup-spec.md`](cleanup-spec.md).

### ② `_check_stale_locks(now)`

Run `polling_adapter.py stale-locks --state-root DIR` (the executable source of truth). It
scans `<state_root>/claim/*.lock`, deletes entries whose mtime is at least 5 minutes old and
whose recorded pid is dead (`kill(pid, 0)` → ESRCH), and reports what it deleted.

### ③ `_check_long_running(now)`

`release()` issues that have carried `claude-running` for a long time:

1. Enumerate with one `list_issues` operation filtered by `claude-running` and open state, requesting number/createdAt/updatedAt
2. Decide the reference time for each issue:
   - No PR created yet: use `issue.created_at` as the reference → `release()` past 48h
   - A PR exists: use `pr.head commit pushed_at` (or `pr.created_at` if absent) as the reference → `release()` past 48h
3. **A hard cap that forces `release()` once 7 days have passed since `issue.created_at`**
   - Reason: `updated_at` is refreshed by comments, which carries a risk of orphan-pinning DoS by an external user, so it is not adopted
   - The 7-day hard cap guarantees that an external attacker cannot stretch the running state indefinitely

**The per-tick API cap**: `get_issue` calls are limited to at most `rollback_gh_fetch_cap` (default 10) per tick. The excess carries over to the next tick.

### ④ `_check_recovery_markers(now)`

Enumerate with `polling_adapter.py recovery-marker list --state-root DIR` (each entry
carries its mtime and a 7-day-TTL-exceeded flag) and re-evaluate the issues whose
`mark_failed` failed. The issue-state judgments below need the selected transport, so they
stay with the orchestrator; deletion goes through `recovery-marker delete N`.

For each marker, the state of the corresponding issue:
- **closed** (`mark_done` already completed) → delete the marker (no cleanup needed)
- `claude-auto` **absent** → delete the marker (a human has already handled it)
- `claude-auto` only → delete the marker; it becomes a normal claim target on the next tick
- `claude-auto + running/review` → `release(slug)` to remove claude-running/review, then delete the marker. Re-evaluated on the next tick
- `claude-auto + failed-{transient,permanent}` → delete the marker (the previous attempt succeeded after a delay, or a human added it manually)

**The per-tick API cap**: up to `rollback_gh_fetch_cap` (default 10) combined with step ③. The excess carries over to the next tick.

**A 7-day TTL for stale markers**: a marker whose mtime is at least 7 days old is treated as "stale / a bug" and gets a warning log + deletion (preventing indefinite leftovers).

**The atomicity of marker deletion**: deleting the marker is the last step after the judgments above. Even a crash before deletion is harmless, because the same judgment runs idempotently on the next tick.

### ⑤ `_check_closed_with_labels(now)`

Clean up any `claude-*` labels left on a closed issue (recovering from a partial failure of `mark_done`):

Call `list_issues` for closed issues carrying `claude-auto`, requesting number with limit 100,
then run label cleanup for each issue (re-running `mark_done` step 3).

---

## Parallel Precedence

For the relationship between `parallel_worktree_limit` and `max_parallel`, see the precedence table in [`config-defaults.md`](config-defaults.md). The effective cap is `effective_parallel = min(max_parallel, parallel_worktree_limit)`.
