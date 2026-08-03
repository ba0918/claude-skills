## FS Retry State

### Schema

`<state_root>/retry/{issue_number}.json`:

```json
{
  "retry_count": 2,
  "last_failed_at": "2026-04-08T16:40:19Z",
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Atomic Write

Updated with the `write_atomic` procedure:

1. Write to `{issue_number}.json.tmp.{pid}.{random}`
2. Persist the data with `fsync(tmp_fd)`
3. Replace atomically with `rename(tmp, target)`
4. Persist the directory entry with `fsync(parent_dir_fd)`

### `run_id` (UUID v4) generation/validation

- Generation: issued once with `uuid4()` at the start of each tick, and the same value is reused throughout the loop
- Form: UUID v4 (`xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`)
- Validation on read: when it does not match the regular expression `^[0-9a-f-]{36}$`, a warning is logged and that field is ignored (treated as `null`)
- Even on a mismatch, reading the other fields (`retry_count`, `last_failed_at`) continues

### The quarantine rename on detecting corrupt JSON

1. When the JSON fails to parse on read, emit a warning log
2. Quarantine the file by renaming it to `<issue_number>.json.corrupt.{unix_timestamp}`
3. Treat it as `retry_count = 0`; the next write creates a new file
4. On **2 consecutive parse failures** (a new write after quarantine also fails to parse), `fail_closed("retry state corruption")` aborts polling
5. Quarantined files are kept for manual investigation (no TTL; deleted at the operator's discretion)

---

## error_kind Enum

The `error_kind` used by `mark_failed` / `classify_failure` is restricted to the following closed enum. An unknown value is normalized to `"unknown"`, and `classify_failure` is fail-closed by `unknown → Permanent`.

```
error_kind ∈ {
  # Transient (retryable)
  "network",           # Network I/O error, HTTP 5xx, SIGPIPE, broken pipe
  "rate_limit",        # GitHub/Codex API rate limit (HTTP 403 rate, 429)
  "timeout",           # Codex or selected GitHub transport timeout
  "lock",              # lockfile contention (held by another process on the same machine)
                       # SPECIAL: not counted toward failed_streak (silent skip)

  # Permanent (awaiting human judgment)
  "test",              # Test failure
  "compile",           # Build/compile failure
  "abort",             # Cycle explicit abort
  "lgtm_parse_fail",   # Codex JSON parse error (still failing after 1 retry)
  "sanitize_failed",   # sanitize_slug rejection
  "security",          # secret scanner hit, auth failure, untrusted content policy violation
  "not_found",         # selected transport reports that the issue/PR disappeared
  "tool_missing",      # no selected GitHub transport is usable, or git is absent
  "unknown"            # an unknown exception (Permanent, as fail-closed)
}
```

### Transient / Permanent classification

- **Transient** (4 kinds): `network`, `rate_limit`, `timeout`, `lock`
- **Permanent** (9 kinds): `test`, `compile`, `abort`, `lgtm_parse_fail`, `sanitize_failed`, `security`, `not_found`, `tool_missing`, `unknown`

### error_kind Handling Rules

The `failed_streak` counting convention (a GitHub-adapter-specific addition to the shared contract §6 safety brake):

- **`lock` is not counted toward `failed_streak`** (a silent skip)
  - Reason: it means "another process is handling this", so it is treated as a skip of that issue
  - Because it is not an issue-specific failure, it does not increment `failed_streak`
  - Treating it as a failure of the whole tick would falsely trigger the safety brake
- Every other error_kind increments `failed_streak`

For the detailed definition of `normalize_github_error`, see [`codex-review-loop.md §normalize_github_error`](codex-review-loop.md#normalize_github_error).

---

