# Isolation Verification Procedure

How to confirm the worktree-isolation contract of the cycle workflow holds (a manual
check procedure — not executed on the cycle path).

In the primary checkout, switch to any non-default branch that is ahead of the default
branch by unrelated commits, then run `cycle N` and confirm all three of:

1. `git -C <worktree> log origin/${default_branch}..HEAD --oneline` lists only commits
   made by this cycle — none of the unrelated commits appear
2. the resulting PR diff (`get_pr_diff(<PR>)`) contains no changes outside the plan's scope
3. after the run, the primary checkout still sits on the same branch and HEAD as before it
