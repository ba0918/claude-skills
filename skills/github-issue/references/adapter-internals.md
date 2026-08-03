## claim() 3 Layers of Defense

Execute the following 3 layers **in this order**. If even one fails, quietly abort with `ClaimFailed{reason}` (no retry).

```
claim(slug) -> ClaimResult:
  # Input validation: match the raw string, never the parsed integer.
  # int() then re-stringifying silently normalizes "007" to "7", so a
  # zero-padded slug would pass a check applied after the conversion.
  raw = slug.removeprefix("issue-")
  if not re.match(r'^[1-9][0-9]*$', raw):
    fail_closed(f"invalid issue_number: {raw!r}")
  N = int(raw)

  # ① Local lockfile (flock(2) non-blocking)
  lock_path = state_root / "claim" / f"{N}.lock"
  try:
    lock_fd = open(lock_path, O_WRONLY|O_CREAT, mode=0o600)
    flock(lock_fd, LOCK_EX | LOCK_NB)
    write(lock_fd, str(pid))
    fsync(lock_fd)
  except BlockingIOError:
    return ClaimFailed("LockBusy")  # quiet abort

  # ② add the current actor + claude-running through the selected transport
  try:
    github.add_issue_actor(N)
    github.edit_issue_labels(N, add=["claude-running"], remove=[])
  except GitHubTransportError as e:
    close(lock_fd)
    return ClaimFailed(f"github update failed: {e}")

  # ③ re-verify (detecting a post-claim race)
  result = github.get_issue(N, fields=["assignees", "labels"])
  if current_actor not in result.assignees or "claude-running" not in result.labels:
    # Partial claim rollback
    github.edit_issue_labels(N, add=[], remove=["claude-running"])
    github.remove_issue_actor(N)
    close(lock_fd)
    return ClaimFailed("post-claim verify failed")

  return ClaimOk(lock_fd)  # lock_fd is held until the process exits
```

- **The lockfile is released automatically when the process exits** (the kernel releases the flock on `close` or `exit`)
- A **stale lockfile** is deleted by `rollback_orphans()` on the condition of 5 minutes elapsed + a dead pid

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

Scan `<state_root>/claim/*.lock`:
- Delete when the mtime is at least 5 minutes old and the pid is dead
- Determine deadness by `kill(pid, 0)` on the pid written inside the lockfile returning ESRCH

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

Scan `<state_root>/recovery/*` and re-evaluate the issues whose `mark_failed` failed.

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
