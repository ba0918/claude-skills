# Testing Anti-Patterns

Tests verify actual behavior — never the behavior of mocks.
Following TDD (Red → Green → Refactor) prevents most of these anti-patterns before they happen.

**Relation to [design-principles.md](design-principles.md)**: Since testability is the supreme principle, the quality of the tests themselves must be held to the same standard. A broken test is a broken safety net.

## The Iron Laws

```
1. Never test the behavior of mocks
2. Never put test-only methods in production code
3. Never mock a dependency you don't understand
4. Never build incomplete mocks
5. Never write tests after the fact
```

## Anti-Pattern 1: Testing the Behavior of Mocks

**Violation:**
```typescript
// BAD: asserting the existence of a mock
test('renders sidebar', () => {
  render(<Page />);
  expect(screen.getByTestId('sidebar-mock')).toBeInTheDocument();
});
```

**Why it's a problem:**
- It only verifies that the mock works; it verifies nothing about the component's actual behavior
- The test passing gives no guarantee that the code is correct

**Fix:**
```typescript
// GOOD: test the real component's behavior
test('renders sidebar', () => {
  render(<Page />);
  expect(screen.getByRole('navigation')).toBeInTheDocument();
});
```

### Gate Function

```
Before asserting on a mock element, ask:
  "Am I testing the real component's behavior, or just confirming the mock exists?"

  Confirming the mock exists → STOP — delete the assertion or stop mocking
```

## Anti-Pattern 2: Test-Only Methods in Production Code

**Violation:**
```typescript
// BAD: destroy() is only ever called from tests
class Session {
  async destroy() {
    await this._workspaceManager?.destroyWorkspace(this.id);
  }
}
```

**Why it's a problem:**
- Production code gets polluted with test-only code
- Risk of it being called in production by accident
- Mixed responsibilities (violates design-principles #2)

**Fix:**
```typescript
// GOOD: extract into a test utility
// test-utils/session-cleanup.ts
export async function cleanupSession(session: Session) {
  const workspace = session.getWorkspaceInfo();
  if (workspace) {
    await workspaceManager.destroyWorkspace(workspace.id);
  }
}
```

### Gate Function

```
Before adding a method to a production class, ask:
  "Will this method only ever be used by tests?"

  Test-only → STOP — put it in a test utility
  "Does this class own the lifecycle of this resource?"
  It doesn't → STOP — put it somewhere else
```

## Anti-Pattern 3: Mocking a Dependency You Don't Understand

**Violation:**
```typescript
// BAD: mocking away a side effect the test depends on
test('detects duplicate', () => {
  vi.mock('ToolCatalog', () => ({
    discoverAndCacheTools: vi.fn().mockResolvedValue(undefined)
  }));
  await addItem(config);
  await addItem(config); // should throw, but the mock erased the side effect
});
```

**Why it's a problem:**
- The test depended on a side effect of the mocked target
- Over-mocking "to be safe" destroys the actual behavior
- Tests pass for the wrong reason, or fail inexplicably

**Fix:**
```typescript
// GOOD: mock at the right level
test('detects duplicate', () => {
  vi.mock('SlowExternalService'); // mock only the slow external call
  await addItem(config);  // the config file write still happens
  await addItem(config);  // duplicate detection works correctly
});
```

### Gate Function

```
Before mocking a method:
  1. "What side effects does the real method have?"
  2. "Does this test depend on any of those side effects?"
  3. "Do I fully understand why this mock is needed?"

  Depends on side effects → mock at a lower level (the genuinely slow / external operation)
  Understanding incomplete → run against the real implementation first,
    observe what is actually needed, then mock

  Red flags:
    - "Let me mock it to be safe"
    - "It might be slow, so let me mock it"
    - Mocking without understanding the dependency chain
```

## Anti-Pattern 4: Incomplete Mocks

**Violation:**
```typescript
// BAD: mocking only the fields you happen to know about
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' }
  // metadata is missing → downstream code accessing response.metadata.requestId breaks
};
```

**Why it's a problem:**
- Partial mocks hide structural assumptions
- Tests pass but integration breaks
- False sense of security

**Fix:**
```typescript
// GOOD: reproduce the complete structure of the real API response
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' },
  metadata: { requestId: 'req-789', timestamp: 1234567890 }
};
```

### Gate Function

```
Before creating a mock response:
  "What fields does the real API response have?"

  1. Check the real API documentation or a sample response
  2. Include every field that downstream code might consume
  3. Verify the mock matches the real response schema exactly

  Uncertain → include every field the documentation lists
```

## Anti-Pattern 5: Tests After the Fact

**Violation:**
```
✅ Implementation complete
❌ No tests written
"I'll add tests once I get around to it"
```

**Why it's a problem:**
- Tests are part of the implementation, not an optional add-on
- Writing TDD-first makes this pattern impossible
- Claiming "done" without tests is claiming quality without verification

**Fix:**
```
The TDD cycle:
1. Write a failing test (RED)
2. Write the minimal implementation that passes (GREEN)
3. Refactor (REFACTOR)
4. Only now may you say "done"
```

### Gate Function

```
Before declaring "done":
  "Does this code have tests?"
  "Were the tests written before the code?"

  No tests → STOP — it is not done until the tests exist
  Tests written after → do TDD next time
```

## Quick Reference

| Anti-pattern | Fix |
|--------------|-----|
| Asserting on mock elements | Test the real component, or stop mocking |
| Test-only methods | Move them to a test utility |
| Mocking without understanding | Understand the dependency, then mock minimally |
| Incomplete mocks | Reproduce the real API's complete schema |
| Tests after the fact | TDD — write the test first |
| Overly complex mocks | Consider an integration test |

## Red Flags

- Assertions against `*-mock` test IDs
- Methods called only from test files
- Mock setup is more than 50% of the test
- Removing a mock breaks the test (not the implementation)
- You can't explain why a mock is necessary
- Mocking "to be safe"
