# Merge Strategy - Post-Execution Branch Merging

Strategy for merging completed cycle branches back into the main branch.

## Merge Flow

```
For each successful cycle in completion order:
  1. Checkout main branch
  2. Pull latest (fast-forward only)
  3. Merge cycle branch with --no-ff
  4. Run tests (if test runner exists)
  5. If tests pass → continue to next
  6. If tests fail → revert merge, mark cycle as merge-failed
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

After merging (or deciding not to merge), clean up worktrees:

```bash
# git worktree remove で明示的に破棄する
# その後、stale な worktree が残っていないか検証する
git worktree list
git worktree prune
```

All worktrees must be cleaned up regardless of cycle success or failure.

## Safety Rules

- **Never force push** — All merges are standard merges
- **Never rebase** — Only merge commits
- **Pull before merge** — Always sync with remote before merging
- **Test after each merge** — Not just after all merges
- **Preserve failed branches** — Do not delete branches of failed cycles
