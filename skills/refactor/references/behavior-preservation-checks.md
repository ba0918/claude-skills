# Behavior Preservation Checks — the context-verification checklist for preserving behavior

The judgment criteria used in refactor Phase 4 (VERIFY). Against the candidates picked up by the sweep search (Phase 3)
(both `origin` and `sweep_candidates`),
verify from context whether "**the same transformation can be applied safely at this site while preserving behavior**".

> sweep-fix's `context-verification.md` is designed to ask "does the same **bug** hold here".
> This checklist asks "can the same **transformation** be applied while **preserving behavior**". The questions run in opposite directions, so do not reuse one for the other.
> The **definitions** of the 3-valued verdict conform to the shared contract severity-and-verdicts.md (already linked from SKILL.md).

## The definitions of the verdicts (in the refactor context)

| Verdict | Definition | The condition for it to hold |
|------|------|---------|
| **CONFIRMED** | The same transformation can be applied safely while preserving behavior | Every item of the checklist below falls on the "can be applied safely" side, and the grounds can be written in 1-2 sentences |
| **FALSE_POSITIVE** | It resembles the origin on the surface but the context differs (inapplicable or unnecessary) | Some item confirmed that it cannot or should not be applied. Always record the reason for exclusion |
| **UNCERTAIN** | Whether it can be applied is context-dependent and the evidence is insufficient | Neither could be confirmed. Do not fix it; leave it to the user |

> The frame (the 3 values, the Iron Law, fail-safe) is defined in the shared contract
> [severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md), section
> "The 3-valued verdict of context verification". This file specializes the refactor-specific verification predicate (behavior preservation).

## The Iron Law

```
A CONFIRMED whose grounds cannot be written does not exist. If they cannot be written, demote it to UNCERTAIN.
Promotion from UNCERTAIN to CONFIRMED is forbidden (the reverse demotion is always permitted).
```

## The checklist

For each candidate site, **actually read the file with Read** (never judge from the excerpt alone) and confirm the following:

### 1. Identity of the behavioral contract

After the transformation, can the inputs/outputs, side effects, error behavior, and execution order be kept **completely identical**?

- Do the types and conditions of the return value and exceptions stay unchanged?
- Do the **count and order** of side effects (I/O, state changes, logging) stay unchanged?
- Is the order of short-circuit and lazy evaluation preserved?
- If even one of these changes, it is **FALSE_POSITIVE** (that is not a refactor but a behavior change)

### 2. Homogeneity of the calling context (comparison against the origin)

Is the calling context of the sweep_candidate homogeneous with the origin?

- Can the same transformation (for example, splitting a flag argument) be applied with the same meaning at every call site?
- If only one side is a public API, a serialization boundary, or a reflection target, it is **FALSE_POSITIVE / UNCERTAIN**
- Confirm the call sites not just around the candidate line but **all the way back to the function's entry and every caller**

### 3. Traces of a deliberate difference

Is there evidence that this way of writing it is deliberate?

- A comment explains the reason (`// deliberately ...` / `// NOTE:` / a performance note)
- Redundancy for a planned future branch or for backward compatibility (a migration shim and the like)
- A test that pins the behavior presupposes "that shape"
- If any applies, it is **FALSE_POSITIVE** (a deliberate design) or **UNCERTAIN** (the intent is legible but room for improvement remains)

### 4. Whether a means of proof exists (the verifiability of behavior preservation)

After the transformation, can you **prove** that "the behavior has not changed"?

- Does an existing test, type check, lint, or a runnable characterization probe cover this site?
- **None of them covers it → UNCERTAIN** (claiming behavior preservation without a means of proof violates the verification gate)
- A site where a characterization test cannot be newly generated under headless execution is also **UNCERTAIN**

### 5. Performance sensitivity

A two-stage check. First determine whether the transformation could affect performance at all, then check the hot-path status only when it could.

1. **Does the transformation change performance characteristics?** — check whether evaluation order, call count, allocation, or computational complexity change. If none of these change (e.g. a rename, comment cleanup), the transformation is **performance-neutral** and passes this check regardless of hot-path status
2. **Hot-path check** (only when stage 1 answered "yes" or "indeterminate"): is this site on a hot path, a benchmark target, or annotated with measurements?
   - The "simpler version" may be slower, and it cannot be rewritten without measurement → **UNCERTAIN**
   - **When it is unknown whether it is a hot path, fall to UNCERTAIN as well** (completing the fail-safe)
3. **When stage 1 itself is indeterminate** (cannot tell whether the transformation changes performance characteristics), fall to **UNCERTAIN** as well

### 6. Consistency with convention

Is the transformation consistent with the project's conventions (the style and idioms of the surrounding code)?

- A "simplification" that breaks convention is churn. Consistency with the surroundings wins → if inconsistent, it is **FALSE_POSITIVE**

## The fail-safe principle

- The cost of a wrong transformation (applying one that changes behavior or does not fit the context) is greater than the cost of holding back (passing on a genuine improvement)
- When in doubt, do not fix it. Drop "looks the same on the surface but the context differs" into FALSE_POSITIVE or UNCERTAIN

## Examples of verdicts

**The improvement (origin)**: split the boolean flag argument `doExport(true)` into the two functions `doExportAsPdf()` / `doExportAsCsv()`, whose intent is legible (C4)

| Candidate | Context | Verdict | Grounds |
|------|------|------|------|
| `services/order.ts:42` (the origin) | 3 internal calls, each unambiguous in meaning, tests exist | CONFIRMED | Every call site can be split with the same meaning, and existing tests pin the behavior |
| `doExport(true)` at `services/invoice.ts:88` | Calls the same utility internally. Tests exist | CONFIRMED | The calling context is homogeneous with the origin, and the behavioral contract can be preserved |
| `doExport(flag)` at `api/public_export.ts:12` | `flag` originates in an external API query parameter | UNCERTAIN | The argument is external input at runtime, and splitting into 2 functions could ripple into a public API signature change |
| `doExport(true)` at `legacy/report.ts:30` | Immediately preceded by `// TODO: remove after v2 migration` | FALSE_POSITIVE | Temporary code scheduled for deletion. Not worth the effort (covered by the Phase 0 exclusion of temporary code) |

## The recording format

```json
{
  "improvement_id": "R1",
  "verdicts": [
    { "file": "services/invoice.ts", "line": 88, "role": "sweep_candidate",
      "verdict": "CONFIRMED", "reason": "the calling context is homogeneous with the origin and the behavioral contract can be preserved" },
    { "file": "api/public_export.ts", "line": 12, "role": "sweep_candidate",
      "verdict": "UNCERTAIN", "reason": "the argument is external input and could ripple into a public API signature change" }
  ]
}
```

`reason` is required. A verdict with an empty reason is treated as invalid data, and that candidate is re-judged as UNCERTAIN.
