# Agent Artifact Store Contract

Agent-generated working artifacts are project state, not reader-facing documentation. All
skills that create or consume plans, issues, ideas, or loop state MUST resolve their paths
through this contract instead of embedding a `docs/` path.

## Canonical namespace

The repository policy lives at `.agents/artifacts.yml`. The default logical store is:

```text
.agents/artifacts/
├── plans/
├── issues/
├── ideas/
└── loop/
```

The namespace is provider-independent. Do not add model, vendor, or agent names to the
path. Format differences belong in artifact schema metadata.

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
ignored canonical directory. When any legacy `docs/{plans,issues,ideas,loop}` root exists,
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

- **Always machine-local.** `.agents/runtime/` is always ignored by Git and is **never
  shared and never migrated, regardless of the store's `visibility`.** Even a `public`
  store keeps its runtime tree local — visibility governs artifacts, not runtime.
- **Separate tree from the store.** Runtime lives beside `.agents/artifacts/`, not inside
  it, so it is excluded from the migration inventory. When the migration inventory
  encounters a legacy file that matches a runtime pattern (polling kill/session files, the
  loop event log and its monthly archives), it tags the entry `suggested_action: skip`
  while leaving the fail-closed default `action: review` untouched.
- **Co-located runtime is the one exception.** A runtime file whose semantics are
  inseparable from an artifact's on-disk layout stays with that artifact. The polling FS
  adapter's `running/{slug}/.claim` is part of the atomic-rename claim design and therefore
  stays under the queue body (`state_root`), not in `.agents/runtime/`.
- **Not a derived index.** Runtime files are live state, never regenerated from artifacts.

Polling adapters bind their control/session files to a `<runtime_root>`; see the "Roots"
section of `polling-pattern.md`. The loop event log path is defined by
`measurement-identity.md`. (Those files link here; this contract stays a closure leaf so
that referencing the artifact store never drags polling internals into a skill's behavior
surface.)

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
- **Top-level entries only.** The index covers the flat `*.md` entry files directly under
  the kind directory. **Every** subdirectory is excluded — `archives/` (and, for issues,
  `done/` and `failed/`) because they hold resolved or retired entries, but also
  queue-state directories such as `ready/` and `running/`: an issue inside the polling
  queue is owned by the queue's state machine, not by this index. Regenerating an index
  that was previously hand-maintained may therefore drop rows that pointed at entries in
  subdirectories — that is the intended correction, not data loss.
- **Per-kind schema.** The ideas index is `Idea | Tags | Created | Status | Summary`; the
  issues index is `Issue | Tags | Created | Summary` (no Status column). Ideas entries carry
  their fields as bold labels (`**Created:**` / `**Status:**` / `**Tags:**`) under a `#`
  title with a `## Summary` body; issues entries carry them in YAML frontmatter
  (`title` / `status` / `created` / `tags` / `source`) with a `## 概要` body. The frontmatter
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
- **Continuous Integration is structurally blind to a local store.** On a fresh checkout
  the ignored directory is empty, so store-content checks find nothing to inspect and pass
  as a no-op. Do not read a green Continuous Integration run as evidence that the store's
  contents were validated. The gate that matters is the pre-push (writer) side.
- **A `public` store is the only visibility whose contents are gated by Continuous
  Integration**, because a public store is tracked and therefore present on checkout. When
  a repository needs Continuous-Integration-visible artifact checks, it must opt into
  `public` visibility with an explicit tracked policy.

This split is intentional: the writer environment owns content correctness; the tracked
policy (`.agents/artifacts.yml`) and Git-safety invariants are what Continuous Integration
can and does verify on every checkout regardless of store contents.
