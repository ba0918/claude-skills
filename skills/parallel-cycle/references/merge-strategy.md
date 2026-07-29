# Merge Strategy - Post-Execution Branch Merging

Strategy for merging completed cycle branches back into the main branch.

## Merge Flow

```
For each successful cycle in completion order:
  1. Collect before merge into validated main-runtime staging
  2. Checkout main branch and pull latest (fast-forward only)
  3. Merge cycle branch with --no-ff
  4. Run tests (if test runner exists)
  5. If tests pass → publish staged artifacts, then enter cleanup_allowed
  6. If tests fail → revert merge, do not publish, preserve the worktree
```

## Merge Commands

```bash
# Ensure we are on the base branch
git checkout main

# Pull latest
git pull --ff-only

# Merge a successful cycle branch
git merge --no-ff {branch_name} -m "merge: parallel-cycle {plan_title}"

# Run tests (project-dependent)
# If test runner exists: npm test / pytest / cargo test / etc.
# If no test runner: skip test step

# On test failure, revert the merge
git revert -m 1 HEAD --no-edit
```

## Merge Order

1. Merge cycles in group order (Group 1 first, then Group 2, etc.)
2. Within a group, merge in alphabetical order by plan identifier
3. This ensures deterministic merge order for reproducibility

## Partial Success Handling

When some cycles succeed and others fail:

```
Cycle A: ✅ Success → merge
Cycle B: ❌ Failed  → skip merge, branch preserved
Cycle C: ✅ Success → merge
```

- Successful cycles are merged regardless of other failures
- Failed cycle branches are preserved for manual inspection
- The summary report lists which cycles were merged and which were not

## Dependent Cycle Failure Propagation

When a cycle in an earlier group fails, all dependent cycles in later groups are skipped:

```
Group 1: [A] → ❌ Failed
Group 2: [B (depends on A), D (independent)] → B skipped, D executed
Group 3: [C (depends on B)] → C skipped (transitively depends on A)
```

Skipped cycles are reported as "skipped due to dependency failure" — distinct from execution failure.

## Worktree Cleanup

Every recovery instruction in this reference uses the shared exact six-line formatter:

```text
reason_code={reason_code}
run_id={satellite_run_id}
main_tree_path={main_tree_path}
worktree_path={worktree_path_or_unavailable}
reason={reason}
recovery_command=/claude-skills:artifacts recover --run-id {satellite_run_id}
```

After merging (or deciding not to merge), clean up worktrees:

```bash
# Worktree cleanup is handled automatically
# But verify no stale worktrees remain
git worktree list
git worktree prune
```

Publish only after the merge and post-merge verification pass. Remove the worktree of a cycle
only after publication has passed destination CAS, the capability is non-live, and lifecycle is
`cleanup_allowed` — that is Step 3.4, after the decisions above, not during Phase 2. If collect or
publish fails, or a conflict occurs, preserve the worktree and staging and emit the formatter with
the applicable closed reason code. Failed, merge-reverted, and skipped cycles also keep their
worktrees for diagnosis, and those are removed only when a human says so (§Preserved Worktrees in
[SKILL.md](../SKILL.md)).

`git worktree prune` only discards bookkeeping for worktrees whose directory is already gone, so
it never removes a preserved one and is not a substitute for the explicit removal above.

## Safety Rules

- **Never force push** — All merges are standard merges
- **Never rebase** — Only merge commits
- **Pull before merge** — Always sync with remote before merging
- **Test after each merge** — Not just after all merges
- **Preserve failed branches and their worktrees** — Do not delete either. The branch holds only
  what was committed; the worktree holds the rest
