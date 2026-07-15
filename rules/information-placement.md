# Information Placement

Every piece of information has a proper home. Adopt the following four quadrants as the principle of information placement.

```
Code tells you How
Tests tell you What
Commit logs tell you Why
Code comments tell you Why not
```

**Relation to Design Principles**: When code cannot express How, that is a design problem (insufficient decomposition, poor naming) — an early warning of degraded testability.
**Relation to Testing Anti-Patterns**: Because tests express What, they verify actual behavior instead of asserting the existence of mocks.

## The Iron Laws

```
1. Express How in code. Never patch it over with comments
2. Express What in tests. The spec must be readable from test names alone
3. Write Why in commit logs. Never summarize the diff
4. Code comments carry Why not — and nothing else
```

## The Four Quadrants

| Home | Carries | Question it answers |
|------|---------|---------------------|
| Code | How | How is this implemented? |
| Tests | What | What does this do? (spec / behavior) |
| Commit logs | Why | Why was this change needed? |
| Code comments | Why not | Why was the obvious alternative rejected? |

Each quadrant doubles as a diagnostic rule. **If the information cannot be read from its proper home, the home itself is broken.**

- How is not readable from the code → refactoring signal (revisit decomposition and naming)
- What is not readable from test names → test design signal (describe behavior, not implementation details)
- Why is missing from the commit log → context loss (your future self will re-investigate the reason for the change)
- A comment says anything other than Why not → noise (delete it, or move the information to its proper home)

## Anti-Pattern 1: Writing How in Comments

**Violation:**

```typescript
// BAD: comment is a line-by-line transcription of the code
// filter by user ID, then sort
const result = items.filter(i => i.userId === userId).sort(byCreatedAt);
```

**Why it's a problem:**

- When the code changes, the comment becomes a lie. A lying comment is worse than no comment
- Feeling the need for a transcription comment is a signal that the code itself fails to express How

**Fix:**

```typescript
// GOOD: let names tell the How
const userItemsSortedByDate = items
  .filter(i => i.userId === userId)
  .sort(byCreatedAt);
```

### Gate Function

```
Before writing a comment, ask:
  "Is this something the reader learns by just reading the code?"

  Readable from code → STOP — delete the comment and refactor until the code reads that way
  Not readable from code → consider refactoring first.
    Only a constraint that code cannot express earns the right to be a comment
```

## Anti-Pattern 2: Tests That Tell How Instead of What

**Violation:**

```typescript
// BAD: test name describes implementation details (internal method calls)
test('calls repository.findByUserId and applies sortByCreatedAt', () => { ... });
```

**Why it's a problem:**

- Every refactoring (a change of How) breaks the test — even though behavior is unchanged
- Reading the test list tells you nothing about the spec

**Fix:**

```typescript
// GOOD: test name describes behavior (the spec)
test('returns the user\'s items ordered from newest to oldest', () => { ... });
```

### Gate Function

```
Before writing a test, ask:
  "Could someone explain this module's spec by reading the test names alone?"

  They couldn't → rewrite test names as behavior descriptions
  An internal method name or mock name appears in the test name → it's telling How. STOP
```

## Anti-Pattern 3: Writing What in Commit Logs

**Violation:**

```
BAD: fix: change the conditional in validateInput
```

**Why it's a problem:**

- What changed is visible in the diff. The only thing the diff cannot tell you is Why
- Whoever walks `git log` / `git blame` six months later (including your future self) can never reach the reason for the change

**Fix:**

```
GOOD: fix: tighten input validation — whitespace-only input was passing through

A user reported broken rendering when a username consists solely of
full-width spaces. Add an empty-after-trim check to reject it at the boundary.
```

### Gate Function

```
Before writing a commit message, ask:
  "Is this message just a summary of what the diff already shows?"

  It's a diff summary → STOP — write the motivation, context, and judgment behind the change
  You cannot articulate Why → you don't understand the purpose of this commit.
    Re-split the commits into logical units
```

## Anti-Pattern 4: Leaving Why Not Nowhere

**Violation:**

```typescript
// BAD: deliberately unidiomatic code with no explanation
for (const item of items) {
  await processOne(item);  // nobody knows why this isn't Promise.all
}
```

**Why it's a problem:**

- Anywhere you deliberately avoided the obvious approach will be "improved" back into it unless the reason is recorded
- Rejected alternatives and their reasons appear nowhere — not in code, not in tests, not in the diff. Comments are the only home this information has

**Fix:**

```typescript
// GOOD: record why the obvious alternative was rejected
// Sequential on purpose: parallelizing would hit the external API rate limit (10 req/s)
for (const item of items) {
  await processOne(item);
}
```

### Gate Function

```
Right after writing tricky or seemingly redundant code, ask:
  "If someone refactored this into the 'obvious' form, would it break?"

  It would break → write a Why-not comment. Name the constraint
    (rate limit, compatibility, ordering dependency, ...)
  It wouldn't break → no comment needed. If the obvious form works, write it now
```

## Quick Reference

| Symptom | Diagnosis | Prescription |
|---------|-----------|--------------|
| Comments transcribing the code | How is leaking into comments | Delete the comments; let decomposition and naming tell the How |
| Internal method names in test names | Tests are telling How | Rewrite test names in terms of behavior (What) |
| Commit log summarizes the diff | Why is missing | Write the motivation, context, and judgment |
| Deliberate workaround with no explanation | Why not is missing | Write a comment naming the constraint |
| Code buried in comments | Total placement collapse | Sort each comment into its quadrant and move it home |

## Red Flags

- Comments explaining the code line by line
- `// TODO: explain later` (Why not can only be written at the moment of writing)
- `mock`, internal function names, or private method names appearing in test names
- Commit messages that say only "fix X" / "change Y" with no reason
- A reviewer asks "why did you write it this way?" and the answer, given verbally, is recorded nowhere
