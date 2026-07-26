# gh CLI Semantic Wrappers

The list of semantic wrappers around gh CLI invocations. Every place this skill calls `gh` directly must correspond to an entry in these tables.

## Auth / Repo

| Purpose | Command |
|------|---------|
| Check that gh is installed | `gh --version` |
| Check authentication | `gh auth status` |
| Repository information | `gh repo view --json nameWithOwner,defaultBranchRef` |
| Rate limit | `gh api rate_limit --jq '.rate.remaining'` |

## Issue

| Purpose | Command |
|------|---------|
| List issues (claude-auto) | `gh issue list --label claude-auto --state open --json number,title,body,labels,assignees,author,authorAssociation --limit 100` |
| List labels | `gh label list --json name,description,color` |
| Issue detail | `gh issue view <N> --json number,title,body,labels,assignees,author,authorAssociation` |
| Create an issue | `gh issue create --title <T> --body <B> --label <L>` |
| Add an assignee | `gh issue edit <N> --add-assignee @me` |
| Add a label | `gh issue edit <N> --add-label <L>` |
| Remove a label | `gh issue edit <N> --remove-label <L>` |
| Post a comment | `gh issue comment <N> --body <B>` |
| Close an issue | `gh issue close <N>` |

## Pull Request

| Purpose | Command |
|------|---------|
| Create a draft PR | `gh pr create --draft --title <T> --body <B>` |
| Get the PR diff | `gh pr diff <PR>` |
| PR checks status | `gh pr checks <PR>` |
| Mark ready for review | `gh pr ready <PR>` |
| Squash merge | `gh pr merge <PR> --squash --delete-branch` |

## Cautions

- **Do not use `--search`**: the GitHub Search API is limited to 30 req/min, so polling uses a `--label` filter plus client-side exclusion
- **Do not use `gh pr merge --auto`**: to guarantee ordering, run `gh pr ready` and then `gh pr merge` explicitly, in that order
- **`gh pr create --draft` is mandatory**: do not undraft until the auto-merge gate has been passed
- **Make use of `--jq` on JSON output**: avoid shell parsing
