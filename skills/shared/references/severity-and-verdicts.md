# Severity & Verdicts

The severity definitions and verdict criteria used in code review, plus
the three-valued context verification used by find-then-verify skills.
A shared resource referenced by sweep-fix / refactor / iterate / context-audit and others.
Whether a finding's fix can be automated is a separate, orthogonal axis defined by
[fix-action-taxonomy.md](fix-action-taxonomy.md).
A finding's evaluation coverage (what was examined and how far) is likewise a separate, orthogonal axis defined by
[coverage-ledger.md](coverage-ledger.md).

## Severity definitions

| Severity | Meaning | Criteria for choosing it | Examples |
|--------|------|-------------|-----|
| **BLOCK** | Cannot proceed. Continuing as-is causes a serious problem | Security vulnerability, risk of data loss, fundamental design defect | Unmitigated SQL injection, authentication bypass, inverted layer dependency |
| **WARN** | Needs consideration. Not fatal if unaddressed, but should be improved | Performance concern, reduced maintainability, unhandled edge case | An O(n^2) algorithm (when n is small), a DRY violation, insufficient error messages |
| **INFO** | For reference. Acting on it is optional | Style suggestion, future improvement idea, introduction of an alternative approach | Naming suggestions, library recommendations, future refactoring candidates |
| **PASS** | No problem | No problem was detected for the aspect in question | - |

> **Beware the ambiguity of `PASS`**: the severity PASS (no problem for a given aspect) and the
> code-review verdict PASS described below (the review as a whole passed) are different axes. Make clear from context which one is meant.
> It is also orthogonal to the coverage axis of [coverage-ledger.md](coverage-ledger.md):
> severity PASS means "it was evaluated (reviewed) and no problem was found", and is a subset of `reviewed`.
> An area that was not examined (skipped / unsupported / inconclusive) must never be reported as PASS.

### Score-band usage (the plan-reviewer dialect)

plan-reviewer maps a risk score (0-100) onto the bands BLOCK (80-100) / WARN (50-79) / PASS (0-49).
The labels match the severities but the input is a score. It is an approved dialect whose mapping is
consistent with this table's meaning ("the high-risk band = BLOCK"); it does not introduce a separate severity system.

## Implementation review verdicts

| Verdict | Condition | Action |
|------|------|-----------|
| **PASS** | No BLOCK, no WARN. Implementation is sound | Proceed |
| **WARN** | No BLOCK. WARN-level issues remain | Review warnings, fix if necessary |
| **BLOCK** | Critical implementation issues detected | Fix before proceeding |
| **ESCALATE** | A finding requires changing an AGREED ledger row or clause | Escalate to brainstorm for re-agreement — the review cannot resolve spec gaps autonomously |

## Code review verdicts

| Verdict | Condition | Action |
|------|------|-----------|
| **PASS** | No problems, or INFO only | Continue |
| **PASS WITH NOTES** | WARN-level findings exist. Not fatal | Record the findings and continue |
| **NEEDS FIX** | A BLOCK-level problem exists | Issue fix instructions and re-implement → re-review (at most one retry) |

### Handling NEEDS FIX

- **Normal mode**: pass the fix instructions to the agent and re-implement → re-review (at most one retry)
- **Headless mode**: output the review result to the user and stop processing (the user decides the next action)

## Three-valued context verification

The shared frame for verifying, in context, whether a candidate found by a sweep search or similarity detection
may actually be acted on. Used by find-then-verify skills such as sweep-fix / refactor / skill-regression.
**This section is where the frame (the three values, the Iron Law, the fail-safe) is defined.**

| verdict | Meaning | Handling |
|---------|------|------|
| **CONFIRMED** | The verification predicate is satisfied, with grounds | May be acted on |
| **FALSE_POSITIVE** | It matches textually but does not apply in context | Do not act (record the reason) |
| **UNCERTAIN** | The context or grounds needed to decide are missing | Do not act (fail-safe). Report only |

- **The Iron Law**: a CONFIRMED whose grounds cannot be written down does not exist. If they cannot be written, demote it to UNCERTAIN
- When in doubt, fall to UNCERTAIN. Never include UNCERTAIN among the targets to act on (missing something is safer than letting a false positive through)
- **The verification predicate for CONFIRMED is specialized per skill (a deliberate difference)**:
  sweep-fix uses "the same problem holds for the same reason" (`skills/sweep-fix/references/context-verification.md`),
  refactor uses "it can be applied safely while preserving behavior" (`skills/refactor/references/behavior-preservation-checks.md`).
  The predicate is defined on the skill side; this section owns the frame

> **`UNCERTAIN` (the finding-verification axis) and `inconclusive` (the coverage axis) are different axes**:
> `UNCERTAIN` attaches to an individual finding candidate and means "it cannot be decided whether this candidate may be acted on" (this section).
> By contrast, `inconclusive` in [coverage-ledger.md](coverage-ledger.md) attaches to an **area** and means
> "there is not enough evidence to conclude anything about this area". An area can be `reviewed` while an individual candidate in it
> is `UNCERTAIN`. Do not conflate the two.

## Meta-review rules

Meta-review is an additional checking mechanism that safeguards the quality of the discussion.

### Trigger conditions

- Fires automatically **only when there was at least one BLOCK** at the point where the discussion reached agreement
- Skipped when every point converged at WARN or below

### Constraints

| Constraint | Content |
|------|------|
| **Maximum count** | Once only. Prevents infinite loops |
| **Input** | Only the fix diff of the agreed result plus the agreement summary. Resending the full plan is forbidden (token economy) |
| **Target members** | Ask for fix confirmation only from the members who raised a BLOCK/WARN (do not resend to everyone) |
| **The Lead's final authority** | Even if meta-review raises a new BLOCK, the Lead makes the final call |

### Check items

- **Cross-cutting risk**: risk arising from the combination of several proposals (e.g. a Performance parallelization proposal creates a path that bypasses Security's input validation)
- **Consistency of fixes**: whether the fix addressing a BLOCK contradicts other agreed items
- **Oversight detection**: overall risks that individual reviews could not see
