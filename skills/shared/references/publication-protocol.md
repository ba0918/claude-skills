# Publication Protocol

Advancing main after a satellite worktree completes. Consumed by
[cycle](../../cycle/SKILL.md) and [iterate](../../iterate/SKILL.md) standalone worktree
modes — same protocol, no skill-specific overrides. `main` throughout means the
repository's default branch (substitute the actual name, e.g. `master`).

Inputs: `{satellite_branch}`, `{main_tree_root}`.

The git state transitions — prospective merge, compare-and-swap advance, checkout
synchronization, crash recovery — are implemented once in
`skills/shared/scripts/publication_advance.py` and verified by fault-injection tests
(`test_publication_protocol_git.py`). Run the primitive; never hand-roll its git
commands. This file carries only what the executor must judge: the order, and the
safety boundaries.

The staging directory is a **durable marker** of an unfinished publication, not a
vessel for verification evidence. It records that "this merge was intended"
(a merge-intent record with the post-merge SHA and provenance). Verification quality is
the calling skill's review's job; the primitive's own checks are structural only:
compare-and-swap, lock proof, merge shape, and tree safety. This separation came from
[quality-gate-contract.md](quality-gate-contract.md) #308: the ledger layer was
dismantled, the structural safety of the advance survived.

## Sequence

Hold the workspace lock across the whole sequence (cycle and iterate claim it in their
Phase 0 and release it when the run ends) and pass its token to the primitive as
`--lock-token`: the destructive paths verify the token against the live claim in code
and refuse to run without a match — prose alone proves nothing.

1. **Prospective merge** — main untouched:
   `python3 skills/shared/scripts/publication_advance.py merge --repo-root {main_tree_root} --branch main --satellite-branch {satellite_branch}`
   The JSON output gives `expected_main_sha`, `post_merge_sha`, `tmp_merge_root`
   (a temporary worktree holding the merged tree), and `evidence_staging` (the
   run-scoped staging directory that becomes the durable marker). A merge conflict is a
   terminal publish failure. The primitive writes a merge-intent record into the staging
   directory; that readable record — not the bare directory — is what `advance` /
   `recover` recognize.
   The staging directory is the only publication record and it is run-scoped.

2. **Advance** — structural checks and every destructive step in one implementation:
   `python3 skills/shared/scripts/publication_advance.py advance --repo-root {main_tree_root} --branch main --post-merge-sha {post_merge_sha} --expected-main-sha {expected_main_sha} --evidence-staging {evidence_staging} --lock-token {workspace_lock_token}`
   The compare-and-swap inside it is the **commit point** of publication. Exit codes:
   - `0` — main advanced, checkout synchronized, durable marker cleared.
     Publish only after this. Then remove `{tmp_merge_root}`
     (`git worktree remove`).
   - `3` — terminal publish failure: a precondition (lock proof, post-merge SHA
     provenance, clean tree) or the durable marker could not be proven; main
     untouched.
   - `4` — CAS conflict: main moved during verification. Discard `{tmp_merge_root}`
     and the stale staging — the protocol's own reproducible intermediates, not
     satellite work products — and retry the sequence from step 1 exactly once. A
     second CAS failure is a terminal publish failure.
   - `2` — broken invocation before the commit point (arguments or environment);
     main untouched, staging preserved.
   - `7` — failure **after** the commit point: main is already advanced but
     completion (checkout sync or marker removal) did not finish. Not a publish
     failure — never roll back; staging remains as the durable marker. Repair the
     cause, then run `recover`.

## Recovery

The staging directory is the durable marker of an unfinished publication. On entry, if
`evidence-staging/{sha}/` holds a readable merge-intent record with `{sha}` equal to the
current main HEAD, the commit point already passed and completion did not finish. Re-acquire the workspace
lock, then run:
`python3 skills/shared/scripts/publication_advance.py recover --repo-root {main_tree_root} --branch main --lock-token {workspace_lock_token}`

It repairs only what it can prove is untouched post-crash state, and otherwise stops
without mutating anything (exit `6` → manual recovery): a human's post-crash edits
must never be destroyed. Like `advance`, it exits `7` when completion fails again
mid-repair — staging stays preserved; repair the cause and rerun. When no durable
marker exists for the current main HEAD, `recover` reports exit `5` (no unfinished
publication — a no-op, not an error). A staging directory
whose `{sha}` differs from the current main HEAD never published and may be discarded.

## Safety boundaries

- Terminal publish failure (primitive exit `3`/`2`, or a second CAS conflict): do not
  advance main, do not publish, do not compose singleton artifacts, do not close the
  issue, do not clean up.
- Every failure before the commit point preserves the satellite branch and its
  worktree; discarding satellite work products requires explicit human authorization.
  Staging is a reproducible protocol intermediate: the CAS-conflict retry discards it,
  every other failure keeps it for diagnosis. After the commit point (exit `7`) there
  are no publish failures — only completion steps, repaired forward by `recover`,
  never rolled back.
- Cleanup only when: publication succeeded, `cleanup_allowed` is proven, and the
  capability is non-live (consumed or revoked).
