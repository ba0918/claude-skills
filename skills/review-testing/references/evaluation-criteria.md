# Evaluation Criteria — the three layers (+ an auxiliary layer)

The evaluation criteria of review-testing. The core is 3 layers (layers 1-3), with readability (layer 4) as an auxiliary layer.
Referenced from SKILL.md. Each finding is handled with the three-valued verdict
(CONFIRMED / FALSE_POSITIVE / UNCERTAIN) and the severity (BLOCK / WARN / INFO) of
[severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md),
and the evaluation scope is recorded in [coverage-ledger.md](../../shared/references/coverage-ledger.md).

**The consequence of emitting no overall score**: each layer produces findings independently. Never build a weighted
average across layers or a "test quality score". Per layer, leave "what was looked at" and "what was inconclusive" in the ledger.

## Default severity (missing tests)

Severity is decided not by "how many tests are missing" but by **the contract impact if it breaks while unverified**.

| The unverified contract | Default severity |
|---|---|
| A boundary whose breakage is a serious incident: authentication/authorization, data loss, monetary calculation, an entire public API | BLOCK |
| A hole that lets a local defect slip through: one branch of a public API, input rejection, a state transition, dependence on a future time | WARN |
| An auxiliary problem that does not directly change the defect detection result, such as naming or explanatory power | INFO |

- Never make it BLOCK automatically from the mere fact that there are 0 tests. Enumerate the target product's contracts and show the impact.
- Without the specification or usage context needed to judge the blast radius, keep the severity conservatively at WARN and use UNCERTAIN for the verdict as needed.
- Do not double-count the same root cause (no test suite) as both "BLOCK overall" and "WARN on every branch" — consolidate into a representative finding plus a breakdown.

## Layer 1: defect detection power (P0)

"Do the tests actually have the power to catch bugs?" Even with high coverage, weak assertions mean zero detection power.

### Detection predicates

- **Vacuous assertions**: the test merely calls the target without verifying behavior (no assertions at all,
  or only `expect(fn).not.toThrow()` without verifying the return value or state transition). → CONFIRMED (evidence: the test body)
- **mutation sensitivity (semi-automated, limited to important contracts)**: for an important contract (a public API or boundary enumerated by layer 2 below),
  does the test fail when a meaning-changing mutant is injected? **Only meaningful survivors are findings.**
  - Procedure: pick one contract → using **a throwaway copy outside the target, or a mutation runner that confines changes outside the target**,
    invert exactly one branch condition, boundary, or return value → run the corresponding tests in isolation → if they do not fail,
    make "a hole in the detection power for that contract" a finding. Never write a mutant into the reviewed target itself.
  - **Do not emit a mutation score** (a survival-rate number). Full mutation testing is out of scope (v1 is semi-automated and narrowed to important contracts).
    If there is no runner, or test side effects cannot be isolated, put this predicate into the ledger as `unsupported`.
- **Tautological assertions**: assertions that can never fail no matter how the implementation changes, such as `expect(true).toBe(true)`
  or verifying a mock's return value as-is. → CONFIRMED (evidence: the assertion expression)

### Guidance for the three-valued verdict

- The hole in detection power was actually shown with a mutant or a data flow → CONFIRMED
- It reads as weak, but another test covers the same contract → FALSE_POSITIVE (reason: where the complementary test is)
- It reads as weak, but there is no material for judging the contract's importance or whether it is complemented → UNCERTAIN

## Layer 2: contract verification (P0)

"Is there a corresponding test for each contract that must hold?" Contract here = public APIs, state transitions, permission boundaries, failure paths.

### Detection predicates

- **An unverified public API**: an exported function / method with no corresponding happy-path test.
  → CONFIRMED after confirming reachability (evidence: the export definition, and the absence of a test referencing it)
- **An unverified failure path**: no corresponding test for a path that throws an error or returns the error branch of a Result.
  The exception, error type, or rejection reason is part of the specification, yet the tests touch only the happy path. → CONFIRMED
- **A hole in the state transitions**: an untested edge among the transitions of a state machine or lifecycle (create → update → destroy, etc.).
- **An unverified permission boundary**: of the two-sided authorization tests (subjects allowed / subjects denied), the denial side is missing.
  It only verifies "what should be allowed passes" and never "what should be denied is denied". → CONFIRMED

### Where the coverage percentage stands

The coverage percentage **never enters a score**. Use the list of unreached lines only as a map for finding
"which contracts are untested". Even 100% coverage means nothing if layer 1 (detection power) is vacuous.

## Layer 3: stability of the safety net (P1)

"Are the tests non-flaky?" An unstable test is a hole in the safety net (failures get ignored, or a re-run passes).

### Detection predicates (making implicit dependencies evidential)

- **Time dependence**: referencing `Date.now()` / `new Date()` / the current time directly instead of injecting it, so it wobbles at boundaries (date rollover, TZ).
- **Randomness dependence**: asserting on random values without a fixed seed.
- **Order dependence**: results change with execution order through shared state between tests (globals, the module cache, a DB).
- **Network / wall-clock dependence**: depending on a real API or a real sleep (timing alignment via `sleep(n)`).

Each predicate is CONFIRMED once you can show "the place where that dependency actually exists" as evidence.
When reproducing the flakiness requires an execution trace, put it into the ledger as `inconclusive` (an area), with individual candidates as UNCERTAIN.

## Layer 4: readability (P2 — auxiliary layer)

- **The test name tells How**: an internal method name or mock name appears in the test name, so refactoring breaks it
  (a violation of information-placement's "Tests tell What"). → mostly INFO. Propose rewriting it as a behavior description.

## Correspondence with design-principles / information-placement

This skill is a translation of the following resident rules into "detection predicates for evaluating tests". Reference the rule text rather than duplicating it.

| Rule | What this skill enforces |
|--------|---------------------|
| [design-principles](../../shared/references/design-principles.md) "Testability Above All" | Layers 1 and 2 (detection power and contract correspondence are what Testability actually is) |
| information-placement "Tests tell What" | Layer 4 (does the test name tell the spec?) |
| The 5 iron laws of testing-anti-patterns | [anti-pattern-detection.md](anti-pattern-detection.md) (enforced in a separate file) |
