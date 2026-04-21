# Scope Criteria - Task Size Judgment

Criteria for determining the scope of additional instructions and routing them to the appropriate execution path.

## Judgment Matrix

| Aspect | Small (lightweight loop) | Large (plan creation recommended) |
|--------|--------------------------|-----------------------------------|
| Changed files | 1-3 | 4+ |
| New file creation | None | Required |
| Impact scope | Local (within 1 module) | Spans multiple modules |
| Design decisions | Not needed (clear direction) | Needed (tradeoffs involved) |
| Test impact | Minor modifications to existing tests | New test case groups required |
| Interface changes | None | Yes (API/type definition changes) |

## Judgment Logic

### Conditions for Small

All of the following must be true:

1. 3 or fewer affected files
2. No new file creation required
3. Impact is contained within 1 module
4. No design tradeoff decisions required
5. No changes to public interfaces (APIs/type definitions)

### Conditions for Large

Any of the following is true:

1. 4 or more affected files
2. New file creation is required
3. Changes span multiple modules
4. Design decisions (architecture/data structure choices, etc.) are needed
5. Changes involve public interface modifications

## Cumulative Impact Assessment

When iterate is called multiple times in the same session, assess the **cumulative** impact across all calls, not just the current one:

| Consecutive Calls | Action |
|-------------------|--------|
| 1st call | Normal judgment (Small/Large based on matrix above) |
| 2nd call | Display notice, apply normal judgment |
| 3rd+ call | Trigger cumulative Large warning. The combined scope of all iterate calls likely exceeds the "lightweight improvement" intent |

Detection method: Count `## Additional Changes` sections in the plan file. Each section represents one prior iterate run.

## Granularity Clarifications

These disambiguate the matrix above. Apply strictly — do NOT substitute personal judgment.

### "1 module" definition

A "module" is a **single file or tightly-coupled file group sharing the same primary concern**. Use this decision:

- Changes confined to **one file + its direct test file** → 1 module (Small)
- Changes confined to **one directory where all files share one concern** (e.g., `src/auth/*` all about authentication) → 1 module (Small)
- Changes touching **multiple independent concerns** (e.g., `src/auth/*` AND `src/billing/*`) → multiple modules (Large)

### "Public interface modifications" — what counts

A public interface change is **any modification to the signature observable from outside the module**. This includes:

- **Always Large**:
  - Removing or renaming exported functions/types
  - Changing parameter types or order of exported functions
  - Narrowing return types (e.g., `T | null` → `T`) — breaks existing callers
  - Adding required parameters to exported functions
  - Breaking HTTP API response contracts (field removal, type narrowing)
- **Small (bug-fix widening, NOT Large)**:
  - Widening return types to `T | null` to surface a previously silent failure mode (e.g., adding an empty-string guard that returns `null`). Callers with strict types will see a compile-time nudge; callers without will keep working.
  - Adding optional parameters with default values
  - Widening input accepted (e.g., accepting both `string` and `string[]`)

**Rule of thumb**: if the change **strictly expands** what inputs/outputs are valid without removing any previously-valid case, it is a widening and can be Small. If it **removes or narrows** any previously-valid case, it is Large.

## Notes on Judgment

- **When in doubt, lean toward Large** — Overestimation is safer than underestimation. But "doubt" should come from genuinely ambiguous cases, not from failure to apply the Granularity Clarifications above.
- Judgment is an estimate; if unexpected impact is discovered during implementation, halt and report
- Judge by actual code impact, not by user expressions like "just a small thing" or "quick fix"
- **Cumulative scope matters**: Even if each individual iterate call is Small, 3+ consecutive calls signal that the task may warrant a full plan
