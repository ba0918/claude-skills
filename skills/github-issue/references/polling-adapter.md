# Polling Adapter (Label-based)

The implementation specification of the Label state adapter of `skills/github-issue/`. It implements the state adapter interface of the shared contract [`skills/shared/references/polling-pattern.md`](../../shared/references/polling-pattern.md) with GitHub labels.

> **Heading Convention:** major sections use H2 (`##`), and subsections such as Interface methods use H3 (`###`). The `grep '^### '` pattern of the Tests checklist depends on this convention.

---

## Assumptions

This adapter presumes **a single host, a single process, a Ralph loop**.

- **Why a single host is presumed**:
  - A claim spans a mixed consistency domain of "a local lockfile + a GitHub label", and exclusion across several hosts grounded only in GitHub labels leaves a post-verify race
  - Because retry state is persisted on the FS (`<state_root>/retry/{N}.json`), polling the same repo from several hosts makes the state inconsistent
- **Unsupported**: distributed polling from several hosts, Windows native (WSL is unsupported over a DrvFs mount)
- **Supported**: the local filesystems of Linux / macOS (ext4, btrfs, xfs, apfs)

If multi-host support becomes necessary, perform "a redesign that moves the source of truth to the GitHub side" in Phase C.

---

## Interface Table

All 13 methods of the shared contract [§3 Interface Table](../../shared/references/polling-pattern.md#3-interface-table-the-state-adapter-contract) are implemented. The table below is the detailed implementation mapping of the Label adapter.

| Interface (§3) | The Label adapter implementation |
|---|---|
| `list_ready(limit)` | §`list_ready(limit)` |
| `claim(slug)` | §`claim(slug)` |
| `release(slug)` | §`release(slug)` |
| `mark_done(slug)` | §`mark_done(slug)` |
| `mark_failed(slug, kind)` | §`mark_failed(slug, kind)` |
| `retry_count(slug)` | §`retry_count(slug)` |
| `increment_retry(slug)` | §`increment_retry(slug)` |
| `kill_file_path()` | §`kill_file_path()` |
| `archive_month_boundary()` | §`archive_month_boundary()` |
| `rollback_orphans(now)` | §`rollback_orphans(now)` |
| `sanitize_slug(raw)` | §`sanitize_slug(raw)` |
| `load_session()` | §`load_session() / save_session(session)` |
| `save_session(session)` | §`load_session() / save_session(session)` |

### list_ready(limit)

The `list_ready(limit)` requirement of shared contract §3 mandates **early termination** (a full scan is forbidden; return as soon as `limit` entries are found). The Label adapter satisfies the early-termination contract with the combination of a server-side limit via `gh issue list --limit {limit}`, a single invocation, and a client-side filter (no re-fetch).

Fetch with a **single invocation** of `gh issue list --label claude-auto --state open --json number,title,labels,author,authorAssociation --limit {limit}`.

1. The client-side filter:
   - Carries `claude-running` → exclude
   - Carries `claude-review` → exclude (a running substate)
   - `state_of_failure(labels) is not None` → exclude (see §Label Mapping)
   - `authorAssociation` is not contained in `require_author_association` → exclude
2. **Do not re-fetch even when the post-filter count is below `limit`** (re-fetch on the next tick. This prevents a fetch storm from repeated fetching. Propagation of stale state stays bounded by `tick_interval_loop_mode = 30s`)
3. The return value is a `list[Slug]` in the form `slug = f"issue-{number}"`

### claim(slug)

The 3 layers of defense are hidden as **an internal implementation detail of the adapter**. SKILL.md only calls `claim(slug)`.

For details see §`claim() 3 Layers of Defense`. On failure it returns `ClaimFailed{reason}` and quietly aborts (no retry).

**Input validation**: the part of the slug after `issue-` must match the regular expression `^[1-9][0-9]*$` **as a raw string**. Anything else (non-numeric, negative, zero-padded, `0`) is `fail_closed("invalid issue_number")`. Applying the pattern after `int()` would not do: the conversion normalizes `007` to `7`, so a zero-padded slug would pass a check placed downstream of it. `invalid issue_number` is the single failure identifier for this gate — the same string appears in [SKILL.md](../SKILL.md)'s pre-check so that one search finds every occurrence.

### release(slug)

```
gh issue edit ${N} --remove-label claude-running --remove-assignee @me
```

Executed best-effort. Even on failure, only a warning is logged and processing continues (the next tick's `rollback_orphans()` reclaims it).

### mark_done(slug)

Execute the 3 steps **in this order**. A failure at any step is recovered by the next tick's `rollback_orphans()` step ⑤ (cleaning up leftover labels on closed issues).

```
# 1. PR merge
gh pr merge <PR> --squash --delete-branch

# 2. Issue close
gh issue close ${N}

# 3. Label cleanup (a single edit)
gh issue edit ${N} \
  --remove-label claude-auto \
  --remove-label claude-review \
  --remove-label claude-failed-transient \
  --remove-label claude-failed-permanent \
  --remove-label claude-failed
```

A partial failure (for example, close succeeded and the label cleanup failed) is detected as "a closed issue with a `claude-*` label" by the next tick's `rollback_orphans()` step ⑤ and cleaned up.

### mark_failed(slug, kind)

**An atomic dual-write of the new and old labels in a single `gh issue edit`, plus verification, plus a recovery marker.**

```
mark_failed(slug, kind) -> Result:
  labels_add = ["claude-failed-transient", "claude-failed"] if kind == TRANSIENT
               else ["claude-failed-permanent", "claude-failed"]

  for attempt in [1, 2, 3]:  # up to 3 times, backoff intervals 0s/1s/2s
    try:
      gh issue edit ${N} --add-label <labels_add[0]> --add-label <labels_add[1]>
      labels_now = gh issue view ${N} --json labels --jq '.labels[].name'
      if all(L in labels_now for L in labels_add):
        record_fs_state(slug, kind)  # completes in the same tick as the FS retry state update
        return Ok
    except GhApiError as e:
      if attempt == 3: break
      sleep(attempt - 1)  # 0s, 1s, 2s

  # every attempt failed — return the claim to ready with a compensating action
  # Crash-safe ordering invariant:
  #   CA-1: persist the recovery marker to the FS with write_atomic (before release)
  #   CA-2: release(slug) removes claude-running / the assignee
  # With this order, even a crash between CA-1 and CA-2 is always reclaimed via the marker.
  # In the reverse order (release → marker), a failed marker write after release leaves
  # 0 labels and no marker, making it untraceable.
  warn_log(f"[mark_failed] verification failed after 3 attempts: {slug}")
  try:
    record_recovery_marker(slug)   # CA-1: persist the FS marker with write_atomic
  except FsError:
    fail_closed("cannot write recovery marker — polling abort")
  release(slug)                    # CA-2: remove the label/assignee on GitHub (best-effort)
  return Err("dual_write_failed")  # picked up by rollback_orphans() step ④ on the next tick
```

**The permitted intermediate states**:
- On the adding side: 0 labels (everything failed, with a recovery marker) or 2 labels (normal). A 1-label state is detected by the verification and retried
- **Never leave 0 labels unattended**: when the verification ultimately does not pass, always place a `<state_root>/recovery/{N}` marker so the next tick's `rollback_orphans()` re-evaluates it

### retry_count(slug)

**Reads the FS state**: read `<state_root>/retry/{issue_number}.json` and return `{retry_count, last_failed_at, run_id}`.

- No file → `0` (treated as the first time)
- JSON parse failure → a warning log, quarantine the file by renaming it to `<issue_number>.json.corrupt.{ts}`, and `0` (recreated)
- On **2 consecutive parse failures** (a new write after quarantine also fails to parse), `fail_closed("retry state corruption")` aborts polling
- The `run_id` field is in UUID v4 form; on read it is strictly validated against the regular expression `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`, and on a mismatch it is warned about and ignored (reading the other fields continues)
- **`retry_count` type/range validation**: it must be `int >= 0` and `< 10000`. A non-integer, a negative value, or 10000 and above produces a warning log and `0` (recreated, preventing a maliciously large written value from falsely triggering `should_promote_to_permanent`)
- **`last_failed_at` format validation**: an ISO8601 form (`YYYY-MM-DDTHH:MM:SSZ` and the like). On a parse failure it is warned about and treated as `null` (retry_count is retained)

### increment_retry(slug)

**Updates the FS state**: follow the `write_atomic` procedure of `.tmp` → fsync → rename → parent fsync. On the single-process premise, the atomicity of the read-modify-write is protected by flock.

- Posting a comment is **abolished** (eliminating both the race condition and the trust-boundary bypass)
- Returns the new count value

### kill_file_path()

Returns the absolute path pair `(<state_root>/.STOP.hard, <state_root>/.STOP)` (**the return order is the check order**, hard takes priority. Conforms to shared contract §3). For resolving `state_root`, see §`state_root Resolution`.

### load_session() / save_session(session)

The tick session of shared contract §6.5. Read and write `<state_root>/session.json` with the `write_atomic` procedure (§Platform Assumptions). A parse failure follows the same quarantine-rename convention as the FS Retry State (`.corrupt.{ts}`) and is treated as `None`.

### archive_month_boundary()

**A no-op on GitHub** (close is equivalent to archiving). The `<state_root>/.last_archive_month` cache is still updated (preserving the unchanged invariant of shared contract §9).

### rollback_orphans(now)

Executed in 5 stages. Each stage is decomposed into a `_check_*()` private submethod. For details see §`rollback_orphans Sub-Steps`.

### sanitize_slug(raw)

Merely calls `sanitize_slug` from the shared contract [§4 Pure Function Signatures](../../shared/references/polling-pattern.md#4-pure-function-signatures).

The Label-adapter-specific `sanitize_repo_slug` coexists with it, dedicated to the `nameWithOwner → path segment` conversion. **The canonical description of the responsibility split is placed in exactly one location, [`cleanup-spec.md`](cleanup-spec.md#sanitize_slug-vs-sanitize_repo_slug-responsibility-separation)**, and this file holds only a link reference to it (preventing a DRY violation).

---

## Label Mapping

**This section is the canonical SSOT.** The plan, `label-spec.md`, and the other references hold only direct links to this section and must never duplicate the body of the mapping table.

### State Mapping Table

| Shared contract State (§2) | The GitHub label set | Notes |
|---|---|---|
| `ready` | `{claude-auto}` only | `claude-running` / `claude-review` / `claude-failed-*` / `claude-failed` not attached |
| `running` | `{claude-auto, claude-running}` | The initial running |
| `running` (substate: review) | `{claude-auto, claude-running, claude-review}` OR `{claude-auto, claude-review}` | **A GitHub-specific intermediate state.** Subsumed into `running` of shared contract §2 |
| `done` | (already closed)| Every `claude-*` is removed at the moment of close |
| `failed/transient` | `{claude-auto, claude-failed-transient}` (+ the alias `claude-failed` dual-write) | Retryable on the next tick |
| `failed/permanent` | `{claude-auto, claude-failed-permanent}` (+ the alias `claude-failed` dual-write) | Awaiting human judgment |
| `archives` | — | On GitHub, close is equivalent to archives; no label is needed |

### is_running predicate (substate unification)

```
is_running(labels) := "claude-running" ∈ labels OR "claude-review" ∈ labels
```

`claude-review` does not appear in the state set of shared contract §2. It is isolated as a running substate inside the Label adapter, and the client-side filter of `list_ready()` excludes both.

### state_of_failure Precedence Rule

```
# Precedence: when a new label is present, ignore the old alias (guarding against a stale leftover)
state_of_failure(labels):
  if "claude-failed-transient" ∈ labels and "claude-failed-permanent" ∈ labels:
    warn("invalid state: both failure labels present")
    return PERMANENT                               # an invalid state is fail-closed (see below)
  if "claude-failed-transient" ∈ labels:  return TRANSIENT
  if "claude-failed-permanent" ∈ labels:  return PERMANENT
  if "claude-failed" ∈ labels:             return PERMANENT  # legacy alias
  return None

is_failed_transient(labels) := state_of_failure(labels) == TRANSIENT
is_failed_permanent(labels) := state_of_failure(labels) == PERMANENT
is_any_failed(labels)       := state_of_failure(labels) is not None
```

**Invalid-state detection**: when both `claude-failed-transient` and `claude-failed-permanent` are attached at once, treat it as an invalid state: a warning log plus handling as `failed/permanent` (fail-closed).

---

## state_root Resolution

### Acquisition and fallback

```python
def state_root(name_with_owner: str) -> Path:
  # 1. XDG fallback chain
  xdg_base = env("XDG_STATE_HOME") or expanduser("~/.local/state")

  # 2. Repo slug (the path segment conversion)
  repo_slug = sanitize_repo_slug(name_with_owner)  # see cleanup-spec.md

  # 3. Clone ID: identify with 16 SHA-1 hex characters after normalizing the git remote URL
  git_remote_url = fetch_git_remote_url()
  normalized = normalize_git_url(git_remote_url)
  clone_id = sha1(normalized).hex[:16]  # a 64-bit space

  target = path.join(xdg_base, "claude-skills", "github-issue", f"{repo_slug}-{clone_id}")

  # 4. Creation (idempotent)
  mkdir(target, mode=0o700, parents=True, exist_ok=True)

  # 5. Collision detection: create .clone_url exclusively with O_CREAT|O_EXCL
  stored_url_file = target / ".clone_url"
  if stored_url_file.exists():
    if read(stored_url_file) != normalized:
      fail_closed(f"state_root clone_id collision: {target}")
  else:
    # O_CREAT|O_EXCL exclusive creation (avoiding the TOCTOU race when several processes start for the first time at once)
    try:
      fd = open(stored_url_file, O_WRONLY|O_CREAT|O_EXCL, mode=0o600)
      write(fd, normalized)
      fsync(fd)
      close(fd)
      fsync(parent_dir_fd)
    except FileExistsError:
      # another process created it first → re-read and verify equality
      if read(stored_url_file) != normalized:
        fail_closed(f"state_root clone_id collision after race: {target}")

  # 6. Ownership verification (guarding against a shared HOME)
  if stat(target).uid != getuid():
    fail_closed(f"state_root ownership mismatch: {target}")

  # 7. FS-kind verification (fail-closed on an unsupported FS)
  fs_type = statfs(target).f_type
  if fs_type in UNSUPPORTED_FS:  # NFS, CIFS, tmpfs, DrvFs
    fail_closed(f"unsupported filesystem: {fs_type}")

  return target

def fetch_git_remote_url() -> str:
  # Primary: git remote get-url origin
  try:
    return shell("git remote get-url origin").strip()
  except GitNotFound:
    pass
  # Fallback: gh repo view
  try:
    return shell("gh repo view --json url --jq .url").strip()
  except GhError:
    fail_closed("cannot resolve git remote URL")

def normalize_git_url(url: str) -> str:
  # The normalization rules:
  # 0. Strict allow-list validation of the URL character set
  # 1. lowercase
  # 2. strip a trailing slash / .git
  # 3. git@host:owner/repo.git → https://host/owner/repo
  # 4. ssh://git@host/owner/repo → https://host/owner/repo

  # STEP 0: strict allow-list validation of the URL character set
  # Allowed: only [a-zA-Z0-9._\-/:@] (enough for path segments / the scheme separator)
  # Forbidden: consecutive `..`, `\`, spaces, tabs, newline, shell metachars ($, `, ', ", ;, &, |, <, >)
  if not re.match(r'^[a-zA-Z0-9._\-/:@]+$', url):
    fail_closed(f"invalid git remote url character set: {url!r}")
  if ".." in url:
    fail_closed(f"git remote url contains path traversal: {url!r}")

  lower = url.lower()
  # git@github.com:foo/bar.git → https://github.com/foo/bar
  if match := re.match(r'^git@([^:]+):(.+?)(?:\.git)?$', lower):
    return f"https://{match.group(1)}/{match.group(2)}"
  # ssh://git@github.com/foo/bar.git → https://github.com/foo/bar
  if lower.startswith("ssh://"):
    lower = re.sub(r'^ssh://(?:git@)?', 'https://', lower)
  # https://...[.git][/] → canonical
  lower = re.sub(r'\.git$', '', lower)
  lower = lower.rstrip("/")
  return lower
```

### Behavior on a creation failure (fail-closed)

| Failure case | Behavior |
|---|---|
| `permission denied` (mkdir) | Warning log + polling abort (fail-closed) |
| `quota exceeded` | Same as above |
| `an error creating the parent` | Same as above |
| `clone_id collision` (stored_url mismatch) | Warning log + polling abort + operator notification |
| `failure to obtain the git remote` | Polling abort (fail-closed) |
| `unsupported FS` (NFS / CIFS / tmpfs / a WSL mount over DrvFs) | **Warning log + polling abort (fail-closed)**. Because fsync/rename atomicity is not guaranteed, silent data corruption is structurally eliminated |
| `ownership mismatch` (`stat.uid != getuid()`) | fail-closed |
| An invalid URL character set | fail-closed |
| A URL containing `..` | fail-closed |

This adapter **has no ephemeral fallback**. In an environment where `state_root` is unusable, polling itself is never started.

### The structure under `state_root/` and the permission contract

> **Roots (shared contract §1):** the `state_root` of this Label adapter is an XDG-based,
> machine-specific FS directory. Separately from the queue proper (the labels on GitHub), the
> control and session files (`.STOP` / `.STOP.hard` / `.polling-initialized` /
> `.last_archive_month` / `session.json`) live here. That is, in this adapter
> **`runtime_root == state_root`** (state_root is itself unshared and machine-specific, so no
> separation is needed). The control and session files that the shared contract writes as
> `<runtime_root>` are read in this adapter as living under `<state_root>` below.

```
<state_root>/                           dir mode 0700
  .clone_url                            file mode 0600  # for URL collision detection
  .STOP                                 file mode 0600  # graceful stop
  .STOP.hard                            file mode 0600  # hard stop
  .polling-initialized                  file mode 0600  # the first-run flag
  .last_archive_month                   file mode 0600  # the "YYYY-MM" cache
  session.json                          file mode 0600  # tick session (shared contract §6.5, only under --stateless)
  retry/                                dir mode 0700
    {issue_number}.json                 file mode 0600  # {retry_count, last_failed_at, run_id}
  claim/                                dir mode 0700
    {issue_number}.lock                 file mode 0600  # the lockfile for flock(2)
  recovery/                             dir mode 0700
    {issue_number}                      file mode 0600  # an empty file, the dual-write failure marker
```

---

## Platform Assumptions

This adapter presumes **the local filesystems of Linux / macOS**. The APIs it uses are a combination of the basic POSIX.1-2008 functions (`open`/`fsync`/`rename`) and OS-dependent APIs (`flock(2)` = a BSD extension, `statfs(2)`/`fstatfs(2)` for determining the FS kind), so it is operated as **"presuming a Linux/macOS local FS" rather than as purely POSIX-conformant**. Operation on Windows native or a non-Linux kernel is unsupported.

Every state file update is performed **atomically** by the following procedure:

```
write_atomic(path, content):
  tmp = path + ".tmp." + pid + ".{random}"
  open(tmp, O_WRONLY|O_CREAT|O_EXCL, mode=0o600)
  write(tmp, content)
  fsync(tmp_fd)                  # persisting the data
  close(tmp)
  rename(tmp, path)              # an atomic rename within the same directory
  fsync(parent_dir_fd)           # persisting the directory entry
```

- **Supported FS**: ext4, btrfs, xfs, apfs (local filesystems only)
- **Unsupported / fail-closed**: NFS, CIFS, tmpfs (rename atomicity and fsync semantics are non-standard), and a WSL mount over Windows DrvFs (permission modes are not reflected). Determined with `statfs(2)`; on detection, **a warning log + polling abort (fail-closed)**. To prevent silent data corruption, a warning alone is not enough
- **Ownership verification**: when state_root is opened, `stat(path).uid != getuid()` is fail-closed (so that under a shared HOME you never mistakenly write into a state_root created by another user)
- **Stale lockfile**: `<state_root>/claim/{N}.lock` records the pid and is held with flock(2). It is released automatically when the process exits. When the pid is dead, `rollback_orphans()` deletes it on the condition that at least 5 minutes have passed

### `.polling-initialized` Lifecycle

- **Creation responsibility**: the polling-adapter creates it automatically **after the first successful tick** (via `write_atomic`)
- **The definition of a successful tick**: the moment a tick completes with `halt_reason=None` or `halt_reason="dry_run"`
- **Update**: once created it is never updated (the mtime remains as the last initialization time)
- **Deletion**: when the user deletes it manually with `rm <state_root>/.polling-initialized`, the next tick again forces `--dry-run` (for deliberate re-confirmation)
- **At alias removal**: it is not a deletion target (it stays as-is even in the 1.16.0 alias-removal cycle)

---

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
  "timeout",           # Codex or gh CLI timeout
  "lock",              # lockfile contention (held by another process on the same machine)
                       # SPECIAL: not counted toward failed_streak (silent skip)

  # Permanent (awaiting human judgment)
  "test",              # Test failure
  "compile",           # Build/compile failure
  "abort",             # Cycle explicit abort
  "lgtm_parse_fail",   # Codex JSON parse error (still failing after 1 retry)
  "sanitize_failed",   # sanitize_slug rejection
  "security",          # secret scanner hit, auth failure, untrusted content policy violation
  "not_found",         # gh CLI 404 (the issue/PR disappeared)
  "tool_missing",      # gh CLI absent, an unsupported gh version, git absent
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

  # ② add the assignee + claude-running with gh issue edit
  try:
    shell(f"gh issue edit {N} --add-assignee @me --add-label claude-running")
  except GhError as e:
    close(lock_fd)
    return ClaimFailed(f"gh edit failed: {e}")

  # ③ re-verify (detecting a post-claim race)
  result = shell(f"gh issue view {N} --json assignees,labels")
  if "@me" not in result.assignees or "claude-running" not in result.labels:
    # Partial claim rollback
    shell(f"gh issue edit {N} --remove-label claude-running --remove-assignee @me")
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

1. Enumerate with `gh issue list --label claude-running --state open --json number,createdAt,updatedAt`
2. Decide the reference time for each issue:
   - No PR created yet: use `issue.created_at` as the reference → `release()` past 48h
   - A PR exists: use `pr.head commit pushed_at` (or `pr.created_at` if absent) as the reference → `release()` past 48h
3. **A hard cap that forces `release()` once 7 days have passed since `issue.created_at`**
   - Reason: `updated_at` is refreshed by comments, which carries a risk of orphan-pinning DoS by an external user, so it is not adopted
   - The 7-day hard cap guarantees that an external attacker cannot stretch the running state indefinitely

**The per-tick API cap**: `gh issue view` calls are limited to at most `rollback_gh_fetch_cap` (default 10) per tick. The excess carries over to the next tick.

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

```
gh issue list --state closed --label claude-auto --json number --limit 100
# run the label cleanup for each issue (re-running mark_done step 3)
```

---

## Parallel Precedence

For the relationship between `parallel_worktree_limit` and `max_parallel`, see the precedence table in [`config-defaults.md`](config-defaults.md). The effective cap is `effective_parallel = min(max_parallel, parallel_worktree_limit)`.
