# Artifact Store — Consumer Contract

This is the consumer view of the [Agent Artifact Store contract](artifact-store.md): everything
a skill needs to read and write artifact paths safely. The full contract remains canonical —
on any conflict, [artifact-store.md](artifact-store.md) wins. Read the full contract only when
you orchestrate satellite worktree runs (ingress / capability / harvest / publish), migrate or
recover a store — consumer skills never need those sections.

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

The namespace is provider-independent: no model, vendor, or agent names in paths. Missing
policy resolves to the v1 defaults (`root: .agents/artifacts`, `visibility: local`,
`worktree_scope: worktree`). Invalid or unknown policy values never fall back to a more
public location.

## Safety invariants (consumer-relevant)

1. `local` is the only implicit visibility; `shared-private` and `public` require an
   explicit tracked policy.
2. A local store is ignored by the containing Git repository and never contains tracked
   files.
3. Root traversal, absolute roots, symlink roots, unknown schema versions, and policy
   parse failures are blocking errors.
4. If legacy (`docs/{plans,issues,...}`) and canonical stores both contain artifacts,
   writers stop. They do not choose one side or create more state.
5. The tracked policy never contains credentials, remote URLs, or machine-specific
   absolute paths.

## Initialization

When no legacy artifacts exist, a writer may lazily initialize the safe local policy and
the ignored canonical directory. When any legacy `docs/` artifact root exists,
initialization stops and directs the operator to migration (a full-contract operation).

## The three sibling trees

Not everything an agent writes is an artifact. What distinguishes them is **who is expected
to read it later**:

| Tree | Read later by | Examples |
|---|---|---|
| `.agents/artifacts/` | a future session, a reviewer, another skill | plans, issues, reviews |
| `.agents/runtime/` | a concurrent process on this host | kill files, locks, event logs |
| `.agents/tmp/` | only the step running right now | scratch JSON, working dirs |
| `.agents/config/` | skills, on every run (tracked, committed) | review-rules.md, baselines |

`runtime/` and `tmp/` are always machine-local, Git-ignored, and excluded from sharing and
migration. `config/` is the one deliberately committed tree: flat layout, one file per
concern, never secrets.

## Derived indexes

`ideas/idea-status.md` and `issues/issue-status.md` are regenerable caches, not
authoritative state. On any inconsistency the entry files win — rebuild with
`python3 skills/shared/scripts/artifact_store.py rebuild-index --kind <kind>`, never
hand-reconcile. `status.md` and `session-history.md` are session state, not indexes.

## Path resolution

Repository scripts use `skills/shared/scripts/artifact_store.py`. Skill prose should say
"resolve the artifact store using this contract" and link here rather than duplicating the
schema or validation rules.
