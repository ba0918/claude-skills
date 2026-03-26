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

## Notes on Judgment

- **When in doubt, lean toward Large** — Overestimation is safer than underestimation
- Judgment is an estimate; if unexpected impact is discovered during implementation, halt and report
- Judge by actual code impact, not by user expressions like "just a small thing" or "quick fix"
- **Cumulative scope matters**: Even if each individual iterate call is Small, 3+ consecutive calls signal that the task may warrant a full plan
