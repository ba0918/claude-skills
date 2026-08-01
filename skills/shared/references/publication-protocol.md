# Publication Protocol

Ordered procedure for advancing main after a satellite worktree completes.
Consumed by [cycle](../../cycle/SKILL.md) and [iterate](../../iterate/SKILL.md) standalone
worktree modes. Both follow the same protocol — no skill-specific overrides.

## Inputs

- `{satellite_branch}`: the branch to merge
- `{main_tree_root}`: path to the main worktree

## Step 1: Prospective merge

Create a prospective merge commit **without** advancing main.

1. Save `{expected_main_sha}` = current main HEAD (`git rev-parse main`).
2. Merge the satellite branch into a temporary integration ref
   (e.g. `refs/cycle/integration`) or a detached HEAD:
   `git merge-base main {satellite_branch}` to confirm fast-forward or real merge,
   then `git merge --no-ff --no-commit` on a temporary checkout of main →
   `git commit-tree` or equivalent to produce the merge commit without advancing main.
3. Resolve the full 40-hex `{post_merge_sha}` from that commit.

Pre-merge or satellite evidence does not transfer — all later verification and evidence
must name the exact `{post_merge_sha}`.

## Step 2: Re-earn evidence

Re-earn both states required by the
[quality-gate contract](quality-gate-contract.md) for `{post_merge_sha}`
**before** advancing main:

1. **`machine_verified`**: run the repository's canonical verification entry point against
   the prospective merge tree. Only a complete pass may produce `machine_verified.json`.
2. **`semantic_reviewed`**: run a fresh history-free semantic review of the merged target,
   disposition every finding, and require convergence before producing
   `semantic_reviewed.json`.

Write both records in the default artifact-store evidence directory using the
[evidence format](evidence-format.md): exact `{post_merge_sha}`,
`quality-gate-contract 1.0.0`, `profile: null`, and non-empty grounds naming the run or
review that produced the state.

A Phase 4 review verdict is review input, not reusable evidence.

## Step 3: Checker judgment

Run the canonical checker with every binding input explicit:

```
python3 skills/shared/scripts/evidence_check.py \
  --target-sha {post_merge_sha} \
  --contract skills/shared/references/quality-gate-contract.md \
  --repo-root {main_tree_root}
```

### Exit 0 — advance main

Advance main with compare-and-swap:
`git update-ref refs/heads/main {post_merge_sha} {expected_main_sha}`.

If CAS fails (main moved during verification):
1. Discard the stale prospective merge.
2. Re-create the prospective merge from the new main (repeat Steps 1-2).
3. Re-run the checker.
4. Retry at most **once**. A second CAS failure is a terminal publish failure (treat as
   exit 1).

Do not force the update. Publish only after main is advanced.

### Exit 1 (missing, stale, or invalid evidence) / Exit 2 (checker could not run)

Terminal publish failure:
- Do not advance main
- Do not publish
- Do not compose singleton artifacts
- Do not close the issue
- Do not clean up

Main remains untouched.

## Failure path preservation

Every failure path preserves staging and the worktree. Discard requires explicit human
authorization.

## Cleanup gating

Cleanup only when:
1. Publication succeeded, **and**
2. `cleanup_allowed` is proven, **and**
3. The capability is non-live (consumed or revoked).
