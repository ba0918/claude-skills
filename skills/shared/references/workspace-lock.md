# Workspace Lock Contract

The core implementation loop (`cycle` → `plan-implement` → `iterate`) writes directly into a
shared checkout and never checks whether another session is already working there. Two
sessions in one tree overwrite each other's edits, run tests against the other side's
half-finished state, and cut commits spanning both. Each of those only becomes visible much
later, and the cause is expensive to recover.

This contract is that missing occupancy check. It is **always on and not configurable**. The
cost is effectively zero, and a switch would leave the accident in place precisely in the
environments where the switch was thrown.

## The resource

**The resource is the working tree, and the lock is `.agents/runtime/workspace.claim`.**

The location settles the granularity by itself. The runtime area is per working tree (see
[artifact-store.md](artifact-store.md) §Runtime area), so one working tree is one lock — no
hash, no key design.

**Identity is the working-tree path, not the branch.** The same checkout collides across
branches; separate worktrees never collide even on the same branch. A branch is recorded in
the claim for display only.

**Writing the claim is not "writing to the tree".** The rule elsewhere in this contract is
"take the lock before writing a single byte of project state", and the claim file itself is
the one exception: it lives in the runtime area, which is machine-local, Git-ignored, and
never project state (artifact-store.md §Runtime area). Stating it here so a reader does not
have to derive it — the rule would otherwise read as forbidding the very act it requires.

## What is reused, not redefined

The claim semantics already exist in [polling-pattern.md](polling-pattern.md) §6.3–6.4 and
are **referenced here, not restated**:

- atomic claim, with failure carrying a reason
- `pid` + `started_at` recorded in the claim
- claim file created with permission mode `0600`, best-effort where the filesystem does not
  honor it (warn and continue, never stop)
- pid liveness decides orphan recovery
- a trap releases on shutdown, and the case where the trap never fires (SIGKILL / crash) is
  recovered by the stale sweep — the two-stage arrangement

New here is only **what is locked** and **who locks it**.

## The claim record

| Field | Meaning |
|---|---|
| `pid` | The claiming process. Liveness of this pid is the only stale test |
| `started_at` | UTC timestamp, shown in the conflict display |
| `skill` | Which skill took the tree, shown in the conflict display |
| `branch` | Recorded for display. **Never part of identity** |
| `token` | Opaque value proving the right to release |

## Operations

Repository scripts use [`skills/shared/scripts/workspace_lock.py`](../scripts/workspace_lock.py).
Skill prose should say "take the working tree per the workspace lock contract" and link here
rather than reimplementing resolution or validation.

```bash
python3 skills/shared/scripts/workspace_lock.py claim   --repo . --skill cycle
python3 skills/shared/scripts/workspace_lock.py release --repo . --token {token}
python3 skills/shared/scripts/workspace_lock.py status  --repo .
```

`claim` prints the outcome as JSON and exits non-zero **only** for `LOCK_HELD` — that is the
branch a caller needs. `UNAVAILABLE` exits 0, because the contract is fail-open.

| Operation | Result |
|---|---|
| `claim(repo, skill)` | `ACQUIRED` / `STALE_RECLAIMED` / `LOCK_HELD` / `UNAVAILABLE` |
| `release(repo, token)` | True only for the holder of `token` |
| `status(repo)` | The holder plus a liveness flag, or None |

### Stale decision

- The existing claim's pid is **not alive** → reclaim it, and surface `STALE_RECLAIMED` in
  the display. A crashed session must be seen to have been cleaned up, not silently ignored
- The existing claim's pid **is alive** → stop with `LOCK_HELD`

**A live claim must never be taken over.** There is no force path, in the module or in the
display. A pid whose liveness cannot be determined (for example another user's process,
where signalling raises a permission error) counts as **alive** — deciding otherwise would
let one user steal another's tree.

## Conflict behavior

Stop **before writing a single byte of project state**. Show the holder's `skill` / `pid` /
`branch` / `started_at` and the elapsed time, and offer exactly two options:

1. wait for the other session to finish
2. after confirming the other session is dead, delete the claim file

No automatic takeover is offered.

## When the lock cannot be taken (fail-open)

If `.agents/runtime/` cannot be created, **or the claim file inside it cannot be written**
(outside Git control, read-only mount, quota exhausted, a differently-owned runtime area,
and so on), emit a single warning and **continue**.

Both halves matter. A runtime area that already exists but rejects writes must reach
`UNAVAILABLE` too — surfacing it as an error would exit non-zero, and the contract reserves
that for `LOCK_HELD`, so callers would stop on a holder that does not exist.

This is deliberate. The lock is an addition to existing behavior; stopping where it cannot be
held would break setups that used to work. Such an environment keeps its previous safety —
unimproved, but not worsened.

## Who claims

| Skill | Claims | Note |
|---|---|---|
| `cycle` | yes | At the very start of Phase 0, before plan validation |
| `plan-implement` | only standalone | Under `cycle` it receives a token and does not claim |
| `iterate` | yes | |
| `parallel-cycle` | yes (main tree) | Each worktree delegate claims its own tree separately |

- **On delegation, pass the token in the delegate's prompt.** A delegate holding a token
  neither claims nor releases. `cycle` already passes `{run_id}` into the delegation prompt,
  so the token rides the same path
- `commit`, `plan`, and every other sub-skill **do not claim**. That is what structurally
  prevents a nested self-deadlock
- A `parallel-cycle` worktree delegate reads its own tree's `.agents/runtime/`, so it is a
  different resource from the main tree. No token is passed to it
