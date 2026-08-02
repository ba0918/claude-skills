# Agent Artifact Store Contract

Agent-generated working artifacts are project state, not reader-facing documentation. All
skills that create or consume plans, issues, ideas, handoff, loop, review, or decision state MUST resolve
their paths through this contract instead of embedding a `docs/` path.

## Canonical namespace

The repository policy lives at `.agents/artifacts.yml`. The default logical store is:

```text
.agents/artifacts/
├── plans/
├── issues/
├── ideas/
├── handoff/
├── loop/
├── reviews/
└── decisions/
```

The namespace is provider-independent. Do not add model, vendor, or agent names to the
path. Format differences belong in artifact schema metadata.

The `decisions` kind holds decision and case-law records — durable rationale of architecture and technology bets. No legacy `docs/decisions` predecessor, so it participates in initialization but not migration.

## Policy schema v1

```yaml
schema_version: 1
root: .agents/artifacts
visibility: local
worktree_scope: worktree
```

- `schema_version` MUST be `1`.
- `root` MUST be the repository-relative canonical path `.agents/artifacts` in v1.
- `visibility` is `local`, `shared-private`, or `public`.
- `worktree_scope` MUST be `worktree` in v1. Repository-wide shared storage is reserved
  for a later backend contract.

Missing policy resolves to the v1 defaults above. Invalid or unknown values never fall
back to a more public location.

Workspace selection and worktree lifecycle are defined by
[Workspace Isolation](workspace-isolation.md). This section defines the artifact side of
that protocol.

## Satellite stores and transport

A linked worktree has its own canonical artifact root, called a **satellite store**. The main
tree remains the authority for transport and singleton state. Linked-worktree identity MUST
be derived through Git common-directory metadata; submodules MUST be explicitly excluded.
Callers do not supply unresolved absolute destinations.

### State classification

- **Mergeable entities:** the pinned per-plan file and newly created durable entity files.
  An authorized satellite may write these and harvest may import them.
- **Singleton state:** `status.md`, `session-history.md`, and any other cross-run singleton.
  A satellite MUST NOT write these; the main orchestrator composes them after collection.
- **Derived indexes:** regenerated in the main tree, never transported or merged.
- **Control state:** runtime, ephemeral, dotfiles, migration data, and transport metadata.
  These are never harvestable artifacts. Delegation result files
  (`.agents/runtime/delegation/{run_id}_*.md`) are control state; in worktree mode they
  reside in the satellite's runtime area (the delegate writes them) and are not transported
  — the orchestrator reads them directly from the satellite path before cleanup.

Unknown future artifact kinds are eligible when they satisfy the generic mergeable-entry
rules. Transport MUST sweep the complete store and then fail closed on exclusions rather
than enumerate only today's known kinds.

### Runtime layout and provenance schema

Authoritative records live only in ignored main-tree runtime:

```text
.agents/runtime/satellite-runs/{run_id}/
├── provenance.json
├── lifecycle.lock
├── ingress-manifest.json
├── discard-evidence.json
└── staging/
```

The concrete discard-evidence record is
`.agents/runtime/satellite-runs/{run_id}/discard-evidence.json`.

`provenance.json` MUST contain:

| Field | Meaning |
|---|---|
| `schema_version` | integer schema version, initially `1` |
| `run_id` | unique run identifier |
| `main_tree_path` | canonical local main-tree path |
| `worktree_path` | canonical linked-worktree path |
| `worktree_id` | identity derived from Git common-dir metadata |
| `pinned_plan` | store-relative plan path (relative to the canonical artifact root) |
| `created_at` | UTC timestamp |
| `owner_pid` | orchestrator process ID used as one part of reconciliation identity |
| `owner_pid_start_time` | OS-reported process start time paired with `owner_pid` |
| `ingress_manifest_digest` | SHA-256 of the canonical manifest bytes |
| `capability_digest` | SHA-256 of the raw bearer capability |
| `capability_state` | `live`, `consumed`, or `revoked` |
| `capability_epoch` | monotonic capability generation, initially `1` |
| `lifecycle_state` | state from the workspace lifecycle table |
| `lifecycle_version` | monotonic compare-and-swap version |
| `staging_disposition` | `pending`, `published`, or `discarded` |

The satellite may contain non-authoritative provenance sufficient to identify the main tree
and run, but it cannot mint or replace authorization. Machine paths are runtime metadata and
MUST NOT be added to `.agents/artifacts.yml`.

`provenance.json` fields `capability_digest`, `capability_state`, and `capability_epoch`
jointly form the canonical capability representation; `capability_digest` is the single
canonical capability authority. There is no second digest file or satellite-side authority.
Integrity and concurrency are checked together: while holding `lifecycle.lock`,
authorization reads the capability representation, `lifecycle_state`, and
`lifecycle_version` from the same locked provenance snapshot. Any operation that both
authorizes and changes state MUST require the capability digest match and lifecycle
compare-and-swap against that snapshot; either failure changes nothing.

Process ownership is the pair (`owner_pid`, `owner_pid_start_time`), not the PID alone.
Reconciliation considers an owner live only when both `owner_pid` and
`owner_pid_start_time` match the operating system's current process identity. This makes the
check safe against PID reuse.

### Capability channel and write authorization

The orchestrator generates a cryptographically random, run-scoped capability. Its digest is
authoritative in main runtime. The raw value is written only to a satellite runtime file with
mode `0600`; the delegate context references that file by path. The raw capability MUST NOT
appear in prompts, tracked configuration, durable artifacts, logs, manifests, or completion
output.

This bearer protects against a stale independent session. It does not defend against a
malicious process running as the same operating-system account while the capability is live.

A durable satellite write requires all of:

1. a linked-worktree identity matching provenance and not a submodule;
2. a live main-runtime lifecycle record;
3. a capability whose digest matches `capability_digest`;
4. an unconsumed and unrevoked capability;
5. a permitted mergeable destination.

The closed set of lifecycle states permitting a durable satellite write is exactly `active`.
No other lifecycle state, including `created`, `failed_readonly`, or `recovery_required`,
permits a write.

For each durable satellite write, authorization and the durable write commit MUST occur
while holding the same `lifecycle.lock`. After validating the locked provenance snapshot,
the writer MUST write a temporary file, `fsync` it when durability is requested, atomically
rename it to the destination, and only then release the lock. Consequently, revocation
cannot race an authorized write commit: it acquires the same lock before changing capability
state.

A missing, mismatched, consumed, or revoked capability denies the write. Denial identifies
the canonical `main_tree_path` and `run_id`, then gives exactly:
`/claude-skills:artifacts recover --run-id {run_id}`. A capability authorizes satellite
writes only; harvest is a main-tree operation and remains retryable after consumption.
Starting harvest MUST atomically compare-and-swap `capability_state: live` and the expected
`capability_epoch` to `capability_state: consumed` while also applying the lifecycle
state/version CAS under `lifecycle.lock`; mismatch changes nothing. Revocation MUST
atomically compare-and-swap `capability_state: live` and the expected `capability_epoch` to
`capability_state: revoked` under the same lock; an already consumed capability remains
consumed, and mismatch changes nothing. Terminal handling removes or invalidates the raw
capability file. A newly authorized resume increments `capability_epoch`, installs the new
digest, and sets `capability_state` to `live` in one locked provenance update.

### Ingress manifest schema

Ingress copies the pinned plan before delegation and records a canonical JSON manifest. Each
entry contains:

| Field | Constraint |
|---|---|
| `relative_path` | normalized path relative to the canonical store; no traversal |
| `file_type` | `regular` only for importable content |
| `content_hash` | SHA-256 of file bytes |

The manifest object also contains `schema_version`, `run_id`, `created_at`, and sorted
`entries`. Its canonical-byte SHA-256 MUST match `ingress_manifest_digest`.

### Harvest validation and three-way outcomes

Every satellite byte is untrusted even if its writer presented a capability. Harvest sweeps
the whole satellite store and rejects symlinks, traversal, non-regular files, runtime data,
dotfiles, migration/control files, singleton state, raw capability occurrences, and paths
outside the canonical store. It repeats containment and file-type checks immediately before
staging.

For every relative path, let `B`, `M`, and `S` be its ingress-baseline, current-main, and
current-satellite content hashes. `ABSENT` is a first-class value, not a hash or an omitted
row. Classification applies the exceptional absence predicates first, then the ordinary
hash predicates:

- `deletion`: `B != ABSENT` and exactly one of `M` or `S` is `ABSENT`. Retain the
  non-absent version and require judgment; publish nothing.
- `recreation`: `B == ABSENT`, `M != ABSENT`, `S != ABSENT`, and `M != S`. Retain both
  versions and require judgment.
- `unchanged`: `M == B and S == B`. Do not stage.
- `satellite_only_change`: `S != B and M == B`. Stage satellite bytes.
- `main_only_change`: `M != B and S == B`. Retain main bytes.
- `identical_concurrent_change`: `M == S and M != B`. Retain one identical result.
- `conflict`: `B`, `M`, and `S` are pairwise distinct. Retain both current versions and
  publish nothing.

The ordered predicates cover the per-path hash/absence states relevant to transport, but
MUST NOT call the per-path table exhaustive for filesystem intent. In particular, rename
cannot be proven from per-path hashes alone. A deletion paired with a byte-identical creation
at another path is only a `rename_candidate`; retain both paths and require human judgment.
A delete-then-create at the same path is observable as `recreation` only when the ingress
baseline was absent and main and satellite independently created different bytes. Other
history with the same final hashes is intentionally indistinguishable.

Ambiguous outcomes enter `recovery_required`. There is no last-writer-wins behavior.

### Collect, publish, and destination CAS

**Collect** validates content and writes an immutable staging set. For each staged entry it
records `relative_path`, staged `content_hash`, classification, and the **destination hash**
observed in the main tree (`null` when absent). Collection itself never mutates the main
artifact store.

A partial or invalid staging set MUST NOT enter `staged` or use the `discarded` disposition.
Collection failure instead enters `recovery_required`, MUST record failure evidence that
identifies the unvalidated staging set without claiming validation, and MUST preserve the
satellite and staging bytes for recovery. `discarded` certifies only that a complete
validated staging set was deliberately rejected by an authorized human; its discard evidence
records that decision and the validated staging-set digest.

`discard-evidence.json` is a canonical JSON object with these fields:

| Field | Constraint |
|---|---|
| `run_id` | exactly the lifecycle run identifier |
| `staging_manifest_digest` | SHA-256 of the validated staging manifest; required for `discarded` |
| `partial_staging_inventory` | `null` for `discarded`; failure evidence uses this field instead of a digest when validation was incomplete |
| `reason_code` | one of the closed set `REJECTED`, `USER_REJECTED`, `MERGE_REVERTED`, `VERIFICATION_FAILED`, `SUPERSEDED` |
| `actor` | authenticated identity that authorized the discard |
| `discarded_at` | RFC 3339 UTC decision timestamp ending in literal `Z` |
| `preserved_satellite` | boolean; `true` until separate cleanup succeeds |
| `lifecycle_version` | target version of the `discarded` transition |

The writer MUST atomically bind the evidence to the `staged` to `discarded` lifecycle
compare-and-swap under `lifecycle.lock`: it validates the expected state and version, writes
canonical evidence through a temporary file and atomic rename, and commits provenance with
the same target `lifecycle_version` before releasing the lock. A stale comparison changes
neither authoritative provenance nor evidence. Cleanup MUST compare the evidence `run_id`,
staging manifest digest, and `lifecycle_version` with authoritative provenance and staging;
any mismatch enters `recovery_required` and preserves the satellite.

**Publish** is allowed only after the branch merge and post-merge verification succeed.
When the merge is performed as a prospective merge commit (created without advancing main)
and main is advanced via compare-and-swap (`git update-ref` with expected old SHA),
verification of the prospective merge SHA satisfies the post-merge verification requirement
— the CAS guarantees that main HEAD equals the verified SHA after advance.
Under the lifecycle lock, it performs compare-and-swap on the expected prior state and
revalidates every destination hash against the value observed during collection. If any
destination changed, it publishes nothing atomically, enters `recovery_required`, and
retains staging plus both versions. A reverted or failed merge cannot publish completed
progress.

Lifecycle transitions, crash reconciliation, cleanup evidence, and retryable states are
normative in [Workspace Isolation](workspace-isolation.md). On process startup, owned
provenance is reconciled: dead-owner capabilities are revoked and incomplete atomic
transitions are completed or rolled back. Conflict resolution is never automatic.

Cleanup is forbidden until staging is published or deliberately discarded, the capability
is non-live (`consumed` or `revoked`), and state is `cleanup_allowed`. Denied writes,
conflicts, interrupted harvest, and preserved satellites use the single recovery command:
`/claude-skills:artifacts recover --run-id {run_id}`.

## Safety invariants

1. `local` is the only implicit visibility.
2. `shared-private` and `public` require an explicit tracked policy.
3. A local store MUST be ignored by the containing Git repository and MUST NOT contain
   tracked files.
4. Root traversal, absolute roots, symlink roots, unknown schema versions, and policy
   parse failures are blocking errors.
5. If legacy and canonical stores both contain artifacts, writers MUST stop. They do not
   choose one side or create more state.
6. The tracked policy MUST NOT contain credentials, remote URLs, or machine-specific
   absolute paths.

## Initialization

When no legacy artifacts exist, a writer may lazily initialize the safe local policy and
ignored canonical directory. When any legacy `docs/{plans,issues,ideas,handoff,loop,reviews}` root exists,
initialization stops and
directs the operator to migration. This prevents an empty canonical store from splitting
state from an active legacy store.

## Migration

Changes to root, visibility, backend, or sharing scope are migrations, not ordinary
configuration reloads. Migration follows:

1. inventory without writes;
2. classify each entry as `move`, `copy`, `keep`, or `skip`;
3. stop writers;
4. copy to a staging store;
5. verify counts, hashes, and links;
6. atomically activate the new policy/store;
7. retain the source until a separate cleanup decision.

Moving a file out of a public repository does not remove it from Git history, forks, or
caches. Never describe that operation as retroactive secrecy.

## Path resolution

Repository scripts use `skills/shared/scripts/artifact_store.py`. Skill prose should say
"resolve the artifact store using this contract" and link here rather than duplicating
the schema or validation rules.

## Runtime area

Not everything an agent writes is an artifact. Machine-specific control and session state —
the files that coordinate a single host's running processes — are **runtime**, not project
state, and live in a separate tree:

```text
.agents/runtime/
├── polling/   (.STOP, .STOP.hard, .polling-initialized, .last_archive_month, session.json)
└── loop/      (events.jsonl, archives/YYYY-MM.jsonl)
```

Rules for the runtime area:

- **Always machine-local.** Ignored by Git; never shared, never migrated, regardless of `visibility`. Visibility governs artifacts, not runtime.
- **Separate tree from the store.** Excluded from the migration inventory. Legacy files matching runtime patterns (polling kill/session files, loop event log + archives) are tagged `suggested_action: skip` with the fail-closed default `action: review` untouched.
- **Co-located runtime is the one exception.** Runtime files whose semantics are inseparable from an artifact's on-disk layout stay with that artifact — e.g. polling FS adapter's `running/{slug}/.claim` stays under `state_root` (part of the atomic-rename claim design).
- **Not a derived index.** Live state, never regenerated from artifacts.

Polling adapters bind control/session files to a `<runtime_root>` (see `polling-pattern.md` §Roots). Loop event log path is defined by `measurement-identity.md`.

## Ephemeral area

Intermediate files a skill writes while working — scratch JSON, a batch's working
directory, a report it is about to summarize and discard — are **ephemeral**. They are
neither project state nor process control, and they live in a third tree:

```text
.agents/tmp/
```

Rules for the ephemeral area:

- **Always machine-local.** Ignored by Git; never shared, never migrated, regardless of
  `visibility`. Visibility governs artifacts, not scratch.
- **Excluded from the migration inventory**, on the same footing as the runtime area.
- **Losable by definition.** Unlike an artifact, an ephemeral file may vanish at any time
  and nothing is expected to restore it. A skill that cannot survive its scratch
  disappearing is holding project state in the wrong tree.
- **Not a derived index.** A derived index is regenerated on demand from artifacts;
  ephemeral output is simply discarded.

The distinction that matters is **who is expected to read it later**. An artifact is read
by a future session, a reviewer, or another skill. A runtime file is read by a concurrent
process on this host. An ephemeral file is read by the step that is running right now, and
by nothing after it.

## Configuration area

Skill-facing configuration and accepted baselines are **tracked project state**, and they
are the one tree here that is deliberately committed:

```text
.agents/config/
├── review-rules.md
├── context-audit-baseline.json
├── loop-baseline.json
└── skill-interface-audit-baseline.json
```

Rules for the configuration area:

- **Tracked, not ignored.** These files are committed and shared. A baseline records which
  findings a team has already accepted; if it did not travel with the clone, every fresh
  checkout would re-report findings the team already ruled on.
- **Flat layout.** One file per concern, named after the skill or the concern it serves. No
  per-skill subdirectories — the set is small and a nesting rule would be a second thing to
  keep in sync.
- **Distinct from the store policy.** `.agents/artifacts.yml` declares *where and how the
  store itself lives*, and changing it is a migration governed by the seven steps above.
  `.agents/config/` holds ordinary settings that skills read; changing one is a normal edit
  with no migration discipline attached. Do not merge the two: putting a routine toggle
  under migration discipline either burdens the toggle or erodes the discipline.
- **Never holds secrets.** Same prohibition as the tracked policy (safety invariant 6):
  no credentials, no remote URLs, no machine-specific absolute paths.

## Derived indexes

`ideas/idea-status.md` and `issues/issue-status.md` are **derived caches**, not
authoritative state. Each is a pure function of the top-level entry files in its kind
directory and can be regenerated at any time:

```bash
python3 skills/shared/scripts/artifact_store.py rebuild-index --kind ideas
python3 skills/shared/scripts/artifact_store.py rebuild-index --kind issues
```

Rules for a derived index:

- **Regenerate, never merge.** On any inconsistency between an index and the entries it
  summarizes, the entries win: rebuild the index from scratch rather than hand-reconciling
  rows. Two rebuilds over identical entries produce byte-identical output (the timestamp
  in the index is derived from the newest entry, not from wall-clock time).
- **Top-level entries only.** Index covers flat `*.md` entry files directly under the kind directory. **Every** subdirectory is excluded — `archives/` (and for issues, `done/` / `failed/`) hold resolved/retired entries, and queue-state directories (`ready/` / `running/`) are owned by the queue's state machine.
- **Per-kind schema.** The ideas index is `Idea | Tags | Created | Status | Summary`; the
  issues index is `Issue | Tags | Created | Summary` (no Status column). Ideas entries carry
  their fields as bold labels (`**Created:**` / `**Status:**` / `**Tags:**`) under a `#`
  title with a `## Summary` body; issues entries carry them in YAML frontmatter
  (`title` / `status` / `created` / `tags` / `source`) with a `## Overview` body. The frontmatter
  is read with the repository's minimal flat-scalar parser — no external YAML engine is
  introduced, so an entry file can never trigger arbitrary YAML execution.
- **Entry text is escaped, never trusted for structure.** Pipes and newlines from an entry
  body are escaped/collapsed so a single entry cannot break the table's rows or columns.
- **Fail-closed.** Regeneration writes only when the store is writable. In a `legacy` or
  `split-brain` state it refuses and writes nothing, so it never resurrects an index in a
  broken store. Because it is an explicit, on-demand command (never run by an unattended
  loop) it does not race the polling adapter that also reads `issue-status.md`; do not run
  the two concurrently.

`status.md` and `session-history.md` are **not** derived indexes: they hold session state
that cannot be reconstructed from entries, so they are never targets of regeneration.

## Quality gates

A `local` (or `shared-private`) store is ignored by the containing repository, so its
contents never travel with a clone, a pull request, or a Continuous Integration checkout.
This is a deliberate consequence of safety invariant 3, not an oversight:

- **Store-content checks run in the writer's environment.** Any gate that inspects the
  bytes of an artifact — dossier lint, index consistency, migration state — is only
  meaningful where the store physically exists. Run these in the environment that produced
  the artifacts (for example a pre-push hook, or an operator running the validator
  locally), where the ignored directory is present.
- **Continuous Integration is structurally blind to a local store.** On a fresh checkout the ignored directory is empty; store-content checks pass as no-op. The gate that matters is pre-push (writer) side.
- **A `public` store is the only visibility whose contents are gated by Continuous
  Integration**, because a public store is tracked and therefore present on checkout. When
  a repository needs Continuous-Integration-visible artifact checks, it must opt into
  `public` visibility with an explicit tracked policy.

This split is intentional: the writer environment owns content correctness; the tracked
policy (`.agents/artifacts.yml`) and Git-safety invariants are what Continuous Integration
can and does verify on every checkout regardless of store contents.
