# Cleanup Specification

The rules for detecting and cleaning up orphaned worktrees and branches.

> **Drift Prevention (in compliance with shared contract §11)**: shared specifications such as the kill file, the SIGINT trap, and the orphan-recovery pure functions are consolidated in [`polling-pattern.md`](../../shared/references/polling-pattern.md). This file keeps only the GitHub-specific parts (`sanitize_repo_slug` / worktree naming / the 24h detection / Partial Claim Rollback).

## sanitize_slug vs sanitize_repo_slug Responsibility Separation

> **Canonical Location**: this section is the canonical SSOT. `polling-adapter.md` / `SKILL.md` / the other references hold only direct links to this section and never duplicate the definition of the responsibility split.

This skill has 2 similar sanitize functions. **They carry different responsibilities and must not be confused**:

| Function | Where it is defined | Input | Purpose | Responsibility |
|---|---|---|---|---|
| `sanitize_slug(raw)` | Shared contract [`polling-pattern.md §4`](../../shared/references/polling-pattern.md#4-pure-function-signatures) | An issue slug / state slug (e.g. `issue-42`)| Normalizing the slug handed to the shared contract's `list_ready` / `claim` / `mark_*` APIs | Shaping the slug format at the polling-contract level |
| `sanitize_repo_slug(raw)` | This file, §`sanitize_repo_slug()` | `nameWithOwner` (e.g. `owner/repo`)| Converting a path segment embedded in the lockfile / worktree / `state_root` directory names | **GitHub-specific** defense against path traversal and shell metacharacters |

**The must-not-confuse rules**:

- `sanitize_slug` is a pure function of the shared contract, and both the Label and FS adapters use the same one
- `sanitize_repo_slug` is specific to the GitHub Label adapter and exists solely for `nameWithOwner` → path segment
- The two differ in signature, in whitelist, and in purpose
- When adding new code, always consult this table and pick the appropriate function

This convention is referenced from `polling-adapter.md` and `SKILL.md` by direct links to this section (**the canonical copy is this one place only**).

## sanitize_repo_slug()

Whenever `nameWithOwner` (e.g. `owner/repo`) is embedded into a lockfile path, a worktree path, or a `state_root` directory name, always sanitize it with a whitelist approach.

```
sanitize_repo_slug(name_with_owner: str) -> str:
  # Whitelist: allow only [a-zA-Z0-9._-]. Replace everything else with '_'.
  # This structurally eliminates '/', null bytes, path-traversal characters, and shell metacharacters.
  value = regex_replace(name_with_owner, r"[^a-zA-Z0-9._-]", "_")
  # Defense in depth: '.' passes the whitelist, so '..' can survive.
  # Collapse it to '__' so audit tools and reviewers do not misread traces of path traversal.
  value = value.replace("..", "__")
  return value

# Examples:
# sanitize_repo_slug("owner/repo")        -> "owner_repo"
# sanitize_repo_slug("ev/il;rm -rf /")    -> "ev_il_rm_-rf__"
# sanitize_repo_slug("a/../b")            -> "a___b" ('..' disappears from both directions)
```

> The old implementation's `tr / -` lets dangerous characters other than `/` through (whitespace, `;`, `$`, null bytes, and so on), so it is not used.

## Worktree Naming Convention

```
gh-issue-{issue_number}-{yyyymmddhhmmss}
```

Example: `gh-issue-42-20260408041530`

- `issue_number`: the GitHub issue number
- `yyyymmddhhmmss`: the creation time (`date +%Y%m%d%H%M%S`)

Branch names use the same `gh-issue-{N}-{timestamp}`.

The Cycle Workflow creates its dedicated worktree under this name at Step 4 (branching from
`origin/{default_branch}`, never from the primary checkout's HEAD) and removes it itself when the
run ends, on success and failure alike. The orphan detection below is therefore the safety net for
runs that died before reaching their own removal step, not the primary cleanup path.

## Orphan Detection Rules (the 24h condition)

Only a worktree satisfying **all** of the following is a cleanup target.

1. The directory name matches the `gh-issue-{N}-{timestamp}` pattern
2. `timestamp` is **at least 24 hours** before the current time
3. The state of the corresponding issue `#N` is one of:
   - The issue is closed
   - The issue does **not** carry the `claude-running` label
4. The corresponding branch is merged (it appears in `git branch --merged main`), or the corresponding PR is closed/merged

> **Conservative cleanup**: all 4 conditions above are required, ANDed together. If even one is doubtful, do not delete.

This detection is called from `rollback_orphans()` step ① (`_check_worktree_orphans`). See [`polling-adapter.md §rollback_orphans Sub-Steps`](polling-adapter.md#rollback_orphans-sub-steps) for details.

## Deletion Procedure

```bash
# 1. Enumerate the deletion candidates
git worktree list --porcelain | parse → candidates

# 2. Re-check each candidate
for wt in candidates:
  N = extract_issue_number(wt.name)
  ts = extract_timestamp(wt.name)

  if age(ts) < 24h: skip
  state = gh issue view ${N} --json state,labels
  if "claude-running" in state.labels: skip   # the immediately-preceding re-check
  if not (issue closed or branch merged): skip

  # 3. Perform the deletion
  git worktree remove <path> --force
  git branch -D <branch>   # delete the branch too (on the premise that it is merged)
```

## When It Runs

- Executed in `rollback_orphans()` step ① of the **Polling Workflow** (cleanup at the head of every tick)
- Not executed on a manual `cycle` run (so it cannot affect other workers running alongside)

## Partial Claim Rollback

Because the atomic-claim 3 layers of defense in Cycle Workflow Step 2 (see [`polling-adapter.md §claim() 3 Layers of Defense`](polling-adapter.md#claim-3-layers-of-defense)) execute in sequence, side effects can remain when an intermediate stage fails. The case where acquiring the lockfile succeeded but setting the assignee / label failed is rolled back explicitly by the following procedure:

1. Run `gh issue edit ${N} --remove-label claude-running` best-effort (in case it had already been added)
2. Run `gh issue edit ${N} --remove-assignee @me` best-effort (in case you had become the assignee)
3. If the dual-write labels were partially added, remove them **in the order `-transient -permanent -claude-failed`** (keeping consistency with the precedence rule)
4. Releasing the `flock` happens automatically on process exit. Closing it explicitly with `exec 8>&-` is also acceptable
5. Even if the rollback itself fails, the process continues aborting (recovery comes from the next tick's idempotency)
6. Log `[claim-rollback] issue=#${N} reason=<…>` to stderr

This minimizes half-finished states from a partial claim, such as "the assignee is set but the lock has already been released".

## Logging

When cleanup runs, record the following on standard output:

```
[cleanup] removed worktree: gh-issue-42-20260407041530 (issue closed, branch merged)
[cleanup] removed worktree: gh-issue-99-20260406120000 (issue !running, age 36h)
```
