## state_root Resolution

### Acquisition and fallback

The executable source of truth is
`python3 skills/github-issue/scripts/polling_adapter.py state-root --name-with-owner OWNER/REPO [--remote-url URL]`
— run it instead of re-deriving the procedure. The contract it guarantees:

1. **XDG fallback chain**: `XDG_STATE_HOME`, else `~/.local/state`; the resolved path is
   `{xdg}/claude-skills/github-issue/{repo_slug}-{clone_id}` where `repo_slug` is the
   `nameWithOwner → path segment` conversion (responsibility split: see
   [`cleanup-spec.md`](cleanup-spec.md)) and `clone_id` is the first 16 SHA-1 hex characters
   of the normalized git remote URL (a 64-bit space)
2. **URL normalization** (fail-closed): strict allow-list on the character set
   (`[a-zA-Z0-9._\-/:@]` only) and rejection of `..`; then lowercase, strip trailing `/`
   and `.git`, and rewrite `git@host:o/r` / `ssh://git@host/o/r` to `https://host/o/r`
3. **Creation and safety checks**: idempotent `mkdir` (mode 0700), `.clone_url` collision
   detection via O_CREAT|O_EXCL exclusive creation (TOCTOU-safe against concurrent first
   starts), ownership verification (`stat.uid == getuid()`), and FS-kind verification
   (fail-closed on the unsupported list — see §Platform Assumptions)
4. **Remote URL sourcing**: the script tries `git remote get-url origin` itself; when git
   cannot resolve it, the script exits 2 and the orchestrator re-invokes with
   `--remote-url` taken from the selected transport's repository metadata, or fails closed
   when neither source resolves

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

Every state **file update** is performed **atomically** with the `write_atomic` procedure
(tmp file with O_EXCL and mode 0600 → data fsync → same-directory atomic rename → parent
directory fsync). The executable source of truth is `polling_adapter.py` — the file-writing
subcommands (`increment-retry`, `session-save`, `recovery-marker add`) apply it; never
hand-roll the sequence in shell. Lock operations are the exception by design: `claim-lock`
writes under its flock guard and releases/stale-deletions are plain unlinks (a lockfile's
consistency comes from the flock + pid lease, not from rename atomicity).

- **Supported FS**: ext4, btrfs, xfs, apfs (local filesystems only)
- **Unsupported / fail-closed**: NFS, CIFS, tmpfs (rename atomicity and fsync semantics are non-standard), and a WSL mount over Windows DrvFs (permission modes are not reflected). Determined with `statfs(2)`; on detection, **a warning log + polling abort (fail-closed)**. To prevent silent data corruption, a warning alone is not enough
- **Ownership verification**: when state_root is opened, `stat(path).uid != getuid()` is fail-closed (so that under a shared HOME you never mistakenly write into a state_root created by another user)
- **Stale lockfile**: `<state_root>/claim/{N}.lock` records the owner pid as the lease;
  flock(2) guards only the read-modify-write inside each CLI invocation (the old
  held-until-process-exit model presumed a long-lived adapter process — see
  [adapter-internals.md](adapter-internals.md) for the Why-not). A live recorded pid means
  LockBusy regardless of age; when the pid is dead, `rollback_orphans()` deletes the file on
  the condition that at least 5 minutes have passed

### `.polling-initialized` Lifecycle

- **Creation responsibility**: the polling-adapter creates it automatically **after the first successful tick** (via `write_atomic`)
- **The definition of a successful tick**: the moment a tick completes with `halt_reason=None` or `halt_reason="dry_run"`
- **Update**: once created it is never updated (the mtime remains as the last initialization time)
- **Deletion**: when the user deletes it manually with `rm <state_root>/.polling-initialized`, the next tick again forces `--dry-run` (for deliberate re-confirmation)
- **At alias removal**: it is not a deletion target (it stays as-is even in the 1.16.0 alias-removal cycle)

---

