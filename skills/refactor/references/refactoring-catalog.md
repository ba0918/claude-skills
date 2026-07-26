# Refactoring Catalog — the catalog of improvement patterns

Used in refactor Phase 2. A collection of patterns for improving expression — raising the "speed of understanding" while preserving behavior.
**The criterion for conciseness is not line count but whether a new team member can understand it faster than before.**

## The governing principle

```
What is being improved is "expression that obstructs understanding", not "line count".
A one-line nested ternary is more complex than a five-line if/else. Some improvements increase the line count.
```

## The pattern table

Each candidate carries a pair: "why it obstructs understanding" and "the transformation applicable while preserving behavior".
The numbers in the "Signs" column (3 levels or more, 3 sites or more, and so on) are **guides, not cut-off conditions**.
Borderline cases (2 levels of nesting and the like) may still become candidates, and whether to adopt them is decided by the "new team member" test.

| # | Pattern | Signs | The behavior-preserving transformation | Cautions (the trap of over-simplification) |
|---|---------|------|---------------|------------------------|
| C1 | Deep nesting | if/for nesting 3 levels or more, code drifting rightward | Flatten with early returns / guard clauses | The early return must not change the order of side effects |
| C2 | An overly long function | One function carrying several responsibilities, requiring scrolling | Extract functions at meaningful units (so the name explains it) | The extraction must not reduce the visibility of shared state |
| C3 | Nested ternaries | `a ? b : c ? d : e` | if/else or an early return, or a lookup table | Preserve the side-effect order of short-circuit evaluation |
| C4 | A boolean flag argument | `doThing(true)`, where the call site is unreadable | Split into 2 functions whose intent is conveyed, or an enum type | It entails rewriting every caller (verify both origin and sweep) |
| C5 | Generic names | `data` / `tmp` / `res` / `handle()` | Rename to a name expressing the role | Public APIs and serialization keys cannot be renamed (public_api) |
| C6 | What-comments | A comment transcribing the code (`// increment i`) | Delete the comment + express the intent through naming. Keep why-comments | Never delete a comment explaining "why" |
| C7 | Duplicated logic | 3 or more copies of identical logic | Extract into a shared function (DRY) | Do not merge "accidentally identical" shapes. Keep what is scheduled to diverge |
| C8 | Dead code | Unreachable branches, unused variables and functions | Deletion is **out of scope for the first edition** (deletions have low reversibility). Record it as INFO in the REPORT | Watch for use via dynamic dispatch or reflection |
| C9 | A worthless wrapper | A wrapper that merely wraps one line with no abstractive value | Inline it | An abstraction that gives a concept a name, or one that forms a test boundary, is not "worthless" |
| C10 | Magic numbers | Numeric literals of unclear meaning scattered about | Extract into named constants | Making it a constant must not change the timing of computation (compile time vs runtime) |
| C11 | Chained negations | `if (!(!a && !b))` | Clarify with De Morgan's laws | Confirm the truth tables match exactly |
| C12 | A redundant intermediate variable | A variable used once whose name adds nothing | Inline it | Do not change the timing of evaluation or the number of side effects |

## Deletion and consolidation are out of scope for the first edition

Limit it to **highly reversible transformations** such as tidying names, extraction, and removing duplication.
Transformations with low reversibility, such as deleting dead code or consolidating APIs, risk breaking code that looks temporary but has become part of the spec
(a migration shim, a backward-compatibility shim, and the like), so the first edition does not handle them and reports them as INFO.

## The "new team member" test

Apply it to each `REFACTOR_CANDIDATE`:

```
Can a new member unfamiliar with the project understand the transformed code
"faster and more accurately" than the original?

  YES → it stays a REFACTOR_CANDIDATE
  NO / borderline → drop it to ALREADY_CLEAN (do not force weak improvements into the list)
```

## The trap of over-simplification (the "improvements" that must not be applied)

| The trap | Why it is a trap |
|----|---------|
| Inlining every abstraction to make it "flat" | An abstraction that gives a concept a name is not complexity. A named abstraction aids understanding |
| Shortening it by removing error handling | A behavior change. Error behavior is part of the behavioral contract |
| Unifying on a "better way of writing it" that differs from convention | Consistency with the surrounding code wins. Convention-breaking churn obstructs understanding |
| Turning things into one-liners to cut line count | A dense single line lowers the speed of understanding. Line count is not the metric |
| Rewriting a hot path to be "more readable" | The risk of unmeasured performance degradation. Fall to UNCERTAIN at the Phase 2 performance gate |
