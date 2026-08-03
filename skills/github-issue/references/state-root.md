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
  # Fallback: the selected transport's repository metadata
  try:
    return github.repository_info().url
  except GitHubTransportError:
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

