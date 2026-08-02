---
name: skill-reviewer
description: Diagnose skill artifacts — a SKILL.md, its references, its fixtures, and its bundled scripts — over behavioral effectiveness, context economy, responsibility placement, instruction quality, and script strength. It is a diagnostic instrument, never a merge gate - it adds no enforcement, runs no dynamic sensors, reads run evidence others already produced, and splits its output into a control-candidate channel and a diagnostics channel so advice cannot be mistaken for a stop order. Use when the user says "skill-reviewer", "review this skill", "diagnose the SKILL.md", "スキルをレビューして", or when a change under skills/ needs reviewing. For application code or a general implementation plan use plan-reviewer; for the quality of a test suite use review-testing; for consistency of naming and entry points across skills use skill-interface-audit.
---

# skill-reviewer

A read-only diagnostic pass over skill artifacts. It reports; the caller decides.

- Output shape and the BLOCK admission rule: [references/output-contract.md](references/output-contract.md)
- What may be claimed from what evidence: [references/evidence-and-coverage.md](references/evidence-and-coverage.md)

## What this is and is not

The merge gates already exist: the repository's canonical check runner and the regression ledger fail on observed
failures and explicit contract violations. This skill adds **no** new enforcement on top of them. It exists because
applying a recall-optimized plan review to natural-language artifacts produced a self-amplifying loop — a finding
answered with more prose, that prose opening new interpretation branches, those branches becoming the next round's
findings — that took 22 rounds to converge (PR #190).

So three things hold throughout:

- **A verdict here is not a stop order.** Stopping and fixing are the caller's decisions.
- **Prose is not the remedy.** A finding whose fix is "add a sentence explaining this" is the loop restarting. If a
  mechanism is wrong (a race, an ordering, a cleanup window), the finding is that it belongs in code with tests.
- **Do not edit the artifact under review.** Diagnose; the fix belongs to whoever owns the change.

## Step 1: Confirm the subject

In scope: `skills/*/SKILL.md`, `skills/*/references/**`, `skills/*/fixtures.json`, `skills/*/scripts/**`,
`skills/shared/references/**`, and the thin `commands/*.md` wrappers.

- Nothing in scope → say so and stop. Do not review application code here.
- Mixed change → review only the in-scope files and say plainly which files you left to a general implementation
  review. The same problem is never counted twice across the two reviews.

## Step 2: Route by change kind

What you read and what you run is determined by what changed — not by reviewer discretion. This keeps the cost of a
review predictable from the diff alone.

| Change kind | Evidence to read | Deterministic checks to run |
|-------------|------------------|------------------------------|
| A new skill | Whether a fixture exists at all; the authoring guide's checklist | Repository validator; unit tests of any bundled scripts |
| A SKILL.md body edit | The ledger record for that skill (5 states) | Repository validator; measure the total load of one execution path |
| A shared contract edit | The reverse-dependency list, and the ledger record of every skill on it | Repository validator; ledger impact lookup; ledger check |
| A `references/` edit | The ledger record of the owning skill | Repository validator; link targets resolve |
| A `scripts/` edit | Existing unit tests and what they actually pin | Run those unit tests; read their assertions |
| A `fixtures.json` edit | The prior fixture text — was a requirement weakened or a scenario made easier? | Repository validator (fixture schema); ledger check |
| A command wrapper, README, or manifest | — | Repository validator |

The commands are the repository's own: its canonical check runner, `scripts/validate_repo.py`, and the regression
ledger tooling described in [references/evidence-and-coverage.md](references/evidence-and-coverage.md). Run them
through a shell command and quote the output — a check you did not run is not evidence, and its absence is a
coverage statement, not a finding.

**Never run an LLM sensor here** — no regression run, no dynamic firing evaluation, no tuning loop. They are
expensive, and the whole design of this skill assumes their cost is paid deliberately by a human, not incidentally
by a reviewer. `dynamic_sensors_executed` stays empty, and the output validator rejects any output claiming
otherwise.

## Step 3: The five dimensions

For each dimension, decide what you can conclude and what you cannot. The right-hand column is the ceiling on what
a static pass may claim; the promotion condition belongs in the coverage ledger.

### 1. Behavioral effectiveness

Does the artifact achieve its purpose when executed — not does an instruction covering the purpose exist. The
presence of a sentence is not the achievement of its goal.

Read the existing run record and classify it into the five states. With no `current_pass` record, this dimension is
`unsupported`: state what a run would cost and what it would settle, and claim no PASS.

### 2. Context economy

Measure, do not estimate: for one execution path, count the lines of the SKILL.md plus every reference that path
actually reads. Look for the same explanation inlined in several places where one contract reference would do, and
for instructions that change no behavior.

The authoring guide's budgets (a SKILL.md beyond ~400 lines; one path loading beyond ~1000 lines) are design smells
that call for re-placing responsibility — not thresholds to BLOCK on, and not a cue to reword more tightly.
Shorter is not automatically better: cutting a convention, a path constraint, or a safe-side default degrades
compliance.

### 3. Responsibility placement

Judgment belongs in words; guarantees belong in code with tests. Check it in both directions:

- A state transition, an ordering, an atomicity or crash-recovery property described in prose → it belongs in a
  script pinned by tests.
- A human judgement call — what may be auto-fixed, where confirmation is required, what a verdict means — hardcoded
  into a script's branches → it belongs in words.

### 4. Instruction quality

Is the purpose, the input, the success and stop conditions, and the safety boundary each decidable by a reader? Is
anything self-contradictory, or contradicted by a contract the body links to? Is the body free of platform-specific
tool API names and model names, and is shared vocabulary linked to its canonical contract rather than redefined
inline?

Whether the description actually fires on the right requests is not decidable here — that needs a dynamic
evaluation, so it is `unsupported`.

### 5. Scripts and tests

Are the primitives correct at their input boundaries and under injected faults? Do the tests pin behavior, or do
they pin the current implementation's wording? A test that would survive the bug it claims to prevent is a finding;
so is a fixture requirement phrased so it can only pass with today's exact output text.

Run the unit tests and quote the result. This dimension is the one where `reviewed` is normally reachable.

## Step 4: Grade the findings

Full rules in [references/output-contract.md](references/output-contract.md). The short form:

- **BLOCK** requires machine evidence that already exists — a currently failing test, a validator violation, or a
  contradiction refutable from the body text alone — and `qualification_reason` names it. If you cannot write down
  what the evidence is, the finding is not qualified; demote it. You are never obliged to build a fixture to
  justify a finding.
- **WARN** in the control channel for a real problem whose evidence does not yet exist. Recorded; execution
  continues.
- **OPPORTUNITY** and **INFO** go to the diagnostics channel. OPPORTUNITY states what improves and what is spent or
  risked by acting.
- Size, duplication, and simplification are OPPORTUNITY by default, not BLOCK.

## Step 5: Emit and check the output

Compose the document per the output contract, then run:

```bash
python3 skills/skill-reviewer/scripts/validate_review_output.py <output.json>
```

Exit 1 means the output violates the contract — fix the output, do not report around it. Then present the findings
for a human, keeping the two channels visibly separate and labeling every evidence state with the validator's own
label rather than one you compose.

## Preventing rationalization

| Excuse | Reality |
|--------|---------|
| "It is obviously wrong, so it is a BLOCK" | Conviction is not evidence. BLOCK needs evidence that already exists, named in `qualification_reason` |
| "The body is over the line budget, so BLOCK" | A budget crossing is a design smell. It is an OPPORTUNITY to re-place responsibility |
| "The instruction is ambiguous — I will add a clarifying sentence" | Adding prose is the loop that cost 22 rounds. Report the ambiguity; you do not edit the artifact |
| "There is no fixture, so the change cannot be approved" | Absent run evidence is a coverage state (`uncovered`), not a defect, and never a gate |
| "Every static check passed, so the skill works" | Static conformance says nothing about execution quality. Cap the claim at what the evidence supports |
| "A quick regression run would settle this" | Sensor cost is a human's call. Recommend it with blast radius and cost; do not run it |
| "No findings, so no problems" | Only if the coverage ledger shows a non-empty scope. Otherwise say what you could not look at |

## Red flags

- A BLOCK whose `qualification_reason` restates the summary instead of naming a check, a test, or a contradiction.
- A finding whose recommended fix is "explain this more thoroughly in the SKILL.md".
- A coverage ledger with no `unsupported` rows even though no run was performed.
- An `accepted_without_run` record presented as run evidence.
- Findings raised against files outside the in-scope list, or the same problem reported in both channels.
- The artifact under review appearing in your own diff.
