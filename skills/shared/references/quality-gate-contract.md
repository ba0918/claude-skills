# Quality Gate Contract — Canonical Guarantee Conditions

The canonical source for the quality gate: the platform-independent guarantee conditions that
govern when a change may enter a protected state (typically "publishable"). This file is the
top layer of a 3-layer architecture:

```
Canonical   — this file. Guarantee conditions as properties (platform-independent)
Enforcement — adapters that mechanically judge evidence (hosted CI + branch protection, ...)
Recall      — adapters that surface obligations at the right moment (context injection, ...)
```

Enforcement and recall implementations are deliberately absent from this file (§7). The
conformance-profile layer and the evidence-format verifier plug into §6 and §2 respectively;
both ship separately.

## The Core Property

```
No state transition into a protected state takes effect without valid
verification evidence bound to the exact version of the target.
```

Everything below refines this single property: what "verification" splits into (§1), what
makes evidence "valid" and when it stops being valid (§2), what makes a review independent
(§3), which obligations the evidence must cover (§4), and when the gate may declare
convergence (§5). Which states are protected is declared by the conformance profile (§6);
`publishable` is the canonical example.

## 1. Verification State Machine

```
machine_verified  ⊥  semantic_reviewed
        \             /
         → publishable   (risk class decides which are required; the default is both)
```

- **`machine_verified`** — every mechanical gate passed on the exact target version.
  Machine gates verify that the change does not violate **expectations that were written
  down in advance** (tests, lint, schema checks, repository validators).
- **`semantic_reviewed`** — a review conforming to §4 completed and converged per §5.
  Semantic review exists for **expectations nobody wrote down**: specification gaps,
  missing tests, unintended impact. The boundary between the two states is the boundary
  of what is mechanically verifiable; neither state substitutes for the other.
- The two states are orthogonal: neither implies, contains, nor refreshes the other.
  `publishable` requires the conjunction demanded by the applicable risk class; a profile
  may require both for everything (the conservative default) but may never require less
  than the generic contract does.
- What a semantic review guarantees is **that the review contract was executed and every
  finding dispositioned** — not that the reviewer's conclusions are correct. Correctness
  claims stay with the evidence; see [verification-gate.md](verification-gate.md) for the
  behavioral rule that no completion claim may outrun its evidence.

## 2. Evidence Validity

Evidence is a record asserting that a gate held for a target. Its validity is defined by
binding, not by trust in whoever produced it:

- **Binding**: every piece of evidence binds to `(target version identifier × verification
  contract version)`. Evidence that does not name the exact target version and the version
  of the contract it verified against is not evidence. (Binding additionally to an input
  manifest hash is a v2 extension — out of scope here.)
- **Invalidation is part of the contract.** Universal invalidation rules:
  - New commits on top of a reviewed version invalidate that review's evidence for the new
    version. Evidence never transfers forward along history.
  - A change to the verification contract version invalidates evidence produced under the
    older contract, for the states that contract governs.
  - Expired evidence is treated identically to absent evidence — the §Core Property blocks
    the transition.
- Re-verification after invalidation may be scoped (what changed decides what re-runs),
  but the scoping rules belong to the conformance profile; the generic contract only fixes
  the invariant that *some* valid evidence must exist per required state.

## 3. Independence of Review

"Independent review" decomposes into four separate properties. Declare which ones a given
review run actually had; none of them implies the others:

| Property | Meaning |
|---|---|
| history-free | The reviewer saw none of the previous review's conclusions |
| evidence-regenerating | The reviewer re-derived evidence instead of reusing recorded evidence |
| strategy-diverse | The review used a different strategy than the prior pass (e.g. refutation-oriented) |
| reviewer-heterogeneous | The review was performed by a different kind of reviewer |

History-freedom alone is **not** sufficient for independence. Risk classes that demand
independent confirmation say *which* of these properties they require; the convergence
condition (§5) requires at least one history-free pass.

## 4. Review Obligations (profile-derived)

Obligations are not a fixed checklist. They are derived: always-on invariants, plus
obligations triggered by the kind of change under review, recorded in an evidence ledger.

### 4.1 Always-on invariants

Evaluated for every change, whatever its kind:

1. **Traceability to requirements and contracts** — the change is consistent with its
   declared purpose, the shared contracts it claims to follow, and the documents it links.
2. **Portable executability** — what the change describes can be executed as written,
   without unstated environmental assumptions.
3. **Completeness of the impacted set** — every consumer, caller, and sibling path affected
   by the change is updated; same-kind paths do not end up with asymmetric guarantees.
4. **Sufficiency of verification evidence** — the verification accompanying the change can
   actually detect the failures the change could introduce.

Calibration is deliberately moderate: the invariants name *what must hold*, never *how to
detect violations* — detection procedure is reviewer competence, and prescribing it adds
no measured detection power. The exception that earns its place: invariant 3 is the one
dimension where contract-driven review showed a measured detection advantage over
uninstructed review (issue #142, measured 2026-07-28). Profiles must not weaken it.

### 4.2 Change-kind trigger table

The kind of change fires additional obligations. The generic contract fixes the mechanism
and reserves one row; profiles supply the concrete table for their domain. Illustrative
rows:

| Change kind | Additional obligations fired |
|---|---|
| Agent-instruction document added/changed | trigger conditions; state transitions and loop termination; fallback paths carry the same guarantees as main paths; consistency with shared contracts |
| Executable script added/changed | input ranges and defaults; boundary conditions; false-positive/false-negative paths; symmetry of checking rules across functions in the same file |
| Shared contract changed | every consumer re-checked; compatibility of vocabulary and semantics |
| **Outside static semantic review** (reserved row) | Defect classes that only manifest under operational measurement — e.g. a fail-safe whose over-application only shows when the environment lacks the data it assumes — are **not** review obligations. They belong to machine gates and operational sensors. A profile must route them there explicitly rather than let the review promise what static reading cannot deliver (measured: 4/4 review conditions missed such a defect, issue #142). |

### 4.3 Evidence ledger

Each fired obligation produces one ledger entry: target / verification predicate / coverage
state / grounds / findings. Vocabulary is reused, not redefined:

- Coverage states (`reviewed` / `skipped` / `unsupported` / `inconclusive`) per
  [coverage-ledger.md](coverage-ledger.md), including its Iron Law: no "no problems"
  without a non-empty evaluated scope, and no silently dropped areas.
- Finding severity (BLOCK / WARN / INFO) and the three-valued verification of individual
  findings (CONFIRMED / FALSE_POSITIVE / UNCERTAIN) per
  [severity-and-verdicts.md](severity-and-verdicts.md). Schemes using other severity scales
  must map onto these consistently, the same way that file admits approved dialects.

The ledger is what makes §5 mechanically decidable — it is the review's output format, not
an optional appendix.

## 5. Convergence Conditions

Convergence is a state, not a feeling of having iterated enough. The gate converges when
**all** of the following hold:

1. Every obligation fired for this change (§4) has been evaluated — its ledger entry exists
   and names a coverage state.
2. No blocking-severity finding verified as CONFIRMED remains undispositioned.
3. Every finding is dispositioned as one of:
   - **FIXED**,
   - **WONT_FIX** with a typed reason — one of: preference difference / outside the
     contract / fix risk exceeds benefit / duplicate,
   - **ACCEPTED_RISK** (an explicitly recorded acceptance).
4. At least one history-free (§3) review pass completed without new blocking findings.

Non-convergence rules:

- Blocking-severity findings left UNCERTAIN, and areas left `inconclusive`, never converge
  silently — they either get resolved or escalate to a human.
- **Oscillation** — a fix followed by a finding pushing in the opposite direction — escalates
  to a human immediately.
- An iteration cap is a **detector of undecidability, not a quality condition**. Reaching it
  does not mean "good enough"; it transitions the change to *explicit human decision
  required*.

## 6. Three Layers of Configuration

```
Generic contract (this file)     — properties that hold everywhere. Never weakened.
Conformance profile (per domain) — minimum evidence, mandatory obligations, and the
                                   no-weakening list for one domain. May only add to or
                                   tighten the generic contract.
Local settings (per project)     — may only add to or tighten the profile.
```

A two-layer design (generic + local) was rejected: it lets a local setting weaken mandatory
conditions. The profile layer exists precisely to hold the line that must not move. The
first conformance profile (for natural-language skill repositories) ships as a separate
file; this repository is one conformance sample of that profile, not the normative
reference.

## 7. Enforcement and Recall Are Adapters

The canonical layer states *conditions*, never *firing points*:

- Pre-condition: the knowledge a task needs is reachable when work starts.
- Post-condition: no transition to a protected state without valid evidence (§Core).

Anything that makes those conditions hold in a specific environment is an adapter. A hosted
CI pipeline combined with branch protection is an enforcement adapter for repository-hosted
development. A local pre-push hook is an **early-feedback layer, not enforcement** — it can
be bypassed or simply not installed, so no guarantee may rest on it. Session-start context
injection is a recall adapter. Adapters are replaceable per environment; the conditions are
not. Conformance of an environment is judged against the conditions, which is how lock-in
to any single platform is avoided.

## 8. v1 Scope Boundary

Deferred to v2 (deliberately, until a second consumer exists): input manifest hashes in
evidence binding, structured per-dimension grounds inspection, risk tiering beyond the
default "both states required", conformance scenario tests, and a second conformance
profile. The v1 companion pieces — the evidence-format verifier for the
`verified(target SHA, contract version) → publishable` slice (§2), the skill-repository
conformance profile (§6), and recall adapters (§7) — ship as separate changes and must not
relax anything written here.
