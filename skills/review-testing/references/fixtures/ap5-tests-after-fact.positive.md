# AP5 POSITIVE — a TDD deviation candidate (the verdict stops at UNCERTAIN)

## Scenario

- Commit order: `feat: add discount calc` (implementation only, no tests) → 3 commits later,
  `test: add discount tests` (tests added).
- A cycle RED/GREEN execution log **does not exist**.

## Expected handling

- git history is the only grounds, so **UNCERTAIN** (squash / rebase can distort the order).
- Promotion to CONFIRMED requires a cycle RED/GREEN execution log.
- "Is this test effective now" is a separate axis and is evaluated fairly by layers 1 and 2 (a test written after the fact still has value if it is effective).
