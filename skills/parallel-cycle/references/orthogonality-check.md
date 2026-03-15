# Orthogonality Check - File Intersection Analysis

Logic for checking file orthogonality between plans and determining execution groups.

## Core Algorithm

### Step 1: Extract Affected File Sets

From each plan's "Files to Change" section, extract the set of files that will be created or modified.

```
Plan A files: {a1.ts, a2.ts, a3.test.ts}
Plan B files: {b1.ts, b2.ts, b3.test.ts}
Plan C files: {c1.ts, a1.ts}
```

### Step 2: Compute Pairwise Intersections

For every pair of plans, compute the intersection of their file sets.

```
A ∩ B = ∅        → orthogonal (parallel OK)
A ∩ C = {a1.ts}  → NOT orthogonal (must serialize)
B ∩ C = ∅        → orthogonal (parallel OK)
```

### Step 3: Build Execution Groups

Combine intersection results with the dependency graph to form execution groups.

**Rules:**
1. A plan cannot be in a group earlier than its dependencies
2. Plans with file intersections must be in different groups (the one with lower priority goes first)
3. Within a group, all plans are independent (no intersections, no dependency edges)
4. Maximize parallelism: place each plan in the earliest valid group

### Step 4: Validate Groups

After grouping, verify:
- [ ] Every plan appears in exactly one group
- [ ] No two plans in the same group share any files
- [ ] No plan is in a group earlier than any of its dependencies
- [ ] Groups are numbered sequentially starting from 1

## Concurrency Limit

Maximum 3 concurrent cycles per group (API rate limit protection).

If a group has more than 3 plans:
- Split into sub-batches of 3
- Execute sub-batches sequentially within the group
- All sub-batches in the same group must complete before the next group starts

## Special Cases

### Empty Affected Files

A plan with no listed affected files is treated as orthogonal to all other plans. It can be placed in any group, subject to dependency constraints.

### Shared Configuration Files

Files like `package.json`, `tsconfig.json`, `.env.example` are often touched by multiple plans. When detected in intersections:
- These plans must be serialized (placed in different groups)
- This is correct behavior (safe side)

### Dependency-Only Constraints

Even if two plans have orthogonal files, if one depends on the other, they must be in different groups with the dependency going first.

```
A files: {x.ts}
B files: {y.ts}
B depends on A
→ A in Group 1, B in Group 2 (despite orthogonal files)
```
