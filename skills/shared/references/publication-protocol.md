# Publication Protocol

Advancing main after a satellite worktree completes. Consumed by
[cycle](../../cycle/SKILL.md) and [iterate](../../iterate/SKILL.md) standalone worktree
modes — same protocol, no skill-specific overrides. `main` throughout means the
repository's default branch (substitute the actual name, e.g. `master`).

Inputs: `{satellite_branch}`, `{main_tree_root}`.

The git state transitions — prospective merge, compare-and-swap advance, checkout
synchronization, evidence promotion, crash recovery — are implemented once in
`skills/shared/scripts/publication_advance.py` and verified by fault-injection tests
(`test_publication_protocol_git.py`). Run the primitive; never hand-roll its git
commands. This file carries only what the executor must judge: the order, the evidence
to earn, and the safety boundaries.

## Sequence

Hold the workspace lock across the whole sequence (cycle and iterate claim it in their
Phase 0 and release it when the run ends) and pass its token to the primitive as
`--lock-token`: the destructive paths verify the token against the live claim in code
and refuse to run without a match — prose alone proves nothing.

1. **Prospective merge** — main untouched:
   `python3 skills/shared/scripts/publication_advance.py merge --repo-root {main_tree_root} --branch main --satellite-branch {satellite_branch}`
   The JSON output gives `{expected_main_sha}`, `{post_merge_sha}`, `{tmp_merge_root}`
   (a temporary worktree holding the merged tree), and `{evidence_dir}` (a run-scoped
   staging directory). A merge conflict is a terminal publish failure.

2. **Re-earn evidence** for the exact `{post_merge_sha}` — satellite or pre-merge
   evidence never transfers, and a review verdict from the calling skill is review
   input, not reusable evidence:
   - `machine_verified`: run the repository's canonical verification entry point
     inside `{tmp_merge_root}`; only a complete pass may produce the record.
   - `semantic_reviewed`: run a fresh history-free semantic review executing the
     [quality-gate contract](quality-gate-contract.md)'s §4 obligations, §4.3 evidence
     ledger, and §5 convergence conditions.
   Write both records into `{evidence_dir}` per the [evidence format](evidence-format.md),
   bound to `{post_merge_sha}`. Never write into the default evidence directory — that
   singleton describes the currently published main until promotion succeeds.

3. **Advance** — checker judgment and every destructive step in one implementation:
   `python3 skills/shared/scripts/publication_advance.py advance --repo-root {main_tree_root} --branch main --post-merge-sha {post_merge_sha} --expected-main-sha {expected_main_sha} --evidence-staging {evidence_dir} --lock-token {workspace_lock_token}`
   The compare-and-swap inside it is the **commit point** of publication. Exit codes:
   - `0` — main advanced, checkout synchronized, evidence promoted into the singleton.
     Publish only after this. Then remove `{tmp_merge_root}`
     (`git worktree remove`).
   - `3` — terminal publish failure: a precondition or the staged evidence could not
     be proven; main untouched.
   - `4` — CAS conflict: main moved during verification. Discard `{tmp_merge_root}`
     and the stale staging — the protocol's own reproducible intermediates, not
     satellite work products — and retry the sequence from step 1 exactly once. A
     second CAS failure is a terminal publish failure.
   - `2` — broken run; staging is preserved for repair.

## Recovery

The staging directory is the durable marker of an unfinished publication. On entry, if
`evidence-staging/{sha}/` exists with `{sha}` equal to the current main HEAD, the
commit point already passed and completion did not finish. Re-acquire the workspace
lock, then run:
`python3 skills/shared/scripts/publication_advance.py recover --repo-root {main_tree_root} --branch main --lock-token {workspace_lock_token}`

It repairs only what it can prove is untouched post-crash state, and otherwise stops
without mutating anything (exit `6` → manual recovery): a human's post-crash edits
must never be destroyed. A staging directory whose `{sha}` differs from the current
main HEAD never published and may be discarded.

## Safety boundaries

- Terminal publish failure (primitive exit `3`/`2`, or a second CAS conflict): do not
  advance main, do not publish, do not compose singleton artifacts, do not close the
  issue, do not clean up.
- Every failure before the commit point preserves the satellite branch, its worktree,
  and staging; discarding satellite work products requires explicit human
  authorization. After the commit point there are no publish failures — only
  completion steps, repaired forward by `recover`, never rolled back.
- Cleanup only when: publication succeeded, `cleanup_allowed` is proven, and the
  capability is non-live (consumed or revoked).
