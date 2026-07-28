# Skill-Repository Conformance Profile

The first conformance profile for [quality-gate-contract.md](quality-gate-contract.md) §6:
the middle layer that fixes, for one domain, the minimum evidence, the mandatory
obligations, and the list of conditions no local setting may weaken. This profile covers
**natural-language skill repositories** — repositories whose primary artifacts are
agent-instruction documents (skill files and their references), shared natural-language
contracts, and the mechanical validators that keep them consistent.

This repository is **one conformance sample** of the profile, not its normative reference.
The profile is written so that a different skill repository, with different validators and
different file layout, can conform without reading this repository.

## Profile Identity

Machine-readable identifier: **`skill-repository-profile 1.0.0`**, conforming to
`quality-gate-contract 1.0.0`. The version rules of the canonical contract's
§Contract Identity apply unchanged: semantic changes bump the version, editorial changes do
not, and versions identify **published** states only.

**This profile is published but not yet in force** (the same distinction
[evidence-format.md](evidence-format.md) draws: a profile document may ship as a forward
declaration while no profile is in force). "In force" means a profile *applies*
in the sense of contract §2, which then requires every piece of evidence to bind to the
profile's version — and the v1 verifier of [evidence-format.md](evidence-format.md)
deliberately rejects any non-null `profile` field. Requiring this profile's obligations
while its binding is unrecordable would make valid evidence impossible, so the two are
coupled: this profile **takes force only when a profile-aware verifier ships** (contract
§8). Until that moment, no change is judged against this profile; evidence keeps
`profile: null` and binds to the generic contract alone, and reviews may use this file as
forward guidance without recording profile conformance. This paragraph is the
non-contradiction rule, not a loophole — a repository claiming conformance to this profile
before it is in force is making an unverifiable claim.

## Domain Characteristics

In a natural-language skill repository, the mechanically verifiable surface is structural:
links resolve, schemas hold, names correspond, vocabularies stay consistent. What the
instructions *mean* — whether a workflow terminates, whether a fallback path silently loses
a guarantee the main path has, whether two contracts contradict — lives almost entirely in
the expectations nobody wrote down as checks. The weight of assurance in this domain
therefore sits on the `semantic_reviewed` side of the contract's §1 state machine. This is
a domain property and belongs here, not in the generic contract: other domains (a typed
service with an exhaustive test suite) distribute the weight differently.

## Minimum Evidence

The generic v1 minimum is normative and unchanged: a protected-state transition requires
**both** `machine_verified` and `semantic_reviewed` (contract §1). For this domain, the
profile fixes what each state minimally means:

- **`machine_verified`** — the repository's canonical verification entry point (the single
  script or pipeline the repository declares as its verification source of truth) passed
  against the exact target version. Running a subset of checks, or running them against a
  different commit, does not produce this state.
- **`semantic_reviewed`** — a review that executed the obligations of this profile (below)
  and converged per contract §5, with the evidence ledger of contract §4.3 as its output.
  A review without a ledger is not evidence, whatever its conclusions.

## Mandatory Obligations

### Always-on invariants

The four always-on invariants of contract §4.1 are mandatory in full. Invariant 3
(completeness of the impacted set) **must not be weakened by any local setting**: it is the
one dimension where contract-driven review showed a measured detection advantage over
uninstructed review (issue #142, measured 2026-07-28), and in this domain its typical
failure mode — a sibling path or a consumer of a shared contract left with asymmetric
guarantees — is exactly the defect class mechanical validators cannot see.

### Change-kind trigger table

Concrete table for this domain, per the mechanism of contract §4.2. A change may fire
several rows at once; each fired row produces its own ledger entries.

| Change kind | Additional obligations fired |
|---|---|
| Skill instruction document added/changed | Trigger conditions are decidable and non-colliding; every described workflow terminates (loops carry caps or convergence conditions); fallback and edge-case paths carry the same guarantees as the main path; the document is consistent with every shared contract it links |
| Shared contract added/changed | Every consumer of the contract re-checked against the new text; vocabulary and semantics stay compatible, or every consumer is migrated in the same change |
| Validator or executable script added/changed | Input ranges and defaults; boundary conditions; false-positive and false-negative paths (including the empty-scan case: zero targets must be distinguishable from zero findings); symmetry of checking rules across functions in the same file |
| Thin command wrapper added/changed | The wrapper stays thin: dispatch only, no obligations or contract content of its own (name-to-skill correspondence is a machine-gate concern, not re-reviewed here) |
| Distribution manifest or install path changed | The change reaches every distribution channel the repository declares; partial-channel updates are treated as incomplete |

### Machine-covered obligations are not re-reviewed

Obligations the repository's mechanical validators already enforce — link resolution,
schema and frontmatter shape, name coverage in indexes, vocabulary-linkage rules,
translation parity, anchor resolution, and whatever else the canonical verification entry
point checks — belong to `machine_verified` and are **removed from the fired semantic
obligation set before the ledger is written**: they produce no semantic ledger entries at
all, in any coverage state. (The four coverage states of
[coverage-ledger.md](coverage-ledger.md) describe semantic evaluation scope; machine-gate
results live in `machine_verified` evidence, not in the semantic ledger.) The trigger
table above names only predicates the machine gates do not prove. Double-counting produces
ritual review and hides where judgment was actually spent. When a reviewer doubts a
machine gate's coverage, the finding is a defect report against the validator (a
"Validator changed" row concern), not a manual re-check.

### Outside static semantic review

The reserved row of contract §4.2 applies with a domain-concrete example: **whether a
skill's trigger description actually fires in live sessions** — its firing rate and
adoption rate — only manifests under operational measurement. A static reading can judge
the description's consistency, not its salience in real routing. Reviews must not carry
this obligation; it routes to trigger-accuracy measurement tooling and operational sensors,
recorded in the ledger as `unsupported` with that routing named (vocabulary per
[coverage-ledger.md](coverage-ledger.md)). The same routing applies to any defect class
that only manifests under operational data the review cannot observe (measured: 4/4 review
conditions missed such a defect, issue #142).

## No-Weakening List

Conditions no local setting built on this profile may relax (contract §6 gives local
settings add-or-tighten rights only):

1. The v1 conjunction: both `machine_verified` and `semantic_reviewed`, unconditionally
   (contract §1).
2. Always-on invariant 3, completeness of the impacted set (§ above).
3. The evidence ledger as mandatory review output, including the Iron Law of
   [coverage-ledger.md](coverage-ledger.md) — no "no problems" claim without a non-empty
   evaluated scope, no silently dropped areas.
4. The disposition rules for findings of contract §5.3 — in particular that UNCERTAIN
   findings (vocabulary per [severity-and-verdicts.md](severity-and-verdicts.md)) stay
   report-only and blocking-severity UNCERTAIN blocks convergence pending recorded
   adjudication.
5. Evidence binding and invalidation per contract §2: total invalidation on new commits,
   no forward transfer of evidence, expired treated as absent.

## Local Settings

A repository adopting this profile may, in its own configuration: add change-kind rows,
mark additional obligations mandatory, tighten iteration caps or severity thresholds, and
require more independence properties (contract §3) for chosen risk classes. It may not
remove rows, downgrade mandatory obligations, or grant itself exceptions to the
no-weakening list. A second conformance profile for a different domain is deliberately
deferred until a second implementation exists (contract §8).
