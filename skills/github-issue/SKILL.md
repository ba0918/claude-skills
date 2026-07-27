---
name: github-issue
description: Drive Claude autonomously from a GitHub issue, fully automating polling then parallel cycles then a draft PR then Codex review then the fix loop then auto merge and close. It provides the 4 workflows `create` / `list` / `polling` / `cycle`. Use when the user says "github issue", "gh issue", "issue polling", "auto merge", or "run it autonomously".
---

# github-issue Skill

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

A self-driving workflow that takes a GitHub issue as its trust boundary. Execution is controlled concurrently-safely by a label-based state machine, and it runs headless through `/loop`.

> **Scope:** This skill works on issues and PRs on GitHub. It is independent of the `issue` skill, which works on the local `.agents/artifacts/issues/`.

## Workflow Selection

The first keyword of the arguments selects the workflow.

| Keyword | Workflow | Purpose |
|---------|----------|------|
| `create` | Create Workflow | Create a new issue (interactive) |
| `list` | List Workflow | List open issues carrying `claude-auto` |
| `polling` | Polling Workflow | The headless tick called from `/loop` |
| `cycle` | Cycle Workflow | Drive a single issue from draft PR through Codex review to auto merge |

> **Note:** `plan` and `close` are implemented as sub-steps inside cycle (removed from the outward-facing commands).

## Common Pre-checks

Run these at the start of every workflow.

1. **gh CLI check**: `gh --version` must succeed. On failure, exit stating that the gh CLI is required and can be installed from https://cli.github.com/.
2. **gh authentication check**: `gh auth status` must succeed. On failure, exit stating that the gh CLI is unauthenticated and that `gh auth login` should be run.
3. **Repository check**: confirm the current directory sits inside a GitHub repository with `gh repo view --json nameWithOwner`. On failure you may resolve it through the same order as `fetch_git_remote_url()` ([`references/polling-adapter.md §state_root Resolution`](references/polling-adapter.md#state_root-resolution)) — `git remote get-url origin` first, `gh repo view` as the fallback. Keeping both in the same order guarantees that the repository check and state_root resolution never disagree about where the URL came from.
4. **Configuration values**: load the defaults from `references/config-defaults.md`. Any value overridden by an argument takes precedence.

> **Relationship to Polling (fail-closed)**: a failure of the pre-checks above is fail-closed and does not start a polling tick (same path as `fail_closed`, with `error_kind` treated as equivalent to [`tool_missing`](references/polling-adapter.md#error_kind-enum)). The one exception: when the user explicitly asks for a check that needs no GitHub access (confirming a kill file stop, for example), you may record the pre-check failure and continue with that check alone.

## References

See the following references for the details of each workflow. The shared polling contract is referenced by direct link to [`../shared/references/polling-pattern.md`](../shared/references/polling-pattern.md) (drift prevention §11).

- [`references/polling-adapter.md`](references/polling-adapter.md) — Label state adapter implementation spec (Interface Table / state_root / error_kind / the three-stage claim defence / rollback sub-steps)
- [`references/label-spec.md`](references/label-spec.md) — Label definitions + Backward Compatibility + Migration Exit Strategy
- [`references/codex-review-loop.md`](references/codex-review-loop.md) — Codex PR review delegation prompt + normalize_github_error + the fail-closed override
- [`references/config-defaults.md`](references/config-defaults.md) — Table of GitHub-specific configuration values (anything duplicated from shared contract §10 is a direct SSOT link)
- [`references/secret-scanner.md`](references/secret-scanner.md) — The regex set for secret detection
- [`references/gh-commands.md`](references/gh-commands.md) — List of semantic wrappers around the gh CLI
- [`references/cleanup-spec.md`](references/cleanup-spec.md) — Orphan cleanup rules for worktrees and branches + the sanitize responsibility split

---

## Create Workflow

Take issue content from the user in natural language, infer suitable labels, and run `gh issue create`.

### Steps

1. Run Common Pre-checks
2. Parse the user arguments (title + body + any hints)
3. Fetch the repository's existing labels with `gh label list --json name,description,color`
4. From the issue content and the existing labels, infer:
   - The labels to apply (`bug` / `feature` / `docs` / `enhancement`, ...)
   - Whether `claude-auto` may be attached (does it carry acceptance criteria clear enough to drive itself?)
   - A candidate title (when one is missing)
5. **Confirm with the user**:
   - Show: title / body / inferred labels / whether `claude-auto` applies / the reasoning
   - Options: create / revise / cancel
6. Once approved, create it with `gh issue create --title ... --body ... --label ...`
7. Show the result (the issue URL)

> **Never call Create from a non-interactive path**: invoking this workflow from a headless path such as polling is forbidden.

---

## List Workflow

List the open issues carrying the `claude-auto` label.

### Steps

1. Run Common Pre-checks
2. Run `gh issue list --label claude-auto --state open --json number,title,labels,assignees,author,authorAssociation --limit 100`
3. Classify client-side and display (for the precedence rule see [`references/polling-adapter.md §state_of_failure Precedence Rule`](references/polling-adapter.md#state_of_failure-precedence-rule)):
   - **Ready**: carries none of `claude-running`, `claude-review`, or the failed labels
   - **Running**: carries `claude-running`
   - **In Review**: carries `claude-review`
   - **Failed (Transient)**: `state_of_failure(labels) == TRANSIENT`
   - **Failed (Permanent)**: `state_of_failure(labels) == PERMANENT` (including a lone legacy `claude-failed`)
4. On zero results, print `No claude-auto issues found.` and finish

---

## Polling Workflow

The headless tick called periodically from `/loop github-issue-polling`. When several issues are detected, it delegates to parallel-cycle.

> **Single-host assumption**: this workflow is designed for a single-host, single-process ralph loop. Distributed polling from several hosts is not supported (for the reasoning see [`references/polling-adapter.md §Assumptions`](references/polling-adapter.md#assumptions)).

> **Persisting the safety brake (`--stateless`)**: a call from `/loop` or cron is one invocation = one tick and the process dies each time, so the
> `max_iter` / `max_wallclock` / `failed_streak` counters cannot survive in process memory. When running on a timer, pass
> `--stateless` and persist the counters to `<state_root>/session.json` per shared contract
> [`§6.5 Tick Session`](../shared/references/polling-pattern.md#65-tick-session-persisting-the-safety-brakes-for-stateless-execution)
> (the `failed_streak` halt is sticky — it does not resume until `session.json` is deleted).

### Workflow structure

This workflow is **a thin orchestrator conforming to the tick() pseudocode in shared contract [`../shared/references/polling-pattern.md §5 Tick Orchestration`](../shared/references/polling-pattern.md#5-tick-orchestration-pseudocode-declaration-level)**. The state machine (§2), the pure functions (§4), the safety brake (§6), and the Tick Schema (§7) live in the shared contract; this file describes only the order in which adapter methods are called.

Label adapter implementation details — the three-stage claim defence, state_root resolution, error_kind classification, the five-stage rollback — are hidden inside [`references/polling-adapter.md`](references/polling-adapter.md) (SKILL.md only calls `claim(slug)`).

### Steps

1. Run **Common Pre-checks**
2. **Adapter init**: obtain the Label adapter instance. Resolving `state_root` runs the XDG fallback, the exclusive creation of `.clone_url`, and the `unsupported FS fail-closed` (details in [`references/polling-adapter.md §state_root Resolution`](references/polling-adapter.md#state_root-resolution))
3. **Kill file check**: use `adapter.kill_file_path()` and check `.STOP.hard` then `.STOP`, in that order. Halt immediately if either exists (shared contract §6.1)
   - Under `--stateless`, evaluate `adapter.load_session()` → `session_resume_action(prev, now, config)` right after this; on `Halt{reason}`, finish immediately with `TickResult(halt_reason=reason)` without claiming (shared contract §6.5)
4. **Orphan recovery**: run the five-stage recovery with `adapter.rollback_orphans(now)` (shared contract §6.4 + [`references/polling-adapter.md §rollback_orphans Sub-Steps`](references/polling-adapter.md#rollback_orphans-sub-steps))
5. **Archive**: `adapter.archive_month_boundary()` (a no-op on GitHub; it only refreshes the cache)
6. **Rate limit pre-check**: `gh api rate_limit --jq '.rate.remaining'` ≥ `min_rate_limit_remaining`. Quiet skip when below
7. **List ready**: call `adapter.list_ready(effective_parallel)` with `effective_parallel = min(max_parallel, parallel_worktree_limit)` (for the precedence rule see [`references/config-defaults.md`](references/config-defaults.md)). One API call; do not re-fetch even if the client-side filter leaves fewer than the limit
8. **Atomic claim**: call `adapter.claim(slug)` for each slug. Failures are a quiet skip (the three-stage claim defence is internal to the adapter). The `authorAssociation` filter is already applied inside `adapter.list_ready()` ([`references/polling-adapter.md §list_ready(limit)`](references/polling-adapter.md#list_readylimit)); do not repeat it in the orchestrator
9. **Dry run decision**: when `config.dry_run` is set or `<state_root>/.polling-initialized` does not exist, `release()` everything claimed and return `halt_reason="dry_run"`
10. **Delegate to parallel-cycle**: build a plan from the claimed issues and delegate to `claude-skills:parallel-cycle`. **parallel-cycle must not re-claim** (claim responsibility stays centralised in Polling)
11. **Classify & persist**: call `classify_failure(normalize_github_error(exc))` for each outcome.
    - **Success**: `adapter.mark_done(slug)`
    - **Transient failure**: `n = adapter.increment_retry(slug)` → `kind = should_promote_to_permanent(n, config.transient_retry_limit) ? Permanent : Transient` → `adapter.mark_failed(slug, kind)` (per the shared contract §5 Classify & persist block)
    - **Permanent failure**: `adapter.mark_failed(slug, Permanent)` (skip `increment_retry`; apply the shared contract §4 `classify_failure` pure function directly)
    - `mark_failed` is an atomic dual-write plus verification in a single `gh issue edit` (details in [`references/polling-adapter.md §mark_failed(slug, kind)`](references/polling-adapter.md#mark_failedslug-kind))
    - `error_kind = "lock"` does not count towards `failed_streak` (silent skip; see [`references/polling-adapter.md §error_kind Handling Rules`](references/polling-adapter.md#error_kind-handling-rules))
12. **Emit TickResult**: return the structured counters conforming to shared contract §7 Tick Schema — `{run_id, tick_started_at, claimed, done, failed_transient, failed_permanent, halt_reason?}`. All seven fields including `run_id` and `tick_started_at` are invariant (see shared contract §7)
13. **On the first successful tick**: create `<state_root>/.polling-initialized` with `write_atomic` (which lifts the forced dry-run from the next tick on)
14. **Session persist (`--stateless` only)**: compute the counter update and the halt decision with `next_session_state(session, tick_result)`, then persist with `adapter.save_session()` (shared contract §6.5)
15. **Measurement event append**: append the TickResult counters as a measurement event ([measurement-identity.md §4](../shared/references/measurement-identity.md#4-mapping-table-for-the-existing-systems)): `python3 {shared_scripts}/measurement_identity.py emit --system polling-label --event tick --skill github-issue --repo-root {repo_root} --run-id {run_id} --outcome '{TickResult counter JSON}'`. `{shared_scripts}` is the `shared/scripts` directory **where the skills are installed**, given as an absolute path; `{repo_root}` is the target project. This skill runs inside a user's project, which holds no `skills/` tree of its own, so a repository-relative path never resolves there (same discipline as the [CLI invocation conventions](../shared/references/checkpoint-pattern.md#cli-invocation-conventions-the-discipline-on-the-skill-side)). A failure here only warns; it never blocks the tick

### Snapshot boundary

Work only on this tick's snapshot. Issues added midway are picked up by the next tick.

---

## Cycle Workflow

The core workflow that drives a single issue to completion.

### Pre-condition

- `claude-skills:cycle` assumes it only makes commits on the current branch. **Branch operations, push, and PR creation are this workflow's responsibility.**

### Steps

#### 1. Pre-check

1. Common Pre-checks
2. `gh api rate_limit --jq '.rate.remaining'` ≥ `min_rate_limit_remaining`
3. Confirm an issue number N was given in the arguments. **N must match `^[1-9][0-9]*$`** (rejecting `0` and any zero-padded form). On no match, fail immediately with `"invalid issue_number"` (to prevent command injection and mistaken invocations)
4. **`codex_required_for_merge` is forced to `true`**: ignore any `--config` override from the user; the pre-flight check in `references/codex-review-loop.md` logs a warning and then resets it to `true`

#### 2. Atomic Claim

Delegated to the adapter: just call `adapter.claim(slug)`. On failure, quiet abort with `ClaimFailed{reason}` (no retry).

The three-stage defence (lockfile + gh edit + re-verify) is hidden in [`references/polling-adapter.md §claim() 3 Layers of Defense`](references/polling-adapter.md#claim-3-layers-of-defense). SKILL.md knows only the interface and does not depend on the internals (shared contract §3 + Layer Separation).

- lockfile path: `<state_root>/claim/{N}.lock` (non-blocking `flock(2)`)
- Failure reasons: one of `LockBusy` / `gh edit failed` / `post-claim verify failed`
- `issue_number` is validated up front (the adapter verifies it matches `^[1-9][0-9]*$`)

#### 3. Building the plan (internal sub-step)

1. Fetch the issue with `gh issue view ${N} --json number,title,body,labels`
2. Build a plan by invoking the `claude-skills:plan` skill from the issue body and acceptance criteria
3. Prepend `**GitHubIssue:** #${N}` to the plan

#### 4. Running cycle

1. Create a new branch: `git switch -c gh-issue-${N}-$(date +%Y%m%d%H%M%S)`
2. Run the `claude-skills:cycle` skill (passing the plan file as the argument). cycle stacks its commits on this branch.

#### 5. Creating the draft PR

```bash
git push -u origin <branch>
gh pr create --draft --title "<plan title>" --body "Closes #${N}\n\n<plan summary>"
```

**Always pass `--draft`** (do not undraft until the auto merge gate has passed).

#### 6. Label transition

Remove `claude-running` and add `claude-review`:

```bash
gh issue edit ${N} --remove-label claude-running --add-label claude-review
```

#### 7. The Codex review loop

See [`references/codex-review-loop.md`](references/codex-review-loop.md) for the details.

Outline:

1. **Pre-filters**:
   - `gh pr diff <PR>` exceeds `max_diff_lines` → skip Codex and go straight to Step 9 (claude-failed)
   - Scan the diff with the regexes in `references/secret-scanner.md`. On a hit, claude-failed the same way
2. **Prompt injection defence**: wrap the issue body in `<untrusted_user_content>...</untrusted_user_content>`
3. **Differential review**: from the second round on, tell Codex the previous findings and how they were addressed, and skip re-reviewing files already marked LGTM
4. **Calling Codex**: follow the subagent pattern defined in [`shared/references/codex-integration.md`](../shared/references/codex-integration.md) (the concrete subagent name lives in `references/codex-review-loop.md`). Pass the diff, the plan, and the acceptance criteria, and force `{"verdict": "LGTM"|"NEEDS_CHANGES", "findings": [...]}`
5. **Decision**:
   - `LGTM` → leave the loop and go to Step 8
   - `NEEDS_CHANGES` → hand `findings` to `claude-skills:iterate` for the fix → `git push` → next iteration
6. **Iteration cap**: reaching `max_review_iterations` (default 3) means claude-failed
7. **Transient vs permanent Codex failures**: transient trouble such as network or rate limits is retried on the next tick; `codex_consecutive_failure_threshold` (default 3) consecutive failures becomes a permanent failed

#### 8. The auto merge gate (four AND conditions)

Merge only when **all** of the following hold.

1. Codex says `LGTM`
2. `gh pr checks <PR>` all pass
3. Zero secret-scanner detections
4. The changed files include no `.env` / `*.key` / `*.pem` / `credentials.*`

On passing:

```bash
gh pr ready <PR>                       # undraft
gh pr merge <PR> --squash --delete-branch
gh issue close ${N}
gh issue edit ${N} --remove-label claude-auto --remove-label claude-review
```

> Do not use the `--auto` flag. Run ready then merge explicitly, in that order, so the ordering is guaranteed.

#### 9. Handling failure

- Keep the PR as a draft
- Save the error details as structure into the **FS retry state** (`<state_root>/retry/{N}.json`) — retry_count / last_failed_at / run_id only; storing free-text errors is forbidden (shared contract §3)
- Remove `claude-running` / `claude-review` and run the **atomic dual-write** through `mark_failed(slug, kind)`:
  - Decide the kind (TRANSIENT / PERMANENT) with `classify_failure(normalize_github_error(exc))`
  - Add both the new and the legacy label at once with a single `gh issue edit --add-label claude-failed-{transient,permanent} --add-label claude-failed`
  - Verify afterwards with `gh issue view`; on a mismatch, retry three times with backoff (0s/1s/2s)
  - On final failure, write the `<state_root>/recovery/{N}` marker (crash-safe ordering: marker write, then release) and `release(slug)` so the next tick re-evaluates it
  - Details in [`references/polling-adapter.md §mark_failed(slug, kind)`](references/polling-adapter.md#mark_failedslug-kind) + [`references/label-spec.md §Backward Compatibility`](references/label-spec.md#backward-compatibility)
- Release the lockfile (automatic on process exit; `flock(2)` releases at the kernel level)

#### 10. Idempotence

- Every workflow is safe to re-run because it reads the label state
- If a worktree is left behind, detect it with `git worktree list` and either reuse it or clean it up per `references/cleanup-spec.md`

---

## Configuration Override

Configuration values can be overridden with the `--config key=value` argument. Every value is defined in the table in [`references/config-defaults.md`](references/config-defaults.md).

Example:
```
github-issue cycle 42 --config max_review_iterations=5 --config parallel_worktree_limit=2
```

---

## Codex Review

The single aggregation point for calling Codex in Cycle Workflow Step 7 (the Codex review loop). The concrete subagent name, the prompt, the JSON contract, and the iteration logic are all collected in [`references/codex-review-loop.md`](references/codex-review-loop.md). Step 7 and this section are the only Codex entry points in this skill; other references must link here.
