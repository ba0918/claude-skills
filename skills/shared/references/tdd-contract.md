# TDD Shared Contract

The TDD (Test-Driven Development) contract shared by the cycle / iterate / test-driven-development skills.
Inject it into the agent prompt during the implementation phase to enforce test-first development.

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

If code was written before the test, delete it and start over. No exceptions.

- Do not keep it around "for reference"
- Do not "adapt" it while writing the test
- Do not look at it. Delete it. Implement anew from the test.

## The RED-GREEN-REFACTOR cycle

```
RED    → write one failing test → confirm it fails (run it with Bash)
GREEN  → write the minimum code that passes the test → confirm everything passes (run it with Bash)
REFACTOR → improve while the tests stay green → confirm everything passes (run it with Bash)
```

### RED — write a failing test

- One test per behavior
- A clear test name (the name says what is being tested)
- Use real code wherever possible (keep mocks to a minimum)

**Required**: run the test and **confirm that it fails**.
- A compile error (an unimplemented type or function) is acceptable
- Confirm that the reason for failure is "the feature is not implemented"
- If the test passes, it is testing existing behavior → fix the test

### GREEN — the minimum implementation

- Write **only the minimum code** needed to pass the test
- No over-abstraction, no speculative implementation, no YAGNI violations
- Do not improve other code "while you are here"

**Required**: run the tests and **confirm that everything passes**.
- The new test passes
- No existing test broke

### REFACTOR — tidy up

- Runnable only after GREEN has been reached
- Remove duplication, improve naming, extract helpers
- Adding new behavior is forbidden
- If there is nothing to tidy (no duplication, naming is clear, responsibilities are well separated),
  **record that basis and move on** — REFACTOR has an explicit exit for "no change needed".
  Do not rearrange the structure just to have performed a REFACTOR (that is a YAGNI violation).
  Recording only "REFACTOR done" without stating what was changed, or what made a change unnecessary, is not acceptable

**Required**: run the tests and **confirm that everything still passes**.

## Rationalization table (top 5)

| Excuse | Rebuttal |
|--------|------|
| "Just skip it this once" | That is rationalization. TDD has no exceptions |
| "I already know it is correct" | Confidence is not evidence. Prove it with a test |
| "I will write the test later" | "Later" is a synonym for "never" |
| "This code is hard to test" | Hard to test = bad design. Fix the design first |
| "It is a prototype, so it needs no tests" | A prototype turning into production is the classic outcome |

## Red Flags (signs of a TDD violation)

- Production code was changed before the test file
- GREEN is declared without running the tests
- One test verifies several behaviors
- Refactoring happens before the tests pass
- Someone says "I will add the tests later"
- The mock setup is more complex than the test logic

## Reference paths from cycle / iterate

- Injected into cycle's agent prompt: "When implementing, follow tdd-contract.md and proceed test-first (RED → GREEN → REFACTOR)"
- Injected into iterate's Phase 3 agent prompt: the same
- The test-driven-development skill is the front end that applies this contract interactively with the user

## Automatic test-framework detection

The agent detects the test framework in the following order:

| File | Test command |
|---------|-------------|
| `package.json` (scripts.test) | `npm test` or `npx vitest` / `npx jest` |
| `Cargo.toml` | `cargo test` |
| `go.mod` | `go test ./...` |
| `pyproject.toml` / `setup.py` / `pytest.ini` | `pytest` |
| `Makefile` (a test target) | `make test` |

If detection fails, confirm the test command with the user.
