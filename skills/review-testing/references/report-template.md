# Report Template — review-testing

The output format for review-testing. **Do not emit an overall score.** The deliverable is
findings plus a [coverage ledger](../../shared/references/coverage-ledger.md) — both, always.
Finding severity and the 3-value verdict follow
[severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md).

    # Test Quality Review — {target}

    Scope: {directory / glob / diff}
    Date: {YYYY-MM-DD HH:MM}
    Contract: read-only / no overall score / findings + coverage ledger
    Target integrity: {machine-checked result before and after, or dynamic evaluation not run}

## Findings

Every finding carries layer / severity / 3-value verdict / evidence / target. A CONFIRMED whose evidence cannot be written down is not listed (demote it to UNCERTAIN).

| # | Layer | Anti-Pattern | Severity | Verdict | Target (file:line) | Evidence |
|---|-------|--------------|----------|---------|--------------------|----------|
| 1 | L1 defect-detection power | AP1 mock behavior | WARN | CONFIRMED | foo.test.ts:42 | Asserts the mock return value as-is. Real behavior unverified |
| 2 | L2 contract verification | Failure path unverified | BLOCK | CONFIRMED | auth.ts:88 | No test exists for the deny path (call sites enumerated) |
| 3 | L3 stability | Time dependence | WARN | UNCERTAIN | order.test.ts:12 | Direct Date reference. Reproducing the flake needs an execution trace |

### Details (expand only what is both CONFIRMED and BLOCK)

- #2 Failure path unverified (auth.ts:88): the deny path of authorization (an unprivileged principal) has no corresponding test.
  Only the allow path is verified. Evidence: the call sites of denyAccess and the list of missing test references.
  Fixing is out of scope for review-testing (hand off to tdd / iterate).

## Coverage Ledger

This section is mandatory even with 0 findings. It distinguishes what was looked at from what was not.

| Target | Value | Reason / promotion condition |
|--------|-------|------------------------------|
| src/**/*.test.ts (N files) | reviewed | Applied the 5 predicates + the three layers to every file |
| Test file search range (when 0 files) | reviewed | Confirmed the glob and the search result. Checked the absence of tests against L2 contract coverage |
| e2e/ | skipped | This review is limited to unit test quality (user-specified) |
| mutation sensitivity | unsupported | No mutation runner installed. Installing one promotes L1 to reviewed |
| Async ordering dependence | inconclusive | Reproducing the flake needs an execution trace. Conclusive if logs exist |
| TDD adherence | inconclusive | git history only. CONFIRMED becomes possible with RED/GREEN logs |

Fixture regression (record this only in a review that changed a detection predicate or a fixture): {AP1-AP4 positive=CONFIRMED / negative=FALSE_POSITIVE, AP5 positive=UNCERTAIN / negative=FALSE_POSITIVE}

## Notes

- No overall score is emitted, deliberately (the coverage ledger is what states plainly what could not be measured).
- No fixes were made (read-only). Hand off to a fix-oriented workflow.
