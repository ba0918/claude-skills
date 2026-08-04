---
name: test-driven-development
description: Guide the TDD (RED-GREEN-REFACTOR) cycle. It enforces test-first development and demands the output of a test run through a shell command as evidence at each phase. Use when the user says "tdd", "test-driven", or "test first".
---

# Test-Driven Development

An interactive guide skill for the RED-GREEN-REFACTOR cycle. It enforces TDD on the user's task and demands evidence of test execution results at every phase.

### Differentiation from Other Skills

- **vs cycle / iterate**: cycle and iterate inject the TDD contract into subagent prompts and run automatically. This skill is a teaching tool that walks the user through one cycle at a time, interactively
- **vs commit**: commit performs best-effort verification before committing. This skill governs the whole implementation process with TDD

## Absolute Constraints

### Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

You may not advance to the GREEN phase until a shell command has confirmed the test fails.
You may not advance to the REFACTOR phase until a shell command has confirmed all tests pass.

### Applying verification-gate

Apply the Gate Function of [../shared/references/verification-gate.md](../shared/references/verification-gate.md) as the transition condition for every phase.
Transitions based on guesswork — "it should pass", "I'm confident" — are forbidden.

## Workflow: Guide (default)

### Phase 0: Acquire Context

0. Determine the [execution context](../shared/references/execution-context.md)
   (interactive or headless) and let every subsequent branch refer to that result.
1. Take the user's task from `$ARGUMENTS`
   - If `$ARGUMENTS` is empty: ask the user "Tell me the task you want to implement with TDD."
2. Auto-detect the test framework per the [detection table in tdd-contract.md](../shared/references/tdd-contract.md#automatic-test-framework-detection)
3. **When test framework detection fails**:
   - **Interactive mode**: ask the user "Tell me the test command (for example `npm test`, `pytest`, `cargo test`)."
     - The user answers "none" → display "TDD requires a test framework. Set up the test environment first." and finish
   - **headless / Auto mode**: do not guess a test command and continue. Report "No test framework could be detected" and abort (standing up test infrastructure is outside this skill's responsibility; the existence of a language's standard test runner does not count as successful detection)
4. Hold the test command as `$TEST_CMD`

Display:
```
══════════════════════════════════════
TDD SESSION
Task: {task_description}
Test command: {TEST_CMD}
══════════════════════════════════════
```

### Phase 1: RED — Write a Failing Test

1. Identify, from the user's task, the first behavior that should be tested
2. Write one test:
   - One test per behavior
   - A clear test name (the name alone tells you what is being tested)
   - Use real code wherever possible (keep mocks minimal)
   - Conform to [testing-anti-patterns.md](../shared/references/testing-anti-patterns.md)
3. **Run the test in the shell**:
   ```bash
   {TEST_CMD}
   ```
4. **Check the test result**:
   - ✅ The test **failed** → RED succeeded. Advance to GREEN
   - ❌ The test **passed** → you are testing existing behavior. Fix the test
     - If rewriting the test still cannot produce a RED (the requested behavior is already implemented) →
       **you must not weaken the implementation to manufacture a RED**. Show, in test execution output,
       that the requirement is already satisfied, then finish the session without adding an implementation.
       This ending is a legitimate result
       (declaring "already implemented, so finishing" without evidence is forbidden — presenting the output is the condition for finishing)
     - Before choosing this ending, **actually probe the boundaries of the input range the requirement covers**.
       Do not generalize from a handful of sampled points to "it holds for every input" (include the points where
       the implementation's branch conditions switch: negatives, zero, empty, upper limits). If even one input
       fails to hold, the requirement is unsatisfied and that is the true RED. If the range cannot be exhausted,
       state the range you checked and finish
   - ❌ The test **errored** (an error in the test framework itself) → fix the error and re-run
   - ❌ **Timeout** (60 seconds or more) → abort the test and ask the user how to proceed:
     ```
     ⚠️ The test run timed out.
     1. Change the test command
     2. Ignore the timeout and continue
     3. Abort the session
     ```

Display:
```
── RED ──
Test: {test_name}
Result: FAIL ✅ (expected)
Failure: {failure_message}
→ Proceeding to GREEN
```

### Phase 2: GREEN — Minimal Implementation

1. Write the **minimum code** that makes the test pass:
   - No excessive abstraction, no implementing ahead of need
   - YAGNI — do not write code the test does not demand
2. **Run the test in the shell**:
   ```bash
   {TEST_CMD}
   ```
3. **Check the test result**:
   - ✅ **All tests pass** → GREEN succeeded. Advance to REFACTOR
   - ❌ The test **failed** → fix the implementation and re-run (do not go back to RED)
   - ❌ **An existing test broke** → prioritize fixing the existing test

Display:
```
── GREEN ──
Tests: {pass_count}/{total_count} passed
Result: ALL PASS ✅
→ Proceeding to REFACTOR
```

### Phase 3: REFACTOR — Tidy Up

1. Tidy the code while the tests are green:
   - Remove duplication
   - Improve naming
   - Extract helpers
   - **Adding new behavior is forbidden**
2. **Run the test in the shell**:
   ```bash
   {TEST_CMD}
   ```
3. **Check the test result**:
   - ✅ **All tests pass** → REFACTOR succeeded. On to the next cycle
   - ❌ The test **failed** → fix what the refactoring broke and re-run

Display:
```
── REFACTOR ──
Changes: {refactoring_summary}
Tests: {pass_count}/{total_count} passed
Result: ALL PASS ✅
```

### Phase 4: Next Cycle or Completion

1. Review the task's remaining behaviors
2. Ask the user which action to take next:
   ```
   🔄 TDD cycle complete!
   
   Implemented: {implemented_behaviors}
   
   Next actions:
   1. Test the next behavior (→ back to RED)
   2. End the TDD session
   ```
3. "next behavior" selected → return to Phase 1 (RED)
4. "finish" selected → completion display:
   ```
   ══════════════════════════════════════
   TDD SESSION COMPLETE
   Cycles: {cycle_count}
   Tests added: {test_count}
   All tests passing: ✅
   ══════════════════════════════════════
   ```

## References

- [../shared/references/tdd-contract.md](../shared/references/tdd-contract.md) — the shared TDD contract
- [../shared/references/verification-gate.md](../shared/references/verification-gate.md) — the pre-completion verification gate
- [testing-anti-patterns.md](../shared/references/testing-anti-patterns.md) — the testing anti-pattern catalog
