# Workspace Isolation Contract

Workspace isolation controls where an orchestrated run executes. Artifact placement and
transport remain governed by the [Agent Artifact Store](artifact-store.md). The two policies
are deliberately separate: `.agents/workspace.yml` chooses a workspace, while
`.agents/artifacts.yml` chooses an artifact store.

## Policy and resolution

The tracked policy has exactly one key:

```yaml
isolation: worktree
```

The in-place form is `isolation: inplace`. `isolation` MUST be either `worktree` or
`inplace`. Resolution happens once at the outer
orchestrator boundary, in this precedence order:

1. a one-shot invocation override;
2. `.agents/workspace.yml`;
3. when the file is missing, the backward-compatible default `inplace`.

An invalid document, unknown key, or invalid value is a blocking error; it MUST NOT silently
resolve to either mode. The resolved execution context is authoritative for inner skills.
An inner skill MUST NOT reread policy, prompt again, or create a nested worktree.

Fresh `artifacts init` writes `isolation: worktree` only if no workspace policy, artifact
policy, canonical store, or legacy store existed when initialization began. Initialization
of an existing or partially initialized repository MUST remain idempotent, report the missing
policy, and offer an explicit opt-in edit rather than silently changing behavior. Artifact
policy schema v1 and `worktree_scope: worktree` are unchanged.

## Ownership and execution

In `inplace` mode, existing execution behavior is unchanged. In `worktree` mode, the outer
orchestrator owns creation, ingress, delegation, harvest, publication, and cleanup. This
applies to `parallel-cycle`, standalone `cycle`, standalone `iterate`, and `github-issue`.

The orchestrator copies the store-relative pinned plan into the satellite before
delegation and passes a resolved context. Delegates update the pinned plan and other permitted
per-entity artifacts. They MUST NOT update main-tree state or satellite singleton state.
The main orchestrator alone composes `status.md`, `session-history.md`, and derived indexes.
Issue #93 supersedes #92 only for progress transport: file harvest is authoritative, while
#92's ingress and singleton-suppression requirements remain normative.

## Transactional lifecycle

The authoritative lifecycle is main-tree runtime state. Normal transitions are:

```text
created -> active -> harvesting -> staged -> published -> cleanup_allowed
                                      \-> discarded -> cleanup_allowed
```

`discarded` is an explicit terminal disposition for a validated staging set that an
authorized human chose not to publish. Exceptional states are `failed_readonly` and
`recovery_required`.

| Current | Allowed next state | Condition |
|---|---|---|
| `created` | `active`, `failed_readonly` | ingress complete; or activation fails |
| `active` | `harvesting`, `failed_readonly` | terminal-path harvest starts (capability is consumed on this edge); or run fails before harvest |
| `harvesting` | `staged`, `recovery_required` | collect succeeds; or validation/collection is interrupted |
| `staged` | `published`, `discarded`, `recovery_required` | merge verification and destination CAS pass; explicit authorized discard; otherwise publish nothing |
| `published` | `cleanup_allowed`, `recovery_required` | capability is non-live and staging disposition recorded |
| `discarded` | `cleanup_allowed`, `recovery_required` | capability is non-live and discard evidence recorded |
| `failed_readonly` | `active`, `harvesting`, `recovery_required` | explicit authorized resume, retry harvest, or unresolved failure |
| `recovery_required` | `harvesting`, `staged` | recovery revalidates and recollects preserved bytes, or resumes a verified staged transition |

Every lifecycle edge in this table, including recovery edges, MUST be committed while holding
`lifecycle.lock` through a single atomic compare-and-swap of both `lifecycle_state` and
`lifecycle_version` against their expected prior values (the expected prior state and
version). Transitions not listed in the table
are forbidden. Authorization and serialization are separate checks. An illegal or stale
transition fails closed without changing state.

Harvest is required after success, failure, cancellation, and verification failure. It has
two phases: collect validates and stages untrusted satellite bytes; publish occurs only after
the branch merge and post-merge verification outcome is known. Cleanup requires staging to
be published or deliberately discarded, the capability to be non-live, and lifecycle state
`cleanup_allowed`. Here, terminal capability handling means it is non-live: harvest consumes
it, while failure handling may revoke it. A harvest failure or conflict preserves the
satellite and staging.
Only a complete staging set that passed collection validation may enter `staged` and later
`discarded`. Partial or invalid staging enters `recovery_required`; failure evidence MUST say
that validation did not complete, and the satellite and staging bytes MUST be preserved.

## Crash reconciliation

At startup, an orchestrator reconciles provenance records it owns under the lifecycle lock.
It treats an owner as live only when both its PID and recorded process start time still match;
this prevents PID reuse from transferring ownership. It revokes capabilities belonging to
dead owners and either completes or rolls back an atomic transition. It never guesses through
an artifact conflict. Preserved worktrees are read-only until the main-tree orchestrator
issues a new run-scoped capability.

## Recovery interface and diagnostics

The single user-facing recovery entry point, run from the main tree, is:

```text
/claude-skills:artifacts recover --run-id {run_id}
```

Every denied write, preserved satellite, conflict, and interrupted harvest diagnostic MUST
use this exact structured template (one field per line):

```text
reason_code={reason_code}
run_id={run_id}
main_tree_path={main_tree_path}
worktree_path={worktree_path_or_unavailable}
reason={reason}
recovery_command=/claude-skills:artifacts recover --run-id {run_id}
```

The closed set of reason-code lines is:

- `reason_code=SATELLITE_WRITE_DENIED`
- `reason_code=SATELLITE_PRESERVED`
- `reason_code=HARVEST_CONFLICT`
- `reason_code=HARVEST_INTERRUPTED`

The preserved-worktree field uses the literal `unavailable` when no path can safely be
reported. Diagnostics MUST NOT contain the raw capability.

Recovery MAY retry collect from `failed_readonly` or `recovery_required`, retry publish from
`staged` after destination comparison succeeds, or create a newly authorized resume context.
Recovery MUST revalidate or collect the preserved bytes, transition through `harvesting` to
`staged`, and only then retry publish; it cannot publish directly from `recovery_required`.
Recovery MUST transition through `harvesting` to `staged` before an authorized discard; it
cannot discard directly from `recovery_required`. It MUST NOT choose a winner for a conflict,
delete a preserved worktree, or publish after a failed/reverted merge without human judgment.
