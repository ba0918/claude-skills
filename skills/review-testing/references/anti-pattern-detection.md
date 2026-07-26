# Anti-Pattern Detection — the enforcement spec for the 5 iron laws

The enforcement spec that turns the 5 iron laws of [testing-anti-patterns.md](../../shared/references/testing-anti-patterns.md) into detection predicates, evidence requirements, and three-valued verdicts.
Rather than duplicating the rule text, it defines the procedure for "collecting candidates mechanically from the test code and settling them with context".

Each predicate's verdict follows the CONFIRMED / FALSE_POSITIVE / UNCERTAIN of
[severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md). **A CONFIRMED whose grounds
(the call site list, the data flow) cannot be written is demoted to UNCERTAIN.** Areas that could not be decided go into
`inconclusive` in [coverage-ledger.md](../../shared/references/coverage-ledger.md).

Each predicate has a corresponding positive (must be detected) / negative (must not be a false positive) pair in
[fixtures](fixtures/). Use them **for regression checking when a detection predicate or a fixture itself changes**.
In an ordinary project review, apply the predicates directly to the target code; re-evaluating the bundled fixtures is not required.

## Common procedure

```
1. Candidate extraction: collect candidates from the test files with the grep / AST pattern of each predicate
2. Context verification: confirm "does it really apply" by enumerating the data flow and every call site
3. Three-valued verdict: CONFIRMED with grounds / FALSE_POSITIVE if it matches textually but does not apply / UNCERTAIN if the grounds are insufficient
4. Maintenance gate (only when a predicate / fixture changes): check that the fixtures' positives are detected and the negatives are not
```

## AP1: testing the behavior of a mock

**Iron law**: never assert the existence of a mock element. Verify the behavior of the real component.

- **Candidate extraction**: assertions on testids or elements containing `*-mock` / `mock`, and assertions that verify a mock's return value as-is.
- **Evidence requirement**: show, by tracing the asserted value back to its origin (the mock definition), that the assertion
  only guarantees "the mock ran" and never touches the implementation's behavior.
- **Three-valued**: traced to be a check of the mock's existence → CONFIRMED / a real element is verified alongside → FALSE_POSITIVE /
  no material to tell mock from real → UNCERTAIN.
- **fixtures**: [positive](fixtures/ap1-mock-behavior.positive.test.ts) / [negative](fixtures/ap1-mock-behavior.negative.test.ts)

## AP2: a test-only method in production code

**Iron law**: never put a method called only from tests into a production class.

- **Candidate extraction**: methods in production code referenced only from test files (`destroy` / `reset` / `_forTest` and the like are signs).
- **Evidence requirement**: **enumerate every call site** and show that there are zero calls from a production path.
  Even one production call means it does not apply.
- **Three-valued**: every call site enumerated, showing zero production calls → CONFIRMED /
  it is used from production too → FALSE_POSITIVE /
  it is a library's public API and external calls are outside the observable scope → UNCERTAIN (never punish a public API).
  **An exported class / method is UNCERTAIN, because even if every in-scope call site is a test, external use cannot be ruled out.**
- **fixtures**: [positive](fixtures/ap2-test-only-method.positive.ts) / [negative](fixtures/ap2-test-only-method.negative.ts)

## AP3: mocking a dependency you do not understand

**Iron law**: never let a mock erase a side effect the test depends on.

- **Candidate extraction**: cases where the mocked target holds a side effect the same test ends up depending on (file writes, duplicate detection, cache registration, and so on).
- **Evidence requirement**: enumerate the side effects of the real methods of the mocked target, and identify which of them the test's assertions depend on.
  If the mock erases a side effect that is depended upon, it applies.
- **Three-valued**: shown via the data flow that "the mock erases a side effect the test depends on" → CONFIRMED /
  only genuinely external or slow processing was mocked (the side effects still run for real) → FALSE_POSITIVE /
  the dependencies cannot be traced fully → UNCERTAIN.
- **fixtures**: [positive](fixtures/ap3-mock-understanding.positive.test.ts) / [negative](fixtures/ap3-mock-understanding.negative.test.ts)

## AP4: an incomplete mock

**Iron law**: never build a partial mock of only the fields you know about. Reproduce the real API's complete schema.

- **Candidate extraction**: the difference between the mock response object and the set of fields the consuming production code references.
- **Evidence requirement**: against the real API's response schema (type definitions, documentation, samples), enumerate the fields the mock lacks,
  and show which of them downstream code references. If a referenced field is missing, "the test passes but integration breaks".
- **Three-valued**: a missing field referenced downstream was shown → CONFIRMED /
  the missing fields are referenced from nowhere → FALSE_POSITIVE /
  the real schema is unknown so the omission cannot be established → UNCERTAIN.
- **fixtures**: [positive](fixtures/ap4-incomplete-mock.positive.test.ts) / [negative](fixtures/ap4-incomplete-mock.negative.test.ts)

## AP5: tests written after the fact (a TDD deviation)

**Iron law**: tests are not bolted on after the implementation (TDD comes first). But treat detection carefully.

- **Candidate extraction**: traces of tests added after the implementation commit (the order of additions to the same file, the PR diff).
- **Evidence requirement**: git history alone is **weak evidence** — squash / rebase distorts it. A cycle's RED/GREEN execution log is strong evidence.
- **Three-valued**: precedence confirmed from the RED/GREEN log (compliance or deviation) → CONFIRMED /
  identifiable as a regression test added after the fact for an existing bug → FALSE_POSITIVE (**never punish it**, so as not to discourage adding to the safety net) /
  judged from git history alone → **stops at UNCERTAIN**.
- **Separating the axes**: "was TDD followed this time" (this predicate) and "is the test effective now" (AP1-AP4, the three layers) are different axes.
  A test written after the fact but effective now is evaluated fairly by layers 1 and 2.
- **fixtures**: [positive](fixtures/ap5-tests-after-fact.positive.md) / [negative](fixtures/ap5-tests-after-fact.negative.md)

## Limits of detection (state them)

- Dynamically assembled mocks and metaprogrammed tests slip past static extraction → that area is `inconclusive`.
- A case where an external library's public API looks test-only is always UNCERTAIN (external calls are outside the observable scope).
- State these limits in the coverage ledger, and never confuse "the detection predicates did not reach it" with "no problems".
