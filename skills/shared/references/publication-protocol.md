# Publication Protocol

Ordered procedure for advancing main after a satellite worktree completes.
Consumed by [cycle](../../cycle/SKILL.md) and [iterate](../../iterate/SKILL.md) standalone
worktree modes. Both follow the same protocol — no skill-specific overrides.

## Inputs

- `{satellite_branch}`: the branch to merge
- `{main_tree_root}`: path to the main worktree

Derived during the protocol: `{expected_main_sha}` / `{post_merge_sha}` (Step 1),
`{tmp_merge_root}` (temporary merge worktree, Step 1), `{evidence_dir}` (Step 2).

Throughout this protocol, `main` means the repository's default branch — substitute the
actual name (e.g. `master`) in every command.

## Step 1: Prospective merge

Create a prospective merge commit **without** advancing main. The procedure is fixed —
do not substitute alternative commands:

1. Save `{expected_main_sha}` = current main HEAD:
   `git -C {main_tree_root} rev-parse main`.
2. Create a temporary detached worktree at that SHA, at a fresh path `{tmp_merge_root}`
   outside `{main_tree_root}`:
   `git -C {main_tree_root} worktree add --detach {tmp_merge_root} {expected_main_sha}`.
3. Create the merge commit in the temporary worktree:
   `git -C {tmp_merge_root} merge --no-ff {satellite_branch}`.
   `--no-ff` guarantees a merge commit even when main could fast-forward, so the commit
   shape does not depend on history. A merge conflict is a terminal publish failure:
   abort the merge, leave main and the satellite worktree untouched, and stop.
4. Resolve the full 40-hex `{post_merge_sha}`:
   `git -C {tmp_merge_root} rev-parse HEAD`.

The temporary worktree now holds the prospective merge tree; Step 2 runs verification
inside it. main and the main worktree remain untouched throughout Steps 1-2.

Pre-merge or satellite evidence does not transfer — all later verification and evidence
must name the exact `{post_merge_sha}`.

## Step 2: Re-earn evidence

Re-earn both states required by the
[quality-gate contract](quality-gate-contract.md) for `{post_merge_sha}`
**before** advancing main:

1. **`machine_verified`**: run the repository's canonical verification entry point inside
   `{tmp_merge_root}` (the prospective merge tree). Only a complete pass may produce
   `machine_verified.json`.
2. **`semantic_reviewed`**: run a fresh history-free semantic review of the merged
   target that executes the [quality-gate contract](quality-gate-contract.md)'s review
   machinery — fire the §4 obligations for the kinds of change in the merge, record
   each in an evidence ledger entry per §4.3 (target / verification predicate /
   coverage state / grounds / findings), disposition every finding according to its
   verification value, and reach the convergence conditions of §5. Only a converged
   review may produce `semantic_reviewed.json`; its grounds must name the review run
   and where the review's ledger is stored. The review procedure and ledger schema are
   the contract's, not this protocol's — this protocol adds only the binding: the
   review subject and every ledger entry target the exact `{post_merge_sha}` tree.

Write both records to `{evidence_dir}` = a run-scoped staging directory keyed by the
prospective merge commit,
`{main_tree_root}/.agents/artifacts/reviews/evidence-staging/{post_merge_sha}/`, using
the [evidence format](evidence-format.md): exact `{post_merge_sha}`,
`quality-gate-contract 1.0.0`, `profile: null`, and non-empty grounds naming the run or
review that produced the state.

Never write prospective evidence into the default evidence directory
(`{main_tree_root}/.agents/artifacts/reviews/evidence/`): that singleton describes the
**currently published** main, and overwriting it before publication succeeds would
destroy or mix the old main's valid evidence on any failure (review failure, CAS
conflict, mid-run stop). Promotion into the singleton is a completion step of Exit 0.
Do not write into `{tmp_merge_root}`'s own store either: the artifact store is
per-worktree, so evidence written there resolves to a different directory than the one
the Step 3 checker reads. Producer and checker must name the same `{evidence_dir}`
explicitly.

A Phase 4 review verdict is review input, not reusable evidence.

## Step 3: Checker judgment

Run the canonical checker with every binding input explicit:

```
python3 skills/shared/scripts/evidence_check.py \
  --target-sha {post_merge_sha} \
  --contract skills/shared/references/quality-gate-contract.md \
  --repo-root {main_tree_root} \
  --evidence-dir {evidence_dir}
```

`--evidence-dir` is not optional here: it pins the checker to the exact directory Step 2
wrote, instead of relying on the default derivation from `--repo-root`.

### Exit 0 — advance main

Execute the advance through the canonical primitive — never hand-roll these git
commands. cycle, iterate, and the regression tests
(`test_publication_protocol_git.py`) all run this same implementation, so the prose
and the verified behavior cannot drift apart:

```
python3 skills/shared/scripts/publication_advance.py advance \
  --repo-root {main_tree_root} --branch main \
  --post-merge-sha {post_merge_sha} --expected-main-sha {expected_main_sha} \
  --evidence-staging {evidence_dir}
```

The numbered steps below are the primitive's specification — what it proves, in which
order — not a command list to reproduce by hand:

1. **Precondition — exclusive access**: the caller must still hold the repository
   workspace lock it acquired at the start of its run (cycle and iterate claim it in
   their Phase 0 and release it only when the run ends). The clean-tree check, the ref
   update, and the checkout synchronization below all run under that exclusion — that
   is what makes check-then-reset safe against concurrent edits. If no lock is held or
   the lock infrastructure is unavailable, the destructive reset in step 4 is
   forbidden, and the branch splits on where `main` is checked out:
   - `main` is checked out in `{main_tree_root}` (or any worktree) → stop **here,
     before step 3's compare-and-swap**, as a terminal publish failure (treat as
     exit 1). Advancing the ref would strand that checkout's index and files at
     `{expected_main_sha}`, and the reset that would synchronize them is exactly what
     is forbidden without the lock.
   - `main` is not checked out anywhere → the ref-level compare-and-swap in step 3 is
     atomic on its own and step 4 is a no-op, so the advance may proceed; still treat
     a dirty tree or any tree change appearing after the check as a terminal publish
     failure.
2. **Precondition — locate the main checkout, require it clean**: list every worktree
   (`git -C {main_tree_root} worktree list --porcelain`) and find where `main` is
   checked out. If `main` is checked out in any worktree other than
   `{main_tree_root}`, stop here — before the compare-and-swap — as a terminal publish
   failure: this protocol defines cleanliness checking and synchronization only for
   `{main_tree_root}`, and advancing the ref would strand that other checkout. If
   `{main_tree_root}` has `main` checked out, require a clean tree
   (`git -C {main_tree_root} status --porcelain` prints nothing). A dirty main tree is
   a terminal publish failure (treat as exit 1) — advancing the ref underneath local
   modifications would entangle them with the merge.
3. **Advance main with compare-and-swap**:
   `git -C {main_tree_root} update-ref refs/heads/main {post_merge_sha} {expected_main_sha}`.
4. **Synchronize the checkout**: if `main` is checked out in `{main_tree_root}`, run
   `git -C {main_tree_root} reset --hard refs/heads/main`. `update-ref` moves only the
   ref — without this reset, the index and working files still reflect
   `{expected_main_sha}` and the main tree reports phantom modifications. The reset is
   safe because the tree was proven clean and the workspace lock excludes concurrent
   writers (step 1). If `main` is not checked out in any worktree, the ref update alone
   completes the advance.
5. **Promote the evidence**: copy — never move — both records from `{evidence_dir}`
   into the default evidence directory
   `{main_tree_root}/.agents/artifacts/reviews/evidence/`, overwriting the superseded
   records of the previous main. Then verify the promoted set by re-running the Step 3
   checker against the default directory (`--evidence-dir` pointing at it, same
   `{post_merge_sha}`); only after that verification exits 0, remove the staging
   directory. Copy-then-verify-then-delete makes promotion idempotent: a crash at any
   point leaves the complete staging set in place, and re-running the promotion from
   staging converges — a partially promoted singleton is always repairable. While the
   copy is in flight the singleton may transiently hold records naming different
   SHAs; any reader fails closed — the checker refuses a mixed set — and the staging
   set remains in place until verification passes.
6. Remove the temporary merge worktree (`git worktree remove {tmp_merge_root}`) only
   after the advance succeeds.

Step 3 is the **commit point** of publication. Every failure before it leaves main
fully untouched — ref, checkout, and the published evidence singleton all still
describe the old main. Once the compare-and-swap succeeds, the advance is committed
and is never rolled back: steps 4-6 are completion steps, each idempotent, and on
failure, interruption, or crash they are re-run until they succeed (re-run the reset,
re-attempt the promotion) rather than being treated as publish failures.

**Recovery after post-commit interruption.** The staging directory doubles as the
durable marker of an unfinished publication: it is deleted only as the final act of
promotion, so no in-process state is needed to detect an interruption. On (re)entry
into this protocol, if an `evidence-staging/{sha}/` directory exists whose `{sha}`
equals the current main HEAD, the commit point already passed and the completion
steps did not finish. First re-acquire the workspace lock — the crashed run's lock is
gone, and repairing without exclusion recreates the concurrent-writer race. Then run
the canonical primitive:
`python3 skills/shared/scripts/publication_advance.py recover --repo-root {main_tree_root} --branch main`.

The primitive repairs only what it can prove is the pure phantom state, because the
durable marker alone cannot distinguish a stale checkout from a human's post-crash
edits — and repair must never destroy the latter. It resets and promotes only when
all of these hold; otherwise it stops without mutating anything and requires manual
recovery:
- the staged evidence still passes the Step 3 checker for `{sha}`;
- index and worktree both still match the merge's first parent (`{sha}^1`, the
  pre-CAS tree) — or already match `{sha}` (the reset had completed before the crash);
- no path the merge adds exists as an untracked file in the worktree.

The reset runs only when `main` is itself checked out in `{main_tree_root}` —
`git reset --hard` moves whichever branch is currently checked out, so with any other
branch checked out there the primitive skips the sync entirely and only promotes.
The pre-CAS clean-tree precondition does not apply during this repair — the phantom
modifications of a stale checkout are the symptom being repaired. A staging directory
whose `{sha}` differs from the current main HEAD names a prospective merge that never
published (or one long superseded) and may be discarded under the CAS failure rule.

If CAS fails (main moved during verification):
1. Discard the stale prospective merge (remove `{tmp_merge_root}` and the stale
   `{evidence_dir}` staging directory — both name a commit that will never publish).
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

Every failure path before the commit point preserves the satellite branch, its
worktree, and its staging, and leaves main — ref, checkout, and published evidence
singleton — untouched. Discarding satellite work products requires explicit human
authorization. The protocol's own derived intermediates — `{tmp_merge_root}` and a
stale `evidence-staging/` directory — are mechanically reproducible from the
satellite branch and the current main, so the CAS retry rule may discard them
automatically; that is not a discard of work products. After the commit point there
are no publish failures, only incomplete completion steps, which are repaired forward
(re-run until they succeed) and never rolled back.

## Cleanup gating

Cleanup only when:
1. Publication succeeded, **and**
2. `cleanup_allowed` is proven, **and**
3. The capability is non-live (consumed or revoked).
