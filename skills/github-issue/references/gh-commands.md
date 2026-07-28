# GitHub Transport Operations

The GitHub state machine depends on the 18 semantic operations below, not on a particular
command-line tool. Every GitHub read or write in this skill must correspond to one row in these
tables and be invoked through the selected transport.

## Transport resolution

`github_transport` has three values:

| Value | Resolution |
|---|---|
| `auto` | Select `gh` when its executable is available; only when it is absent, select a connected GitHub integration that provides all required operations |
| `gh` | Require the `gh` implementation and fail closed when its pre-check fails |
| `integration` | Require a connected GitHub integration and fail closed when its capability pre-check fails |

Resolution happens once during Common Pre-checks and the selected transport is immutable for the
workflow invocation. Do not switch transports midway after a write: retrying a multi-step state
transition through another backend would make success ambiguous.

`auto` preserves compatibility: any environment where `gh` is installed still selects `gh` and
runs its existing authentication and repository checks. Authentication or authorization failure
does not trigger a backend switch. Only the previously terminal `gh`-absent case may fall through
to the integration.

The integration pre-check must establish all of the following without changing GitHub state:

1. a connected GitHub integration is available;
2. it can identify the authenticated actor and current repository;
3. all 18 operations below are supported.

An unavailable explicit transport, or `auto` with neither complete transport available, produces
`tool_missing` and fails closed. Authentication or authorization rejection from an available
transport remains `security`; it is not evidence that the transport is missing.

## Auth / Repo

| Operation | Purpose | `gh` implementation | Connected-integration capability |
|---|---|---|---|
| `check_transport` | Backend availability | `gh --version` | Inspect connection and advertised capabilities |
| `check_authentication` | Authenticated actor | `gh auth status` | Identify the authenticated actor |
| `repository_info` | Repository identity and default branch | `gh repo view --json nameWithOwner,defaultBranchRef` | Read repository metadata and default branch |
| `rate_limit` | Remaining API budget | `gh api rate_limit --jq '.rate.remaining'` | Read the integration's GitHub API rate-limit status |

## Issue

| Operation | Purpose | `gh` implementation | Connected-integration capability |
|---|---|---|---|
| `list_issues(filters, fields, limit)` | List issues for polling and recovery | `gh issue list` with caller-supplied `--label`, `--state`, `--json`, and `--limit` arguments | List issues with equivalent caller-supplied filters, fields, and limit |
| `list_labels` | List repository labels | `gh label list --json name,description,color` | List labels with name, description, and color |
| `get_issue(N, fields)` | Read issue detail | `gh issue view <N> --json <fields>` | Get the caller-supplied issue fields |
| `create_issue` | Create an issue | `gh issue create --title <T> --body <B> --label <L>` | Create an issue with title, body, and labels |
| `add_issue_actor` | Add current actor | `gh issue edit <N> --add-assignee @me` | Add the authenticated actor as assignee |
| `remove_issue_actor` | Remove current actor | `gh issue edit <N> --remove-assignee @me` | Remove the authenticated actor as assignee |
| `edit_issue_labels(add, remove)` | Atomically add and remove labels | One `gh issue edit <N>` carrying every requested `--add-label` and `--remove-label` | Apply all requested label additions and removals in one mutation |
| `comment_issue` | Post a comment | `gh issue comment <N> --body <B>` | Add an issue comment |
| `close_issue` | Close an issue | `gh issue close <N>` | Close the issue |

## Pull Request

| Operation | Purpose | `gh` implementation | Connected-integration capability |
|---|---|---|---|
| `create_draft_pr` | Create a draft PR | `gh pr create --draft --title <T> --body <B>` | Create a pull request with draft state set |
| `get_pr_diff` | Get the PR diff | `gh pr diff <PR>` | Read the complete unified PR diff |
| `get_pr_checks` | Read checks status | `gh pr checks <PR>` | Read all required check conclusions |
| `mark_pr_ready` | Mark ready for review | `gh pr ready <PR>` | Convert the draft PR to ready |
| `merge_pr` | Merge and delete branch | `gh pr merge <PR> --squash --delete-branch` | Squash-merge the PR, then delete its head branch |

## Result contract

Each implementation returns the fields and semantics implied by its row and normalizes backend
field names before workflow logic consumes them:

- label and assignee updates report the resulting state so claim and failure transitions can
  re-verify it;
- `list_issues` accepts arbitrary label/state filters and the union of fields required by List,
  Polling, and orphan recovery; a backend must not hardcode `claude-auto`, open state, or one field
  set;
- pagination or server-side limits preserve the `list_ready(limit)` early-termination contract;
- `get_pr_diff` returns the complete text consumed by line-count and secret-scan gates;
- `get_pr_checks` distinguishes passing, pending, and failing required checks;
- mutation success is not inferred solely from a transport's successful return status when the
  workflow requires post-write verification.

## Cautions

- Do not use GitHub search for polling; filter by label server-side and exclusions client-side.
- Do not request asynchronous auto-merge. Run `mark_pr_ready` and then `merge_pr`, in that order.
- `create_draft_pr` creates a draft. The workflow may mark it ready only after the merge gate.
- Transport selection does not own policy. Codex review, the secret scanner, forbidden credential
  paths, label-state validation, and the four-condition merge gate apply identically to every
  transport.
