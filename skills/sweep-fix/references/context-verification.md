# Context Verification — the context-verification checklist

The judgment criteria used in sweep-fix Phase 3. Against the candidate sites picked up by the sweep search (Phase 2),
verify from context whether "the same problem genuinely holds".

## The definitions of the verdicts

| Verdict | Definition | The condition for it to hold |
|------|------|---------|
| **CONFIRMED** | The same problem holds for the same reason | Every item of the checklist below falls on the "the problem holds" side, and the grounds can be written in 1-2 sentences |
| **FALSE_POSITIVE** | It resembles the origin textually but there is no problem in context | Some item of the checklist confirmed that it does not hold. Always record the reason for exclusion |
| **UNCERTAIN** | The context needed to judge is missing | Neither could be confirmed. Do not fix it; leave it to the user |

> The frame (the 3 values, the Iron Law, fail-safe) is defined in the shared contract
> [severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md), section
> "The 3-valued verdict of context verification". This file specializes the sweep-fix-specific verification predicate (the bug holding).

## The Iron Law

```
A CONFIRMED whose grounds cannot be written does not exist.
If they cannot be written, demote it to UNCERTAIN.
```

## The checklist

For each candidate site, **actually read the file with Read** (never judge from the excerpt alone) and confirm the following:

### 1. Identity of the premises

Are the premises under which the original problem held (where the input comes from, the timing of execution, the presence of concurrency) the same at the candidate site?

- For example, even when the original site's problem is "using user input without validation", if the candidate site's input comes from a constant or an internally generated value, it is **FALSE_POSITIVE**

### 2. The presence of a guard

Does a guard that nullifies the problem already exist upstream of the candidate site (the caller, an early return, a type constraint)?

- For example, even for a null-dereference candidate, if the caller already checks for null or the type is non-nullable, it is **FALSE_POSITIVE**
- Confirm guards not just around the candidate line but **all the way back to the function's entry and its callers**

### 3. Signs of a deliberate difference

Is there evidence that this way of writing it is deliberate?

- A comment explains the reason (`// deliberately ...` / `// NOTE:` / a lint-suppression comment)
- A test exists that pins that behavior
- If any applies, it is **FALSE_POSITIVE** (a deliberate design) or **UNCERTAIN** (when the intent is legible but the possibility of a problem remains)

### 4. Whether the impact is real

Granting that the problem holds, is there a path from that site to actual harm?

- For example, unreachable code, test-only code, or a dead path has no impact → **FALSE_POSITIVE** (though the dead code itself may be recorded in the report as INFO)

### 5. The safety of the fix

If the Phase 1 proposed fix is applied at this site, can you say it will not break the existing behavior?

- When the proposed fix does not suit this site's context (the same problem but a different way of fixing it), **keep it CONFIRMED and adjust the proposed fix per site**
- When the behavioral change from the fix could amount to a specification change, it is **UNCERTAIN**

## The fail-safe principle

- **Promotion from UNCERTAIN to CONFIRMED is forbidden.** It can be re-judged only once additional context (a user's answer, documentation) is obtained
- **Demotion from CONFIRMED to UNCERTAIN is always permitted** (moving in the conservative direction is free)
- The cost of a wrong fix (fixing a false positive) is greater than the cost of holding back (passing on a true positive). When in doubt, do not fix it

## Examples of verdicts

**The original problem**: `JSON.parse(userInput)` is called without a try-catch and crashes on malformed JSON (P1. The severity labels are illustrative; how borderline cases fall follows the rules of SKILL.md Phase 1)

| Candidate | Context | Verdict | Grounds |
|------|------|------|------|
| `JSON.parse(req.body)` at `api/handler.ts:88` | External input, no guard | CONFIRMED | It parses the same external input as the original site without protection |
| `JSON.parse(fs.readFileSync(...))` at `config/loader.ts:12` | A config file inside this repository. Executed once at startup | UNCERTAIN | The input is an internal file, but whether the behavior on corruption (an immediate crash) is intended is unclear. It may be a fail-fast design |
| `JSON.parse(FIXTURE)` at `test/fixtures.ts:30` | Parsing a constant literal | FALSE_POSITIVE | The input is a constant and cannot become malformed JSON. The premise (external input) differs |
| `JSON.parse(msg)` at `worker/job.ts:51` | An `isValidJson(msg)` guard immediately before | FALSE_POSITIVE | The upstream guard nullifies the problem (check 2) |

## The recording format

`.claude/tmp/sweep-fix/verdicts.json`:

```json
{
  "problem_id": "P1",
  "verdicts": [
    {
      "file": "api/handler.ts",
      "line": 88,
      "verdict": "CONFIRMED",
      "reason": "it parses the same external input (req.body) as the original site without protection"
    },
    {
      "file": "test/fixtures.ts",
      "line": 30,
      "verdict": "FALSE_POSITIVE",
      "reason": "the input is a constant literal, so the premise (external input) differs"
    }
  ]
}
```

`reason` is required. A verdict with an empty reason is treated as invalid data, and that candidate is re-judged as UNCERTAIN.
