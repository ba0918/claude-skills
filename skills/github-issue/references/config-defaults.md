# Configuration Defaults

> **SSOT Note**: the values that live in the shared contract [`polling-pattern.md §10 Default Config`](../../shared/references/polling-pattern.md#10-default-config-conservative-initial-values) (`max_parallel` / `max_iter` / `max_wallclock` / `failed_streak_limit` / `transient_retry_limit` / `tick_interval_loop_mode` / `dry_run`, and so on) are referenced with the shared contract as their SSOT and are never redefined here. This file carries **only GitHub-specific config**.

Every value can be overridden with the `--config key=value` argument.

## GitHub-specific Config

| Key | Default | Unit | Description |
|-----|---------|------|------|
| `max_review_iterations` | `3` | times | The loop cap on Codex review → iterate fix |
| `parallel_worktree_limit` | `1` | count | The physical worktree parallelism cap handed to parallel-cycle. Raise it only by explicit opt-in. A separate responsibility from the shared contract's `max_parallel` (see Precedence below) |
| `polling_interval` | `10m` | time | The external invocation interval of the `/loop` command (a reference value). A **distinct concept** from §10's `tick_interval_loop_mode` (the `--loop` retry interval inside a tick, default 30s). `/loop` starts polling in units of ticks, and inside it the `--loop` mode re-ticks every `tick_interval_loop_mode` |
| `min_rate_limit_remaining` | `500` | requests | Skip polling when the remaining GitHub API budget is below this |
| `max_diff_lines` | `2000` | lines | A PR exceeding this is not handed to Codex and becomes claude-failed |
| `codex_review_timeout` | `5min` | time | The timeout for a single Codex invocation |
| `codex_consecutive_failure_threshold` | `3` | times | Once transient Codex API failures occur this many times consecutively, treat it as a permanent failure. An independent parameter from `transient_retry_limit` (§10) ([details](codex-review-loop.md#codex_consecutive_failure_threshold-vs-transient_retry_limit))|
| `auto_merge_strategy` | `squash` | kind | The merge method for `gh pr merge` (`squash` / `merge` / `rebase`)|
| `codex_required_for_merge` | `true` | bool | **Locked (not user-overridable)**: because a GitHub merge is irreversible, fail-closed is enforced. Even an attempt to override it with `--config codex_required_for_merge=false` emits a warning and resets it to `true`.|
| `require_author_association` | `OWNER,MEMBER,COLLABORATOR` | csv | Skip polling when the issue author is none of these |
| `enable_base64_scan` | `false` | bool | Whether to enable secret-scanner's generic Base64 pattern. Off by default because it produces many false positives. See [`secret-scanner.md`](secret-scanner.md) for details |
| `rollback_gh_fetch_cap` | `10` | count | The per-tick cap on `gh issue view` API calls in `rollback_orphans()` steps ③ / ④. The excess carries over to the next tick (preventing a fetch storm)|
| `impact_command` | (unset) | command | The external command that computes the blast radius of a change, used by [Gate 0](polling-adapter.md#self-drive-gates). `{files}` expands to the declared paths, space separated. **When unset, Gate 0's impact check is a no-op** (the skill is distributed to other repositories, and there is no portable oracle) |
| `max_impacted_units` | `1` | count | The upper bound on impacted units that still allows self-driving. Applied only when `impact_command` is set |
| `forbidden_path_globs` | `skills/shared/**` | glob csv | Paths that reject self-driving regardless of the impact count. Evaluated **without** the oracle, so it stays in force even when `impact_command` is unset |
| `default_branch` | (resolved per run) | name | **Not a stored setting**: resolved at Cycle Workflow Step 4 with `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`, and used as the branch point (`origin/{default_branch}`) of the dedicated worktree. Never hardcoded and not user-overridable — a configured branch point would reintroduce the nondeterministic PR bases that issue #83 removed |

### Why the impact oracle is pluggable

`github-issue` is distributed and runs inside other people's repositories, so it must not depend on
this repository's `skills/skill-regression/scripts/ledger.py`. `impact_command` is therefore an
injection point, unset by default, and Gate 0's impact check degrades to a no-op wherever no oracle
is configured. What never degrades is `forbidden_path_globs` — it needs no oracle.

This repository configures:

```
--config 'impact_command=python3 skills/skill-regression/scripts/ledger.py --impact {files}'
```

The command's stdout is read as **one impacted unit per line** (in this repository, a skill name), and
the line count is the impact count. A non-zero exit is **fail-closed**: never read it as "0 impacted
units" (see [`polling-adapter.md §Self-Drive Gates`](polling-adapter.md#self-drive-gates)).

> **Where the per-repository value is persisted**: until `.agents/config/` exists, pass it through
> `--config` and keep the table above as the documented value.

## Parallel Precedence Rule

Because `parallel_worktree_limit` and the shared contract's `max_parallel` (§10) carry different responsibilities, when both apply within the same tick the **effective cap is `min(...)`**:

| Parameter | Where it lives | Responsibility |
|---|---|---|
| `max_parallel` | Shared contract §10 | The claim cap per tick. Logical concurrency in units of issues |
| `parallel_worktree_limit` | This file (GitHub-specific) | The physical worktree resource cap. The parallelism handed to the `parallel-cycle` skill |

The effective cap:

```
effective_parallel = min(max_parallel, parallel_worktree_limit)
list_ready(effective_parallel)  # align the claim count itself with the physical cap
```

This prevents a state where claims advance while worktrees wait. Since `parallel_worktree_limit` defaults to 1, execution is serial unless it is overridden explicitly.

## Schedule Path Alternative

Polling can also run through the `schedule` skill (cron) instead of `/loop github-issue-polling`. This is useful when long cycles run, or when you do not want `/loop` occupied.

Example:
```
schedule create --cron "*/10 * * * *" --command "/github-issue-polling --stateless"
```

> **Always pass `--stateless`**: a cron start means 1 invocation = 1 tick and the process dies every time, so
> without `--stateless` the triple guard of `max_iter` / `max_wallclock` / `failed_streak` resets each time and is effectively disabled
> (see the shared contract [`§6.5 Tick Session`](../../shared/references/polling-pattern.md#65-tick-session-persisting-the-safety-brakes-for-stateless-execution)).

## Override Example

```
github-issue cycle 42 --config max_review_iterations=5 --config parallel_worktree_limit=2
```

## Validation

- `parallel_worktree_limit >= 1`
- `max_review_iterations >= 1`
- `max_diff_lines >= 100`
- `min_rate_limit_remaining >= 0`
- `auto_merge_strategy ∈ {squash, merge, rebase}`
- `rollback_gh_fetch_cap >= 1`
- `max_impacted_units >= 1`
- `impact_command`, when set, contains the `{files}` placeholder exactly once

An invalid value causes an error exit at startup.
