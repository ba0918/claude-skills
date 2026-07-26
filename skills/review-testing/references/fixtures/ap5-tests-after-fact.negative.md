# AP5 NEGATIVE — a test written after the fact that must not be punished

## Scenario

- Along with the fix `fix: reject whitespace-only username`, a regression test pinning that behavior was added.
- This is adding to the safety net for an existing bug, and must not be punished as a TDD deviation.

## Expected handling

- **FALSE_POSITIVE** (written after the fact, but legitimate as a regression test).
- Punishing it would chill "adding to the safety net when fixing a bug", so AP5 does not target it.
- The effectiveness of the test itself is evaluated by layer 1 (defect detection power).
