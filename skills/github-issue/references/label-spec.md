# Label Specification

The exhaustive definition of the labels the github-issue skill manages.

> **Drift Prevention (in compliance with shared contract §11)**: the state transition table and the pure-function signatures are consolidated in the shared contract [`polling-pattern.md`](../../shared/references/polling-pattern.md). This file never redefines them and only links directly. The SSOT for Label Mapping is unified into [`label-mapping.md §Label Mapping`](label-mapping.md#label-mapping).

## Labels

| Label | Meaning | When it is added | When it is removed |
|-------|------|---------------|--------------|
| `claude-auto` | A self-driving target. A trust boundary — only repository administrators may add it. The body must satisfy the contract in §`claude-auto` Body Contract | The user / the Create Workflow | On cycle completion (together with merge & close) |
| `claude-running` | A cycle is running (after the atomic claim)| Cycle Step 2 | Step 6 (the review transition) / on failure (Step 9) |
| `claude-review` | Under Codex review / in the draft-PR review stage | Cycle Step 6 | On auto-merge success / on failure |
| `claude-failed-transient` | Self-driving failed (a transient error, retryable on the next tick)| `mark_failed(slug, TRANSIENT)` | On success at the next tick / on promotion to permanent |
| `claude-failed-permanent` | Self-driving failed (a permanent error, awaiting human judgment)| `mark_failed(slug, PERMANENT)` | A human removes it manually and re-submits |
| `claude-failed` | **A DEPRECATED alias** (precedence: permanent). Backward compatible via dual-write in 1.14.0, scheduled for removal in 1.16.0 | Added together with transient/permanent by `mark_failed`'s dual-write | A human removes it manually and re-submits |

> **`claude-auto` is a trust boundary**: the body of an issue carrying this label is handed to Codex. State explicitly in the documentation that only repository administrators may add it. `require_author_association` additionally checks the issue author's permission.

## `claude-auto` Body Contract

Attaching `claude-auto` is a claim that this issue can be driven **with no human present**, and the body
is the source of truth for that claim. Both sections below are **required**, and both are read
mechanically at claim time by [`self-drive-gates.md §Self-Drive Gates`](self-drive-gates.md#self-drive-gates).
An issue that does not satisfy them gets a quiet skip — it is never claimed, and no failure label is
attached, because a body that does not meet the contract is a defect in how the issue was written.

### What self-driving means

**Self-driving means running to completion in an execution environment where no human is present**
(polling loops, scheduled cloud runs). The contrast is *semi-automatic*: an interactive session where a
human is on hand and can settle a judgment call on the spot. These are different execution environments,
not two ends of a scale, and whether a human is present is 0 or 1 — so the verdict is two-valued.
The full argument, and why `部分的に自走可` is a forbidden value rather than a third state, is in
[`self-drive-gates.md §Self-Drive Gates`](self-drive-gates.md#self-drive-gates) (the canonical SSOT for the
parsing rules; this file does not restate the algorithm).

### Required section 1 — the self-drive verdict

```
## 自走可否

判定: 自走可
```

- **The permitted values are exactly two: `自走可` and `自走不可`.**
- `部分的に自走可` is a **forbidden value** and is treated as ambiguous (quiet skip). An issue that is
  only partly self-drivable gets the self-drivable part split into its own issue — writing the value at
  all means the triage is already done and only the split is missing.
- A missing section, a missing `判定:` line, or any other value is likewise a quiet skip (fail-closed).

### Required section 2 — the declared change targets

```
## 変更対象

- skills/github-issue/SKILL.md
- skills/github-issue/references/label-spec.md
```

- One repository-relative path per list item, and **nothing else on the item**. An annotated item such as
  `- file.md:170 — what to fix here` is deliberately not read as a declaration, so a body may carry a
  second annotated list under the same heading.
- The declaration is the source of truth for scope: the plan may not target a path outside it, and a
  plan that does stops the cycle at Gate 0b instead of implementing.
- The declared paths are also what the blast-radius check measures — an issue whose change reaches more
  than `max_impacted_units` units, or touches `forbidden_path_globs`, is not claimed even when it says
  `自走可`. A verdict written from the size of the edit rather than its radius is rejected here.

## State Machine (a direct link to shared contract §2)

The state-transition definitions are consolidated in the shared contract. This file does not redefine them.

- **States**: `ready` / `running` / `done` / `failed/transient` / `failed/permanent` / `archives` from [`polling-pattern.md §2 Lifecycle State Machine`](../../shared/references/polling-pattern.md#2-lifecycle-state-machine)
- **Transition Table**: see the Transition Table section of [`polling-pattern.md §2 Lifecycle State Machine`](../../shared/references/polling-pattern.md#2-lifecycle-state-machine)
- **The `transition()` pure function**: see [`polling-pattern.md §4 Pure Function Signatures`](../../shared/references/polling-pattern.md#4-pure-function-signatures)

> `claude-review` does not appear in the state set of shared contract §2. It is isolated as a running substate inside the label adapter, and is subsumed into running by `is_running(labels) := "claude-running" ∈ labels OR "claude-review" ∈ labels`. See [`label-mapping.md §Label Mapping`](label-mapping.md#label-mapping) for details.

## Label Mapping (a direct link to the SSOT)

The mapping table from shared-contract states to GitHub label sets has [`label-mapping.md §Label Mapping`](label-mapping.md#label-mapping) as its canonical SSOT. Do not duplicate it in this file (preventing a DRY violation).

## Backward Compatibility

### On read (the Precedence Rule)

For the definition of the `state_of_failure()` function, see [`label-mapping.md §state_of_failure Precedence Rule`](label-mapping.md#state_of_failure-precedence-rule). The essentials:

- When a new label (`claude-failed-transient` / `claude-failed-permanent`) is present, ignore the old `claude-failed` alias (guarding against a stale leftover)
- Only when the old `claude-failed` stands alone is it treated as `PERMANENT` via the legacy alias
- When both `claude-failed-transient` and `claude-failed-permanent` are attached at once, treat it as **an invalid state: log a warning and handle it as `failed/permanent` (fail-closed)**

### On write (Atomic Dual-Write + Verification)

`mark_failed(slug, kind)` **adds the new and old labels together in one selected-transport
`edit_issue_labels` operation** (avoiding both doubled API calls and partial failure):

- `edit_issue_labels(${N}, add=["claude-failed-transient", "claude-failed"], remove=[])`
- or `edit_issue_labels(${N}, add=["claude-failed-permanent", "claude-failed"], remove=[])`

After adding them, re-fetch the label set with `get_issue(${N}, fields=["labels"])` and verify:

- On a mismatch, **retry with backoff up to 3 times** (0s / 1s / 2s)
- On final failure, write a `<state_root>/recovery/{N}` marker plus `release(slug)` so the next tick's `rollback_orphans()` re-evaluates it
- **This structurally prevents leaving an issue with zero labels**

For the detailed pseudocode and the crash-safe ordering invariant (the order CA-1: marker write → CA-2: release), see [`polling-adapter.md §mark_failed(slug, kind)`](polling-adapter.md#mark_failedslug-kind).

### Recovery Marker

When `mark_failed`'s verification ultimately does not pass, place a `<state_root>/recovery/{issue_number}` marker (an empty file) so the next tick's `rollback_orphans()` is guaranteed to re-evaluate it. For details, see `_check_recovery_markers` in [`adapter-internals.md §rollback_orphans Sub-Steps`](adapter-internals.md#rollback_orphans-sub-steps).

### Migration Exit Strategy

| Phase | Version | State |
|---|---|---|
| Introduction | 1.14.0 | Dual-write begins; old readers can still detect it through the alias |
| Monitoring | 1.14.x | Periodically check (manually) the number of issues carrying `claude-failed` alone |
| Announcement | 1.15.0 | Add the notice "the alias is removed in 1.16.0" to `label-spec.md`, and state it in the same release note |
| Removal | 1.16.0 and above | Remove the alias-read precedence; old readers are unsupported |

**Removal conditions** (satisfy any one of them, confirmed in the plan of a separate cycle):

1. Migration of every `claude-failed`-only issue to the new labels is complete
2. At least 4 weeks have passed since the 1.15.0 announcement
3. An operational regime is established in which the `require_alias_compat` config can be set to `false`

### Downgrade is unsupported

**Downgrading from 1.14.0 or later to 1.13.x is unsupported.**

- Because issues carrying the new labels (`claude-failed-transient` / `claude-failed-permanent`) become invisible to an old reader, resulting in **silent data loss**
- State it explicitly in the `plugin.json` release note and in this file

## Advance Notice of Alias Removal

The old `claude-failed` alias is **scheduled for removal in 1.16.0**. How it is announced:

- At the 1.15.0 release, state "DEPRECATED — removed in 1.16.0" explicitly on the corresponding row of `label-spec.md`
- Describe the migration procedure in the same release note
- Allow a migration period of at least 4 weeks from the announcement

## Concurrency Safety

- Adding `claude-running` is guarded by **3 layers of defense: assignee exclusion + post-claim re-verify + local flock(2)** (see SKILL.md Cycle Step 2; the details of the 3 layers are consolidated in [`adapter-internals.md §claim() 3 Layers of Defense`](adapter-internals.md#claim-3-layers-of-defense))
- Issues carrying `claude-running` / `claude-review` / `claude-failed-*` are invisible to polling (a client-side filter)
- Even when several workers target the same issue simultaneously, only one succeeds at adding the label
- **Single-host premise**: distributed polling from several hosts is unsupported. See [`polling-adapter.md §Assumptions`](polling-adapter.md#assumptions) for details
