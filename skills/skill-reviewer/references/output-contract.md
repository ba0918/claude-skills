# skill-reviewer Output Contract

The canonical definition of what skill-reviewer emits. The shape is machine-checked by
[scripts/validate_review_output.py](../scripts/validate_review_output.py) — a review whose output does not pass it
has not been produced.

The severity words are those of
[severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md) (including its evidence-qualified
BLOCK dialect); `AUTO_FIX` / `NEEDS_JUDGMENT` / `REPORT_ONLY` are those of
[fix-action-taxonomy.md](../../shared/references/fix-action-taxonomy.md); the coverage values are those of
[coverage-ledger.md](../../shared/references/coverage-ledger.md).

## The two channels

The output separates findings into two channels, and only the first one is something a consumer may act on.

| Channel | Verdicts it may hold | What a consumer may do with it |
|---------|---------------------|-------------------------------|
| `control_candidates` | BLOCK, WARN | BLOCK may drive a fix loop. WARN is recorded and execution continues. Automatic fixing happens only where `fix_action: AUTO_FIX` is stated |
| `diagnostics` | WARN, OPPORTUNITY, INFO | Display and record only. It never drives an automatic fix, a re-review, or a stop |

The separation is not an understanding between authors — it is a shape. A BLOCK inside `diagnostics`, an
`AUTO_FIX` inside `diagnostics`, and an OPPORTUNITY inside `control_candidates` are all rejected by the validator,
so the channel a finding sits in cannot be quietly ignored downstream. Deciding to stop or to fix belongs to the
caller; a verdict here is input to that decision, never the decision itself.

## The document

```json
{
  "assurance_role": "diagnostic_only",
  "quality_gate_evidence": false,
  "dynamic_sensors_executed": [],
  "target": "skills/example",
  "summary": "One line on what was reviewed and what came out of it",
  "coverage": [
    { "target": "skills/example/SKILL.md", "value": "reviewed", "reason": "Body checked against every referenced contract" }
  ],
  "evidence": [
    { "skill": "example", "state": "accepted_without_run", "reason": "The ledger records result=accepted-without-run" }
  ],
  "control_candidates": [
    {
      "id": "cc-1",
      "verdict": "BLOCK",
      "target": "skills/example/SKILL.md:12",
      "summary": "The body contradicts the contract it links to",
      "qualification_reason": "validate_repo check 9 already reports a violation on this file",
      "fix_action": "NEEDS_JUDGMENT"
    }
  ],
  "diagnostics": [
    { "id": "dg-1", "verdict": "OPPORTUNITY", "target": "skills/example/SKILL.md", "summary": "…", "detail": "…" }
  ]
}
```

Unknown keys are rejected at every level. A key you believed you declared but that is silently dropped is the
hardest kind of divergence to notice, so a typo fails as a violation.

| Field | Required | Notes |
|-------|----------|-------|
| `assurance_role` / `quality_gate_evidence` / `dynamic_sensors_executed` | ✓ | The non-evidence declaration. Fixed values — see below |
| `coverage[]` | ✓ | Non-empty. `target` / `value` / `reason`, every entry with a reason |
| `evidence[]` | ✓ | May be empty. `skill` / `state` (+ optional `reason`, boolean `run_evidence`, string `surface_sha256` — other types are rejected) |
| `control_candidates[]` / `diagnostics[]` | ✓ | May be empty, but both keys are always present |
| Finding `id` / `target` / `summary` | ✓ | `id` is unique across both channels |
| Finding `fix_action` | Required on every `control_candidates` entry | Optional in `diagnostics`, where the value `AUTO_FIX` is rejected |
| Finding `qualification_reason` | Required on control BLOCK; optional on control WARN | The key itself is rejected in `diagnostics` — it is a statement about BLOCK eligibility |
| `target` / `summary` (top level), finding `detail` | - | Free text for the human reader |

## The non-evidence declaration

Every output carries these three fields at fixed values:

```
assurance_role: diagnostic_only
quality_gate_evidence: false
dynamic_sensors_executed: []
```

[quality-gate-contract.md](../../shared/references/quality-gate-contract.md) states that a review without a ledger
is not evidence. These three fields close, in the shape of the document itself, the path by which a diagnostic
report gets mistaken for quality-gate evidence. A non-empty `dynamic_sensors_executed` is rejected, which is what
makes "this skill does not run LLM sensors" a checkable property rather than a promise.

## What qualifies as BLOCK

A BLOCK must point at **machine evidence that already exists**, and `qualification_reason` names it. Three kinds
qualify:

- a test that fails right now,
- a violation reported by an existing repository validator,
- a contract contradiction refutable from the body text alone (an unconditional loop with no exit condition; a body
  that states the opposite of the contract it links to).

Nothing else qualifies. In particular: a finding that would need a new fixture to demonstrate is not a BLOCK — the
reviewer never acquires an obligation to build fixtures. Prose quality, length, ordering, and wording preferences
are not BLOCK material at any severity of conviction. When the evidence exists but you cannot write down what it
is, the finding is not qualified; demote it.

Where a finding lands, once you know it is real:

| The finding is | Evidence already exists | No such evidence |
|----------------|------------------------|------------------|
| Broad in impact | `control_candidates` BLOCK | `control_candidates` WARN |
| Narrow in impact | `control_candidates` WARN | `diagnostics` WARN / INFO |

## OPPORTUNITY

OPPORTUNITY belongs to `diagnostics` alone. It never gets promoted to WARN automatically, and turning one into an
issue is a human action. State both sides: what improves, and what is risked or spent by acting.

A fixture-capture candidate may be raised as OPPORTUNITY only when all three hold — an observable acceptance
condition exists, a reproducible scenario worth pinning can be named, and the regression value is high. With the
material missing it stays INFO carrying `dynamic coverage: uncovered`. Emitting a capture candidate for every new
skill would make the diagnostic instrument a de facto fixture requirement, which is exactly the obligation this
skill declines to impose.

## Running the validator

```bash
python3 skills/skill-reviewer/scripts/validate_review_output.py <output.json>
```

Exit 0 is conformance, 1 is a contract violation with the reasons printed, 2 means the input could not be read or
parsed. Run it against the output before reporting; a violation means the output is fixed, not that the check is
waived.
