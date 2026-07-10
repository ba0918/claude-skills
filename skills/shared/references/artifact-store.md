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
