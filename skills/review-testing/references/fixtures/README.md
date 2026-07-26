# review-testing fixtures

For each anti-pattern, a pair of positive (must be extracted as a candidate) / negative (must not be a false positive).
The detection predicates are owned by [../anti-pattern-detection.md](../anti-pattern-detection.md), and each predicate links here.
Used for regression checking when running a review. The final verdict for a positive follows that fixture's expectation.
AP1-AP4 are CONFIRMED, and AP5 — which has only history — is correctly UNCERTAIN after candidate extraction.

| Anti-Pattern | positive | negative |
|--------------|----------|----------|
| AP1 testing mock behavior | `ap1-mock-behavior.positive.test.ts` | `ap1-mock-behavior.negative.test.ts` |
| AP2 test-only method | `ap2-test-only-method.positive.ts` | `ap2-test-only-method.negative.ts` |
| AP3 mocking without understanding | `ap3-mock-understanding.positive.test.ts` | `ap3-mock-understanding.negative.test.ts` |
| AP4 incomplete mock | `ap4-incomplete-mock.positive.test.ts` | `ap4-incomplete-mock.negative.test.ts` |
| AP5 tests after the fact | `ap5-tests-after-fact.positive.md` | `ap5-tests-after-fact.negative.md` |
