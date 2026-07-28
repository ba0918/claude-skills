# Evidence Format — the verified(target SHA, contract version) slice

The concrete evidence format and verifier for the
[quality-gate-contract.md](quality-gate-contract.md) §2 binding rules. That contract defines
*what makes evidence valid*; this file defines *what a piece of evidence looks like on disk*
and ships the mechanical verifier for the single vertical slice
`verified(target SHA, contract version) → publishable`. Nothing here relaxes the canonical
contract; where the two disagree, the canonical contract wins.

## Evidence record schema (v1)

One JSON file per verification state, named after the state:

```text
<evidence-dir>/
├── machine_verified.json
└── semantic_reviewed.json
```

```json
{
  "schema_version": 1,
  "state": "machine_verified",
  "target_sha": "<full 40-hex commit id of the verified target>",
  "contract": "quality-gate-contract",
  "contract_version": "1.0.0",
  "profile": null,
  "produced_at": "2026-07-28T12:00:00Z",
  "grounds": "free text naming what produced this evidence (command, review run, ledger ref)"
}
```

Field rules:

- `schema_version` MUST be `1`. Unknown versions make the record invalid evidence.
- `state` MUST equal the file's basename (`machine_verified` or `semantic_reviewed`).
  A record cannot testify for a state it does not name.
- `target_sha` MUST be the full 40-hex commit id. Abbreviated ids are invalid evidence:
  binding is to the *exact* target version, and prefix ambiguity breaks exactness.
- `contract` MUST be `quality-gate-contract`; `contract_version` MUST resolve to the
  published version declared in the canonical contract's §Contract Identity. A version
  that does not resolve is invalid evidence (contract §Contract Identity).
- `profile` is `null` until a conformance profile ships; once one applies, it becomes
  `{"name": ..., "version": ...}` and binding extends to the profile version
  (contract §2). The verifier treats a non-null profile as part of the binding.
- `grounds` is required and non-empty: evidence that cannot say what produced it is not
  evidence (the same Iron Law as CONFIRMED in
  [severity-and-verdicts.md](severity-and-verdicts.md)).

## Storage location

Default evidence directory: `evidence/` under the `reviews` kind of the agent artifact
store — `.agents/artifacts/reviews/evidence/` under the v1 defaults of
[artifact-store.md](artifact-store.md). Consequences, stated deliberately:

- The store is Git-ignored (store invariant 3), so evidence never enters the commit it
  binds to. This is required, not incidental: committing evidence would change the SHA it
  testifies about.
- `worktree_scope: worktree` means a fresh worktree starts with no evidence. That is the
  fail-closed default this contract wants: evidence is re-earned per target version
  (contract §2 total invalidation), never inherited through checkout.

## Verifier

`skills/shared/scripts/evidence_check.py` decides the slice mechanically:

```bash
python3 skills/shared/scripts/evidence_check.py \
  [--evidence-dir DIR] [--target-sha SHA] [--contract PATH] [--repo-root DIR]
```

- `--evidence-dir` defaults to the artifact-store resolution above; `--target-sha`
  defaults to the repository's current `HEAD`; `--contract` defaults to the canonical
  contract file in the repository.
- The verifier always prints what it checked (target SHA, published contract version, and
  the per-state judgment) — an empty or missing evidence directory is reported explicitly,
  never passed over.

Exit codes separate judgment from breakage (a vacuous pass is structurally impossible —
absent evidence is a *negative judgment*, not a skip):

| Exit | Meaning |
|---|---|
| 0 | `publishable`: both states hold valid evidence bound to the exact target SHA and the published contract version |
| 1 | Not publishable: at least one state's evidence is absent, expired (SHA mismatch), or invalid (unresolvable version, malformed record). Reasons are printed per state |
| 2 | The check itself could not run: contract file unreadable or its version undeclarable, target SHA unresolvable, evidence dir path invalid |

Per contract §2, expired and invalid evidence are judged identically to absent evidence
(exit 1); exit 2 is reserved for the verifier lacking its own preconditions, so automation
can distinguish "the gate said no" from "the gate could not speak".

## What this slice does not do (v1 boundary)

Consistent with contract §8: no input-manifest hashing, no scoped re-verification (any
invalidation requires full regeneration of that state's evidence), no risk tiering (both
states are always required), and no judgment about *how* the evidence was produced — that
is the province of the conformance profile and the review obligations (contract §4).
