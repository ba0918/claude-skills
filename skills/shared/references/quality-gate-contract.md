# Quality Gate Contract — Canonical Verification Obligations

The canonical source for the quality gate: the platform-independent obligations that
govern when a change may be declared verified. This contract defines **what verification
means**, not how it is recorded. In particular it defines the review obligations that
apply to a change, when a review may be declared converged, and the vocabulary those
judgments use.

Evidence ledgering — binding a verification record to a target SHA and mechanically
inspecting it at publish time — was dismantled in #308. What survives here is the
**definition of verification** that review skills and workflows execute:
[review obligations](#4-review-obligations-derived-from-change-kind), [convergence
conditions](#5-convergence-conditions), the [review output ledger](#43-review-output-ledger),
[independence of review](#3-independence-of-review), and the shared vocabulary. The rule
that no completion claim may outrun its evidence is unchanged; see
[verification-gate.md](verification-gate.md).

## The Core Obligation

```
No verification claim (PASS / CONVERGED / verified) is made without the
review obligations that apply to the change having been executed and disposed.
```

Everything below refines this single obligation: what "review" splits into (§3), which
obligations a review must cover (§4), how obligations fire from the kind of change (§4.2),
and when a review may declare convergence (§5).

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

## 4. Review Obligations (derived from change kind)

Obligations are not a fixed checklist. They are derived: always-on invariants, plus
obligations triggered by the kind of change under review, recorded in a review ledger.

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
uninstructed review (issue #142, measured 2026-07-28). The trigger table (§4.2) must not weaken it.

### 4.2 Change-kind trigger table

The kind of change fires additional obligations. For this repository (a natural-language
skill repository whose primary artifacts are agent-instruction documents), the concrete
table is:

| Change kind | Additional obligations fired |
|---|---|
| Skill instruction document added/changed | Trigger conditions are decidable and non-colliding; every described workflow terminates (loops carry caps or convergence conditions); fallback and edge-case paths carry the same guarantees as the main path; the document is consistent with every shared contract it links |
| Shared contract added/changed | Every consumer of the contract re-checked against the new text; vocabulary and semantics stay compatible, or every consumer is migrated in the same change |
| Validator or executable script added/changed | Input ranges and defaults; boundary conditions; false-positive and false-negative paths (including the empty-scan case: zero targets must be distinguishable from zero findings); symmetry of checking rules across functions in the same file |
| Thin command wrapper added/changed | The wrapper stays thin: dispatch only, no obligations or contract content of its own (name-to-skill correspondence is a machine-gate concern, not re-reviewed here) |
| Distribution manifest or install path changed | The change reaches every distribution channel the repository declares; partial-channel updates are treated as incomplete |
| **Outside static semantic review** (reserved row) | Defect classes that only manifest under operational measurement — e.g. whether a skill's trigger description actually fires in live sessions — are **not** review obligations. They belong to machine gates and operational sensors. The trigger table must route them there explicitly rather than let the review promise what static reading cannot deliver (measured: 4/4 review conditions missed such a defect, issue #142). |

A change may fire several rows at once; each fired row produces its own ledger entries.
Obligations the repository's mechanical validators already enforce (link resolution,
schema and frontmatter shape, name coverage in indexes, vocabulary-linkage rules,
translation parity, and whatever else the canonical verification entry point checks) are
**removed from the fired semantic obligation set**: they produce no semantic ledger
entries, in any coverage state. When a reviewer doubts a machine gate's coverage, the
finding is a defect report against the validator, not a manual re-check.

### 4.3 Review output ledger

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
an optional appendix. A review without a ledger is not a verification claim, whatever its
conclusions.

## 5. Convergence Conditions

Convergence is a state, not a feeling of having iterated enough. The gate converges when
**all** of the following hold:

1. Every obligation fired for this change (§4) has a ledger entry, and every **mandatory**
   obligation — the always-on invariants, plus whatever the trigger table (§4.2) marks
   mandatory — reached coverage state `reviewed`. A mandatory obligation left `skipped`, `unsupported`,
   or `inconclusive` blocks convergence, unless a human records an explicit waiver naming
   the obligation and the reason. A ledger entry's mere existence never counts as
   evaluation.
2. No blocking-severity finding verified as CONFIRMED remains undispositioned.
3. Every finding is dispositioned **according to its verification value** (the three-valued
   judgment of [severity-and-verdicts.md](severity-and-verdicts.md)):
   - **CONFIRMED** → one of **FIXED**, **WONT_FIX** with a typed reason (preference
     difference / outside the contract / fix risk exceeds benefit / duplicate), or
     **ACCEPTED_RISK** (an explicitly recorded acceptance);
   - **FALSE_POSITIVE** → a recorded dismissal with the reason it does not apply;
   - **UNCERTAIN** → stays report-only, never marked fixed or accepted. Blocking-severity
     UNCERTAIN blocks convergence until a recorded adjudication resolves it to CONFIRMED
     or FALSE_POSITIVE and the corresponding disposition is applied. Escalation is **not**
     an alternative to resolution: escalating transitions the change to the non-converged
     *explicit human decision required* state, and only the human's recorded adjudication
     re-opens the path to convergence. Non-blocking UNCERTAIN is recorded as-is and does
     not block.
4. At least one history-free (§3) review pass completed without new blocking findings.

Non-convergence rules:

- Blocking-severity findings left UNCERTAIN, and mandatory-obligation areas left
  `inconclusive`, never converge silently. Escalating them to a human is a transition to
  *explicit human decision required* — a non-converged state — never a substitute for
  resolution; convergence resumes only from the human's recorded adjudication.
- **Oscillation** — a fix followed by a finding pushing in the opposite direction — escalates
  to a human immediately.
- An iteration cap is a **detector of undecidability, not a quality condition**. Reaching it
  does not mean "good enough"; it transitions the change to *explicit human decision
  required*.
