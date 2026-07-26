# Pattern Extraction — the guide for converting a problem into a search pattern

Used in sweep-fix Phase 2. It converts a problem detected in Phase 1 into "a search signature that can find sites of the same kind across the whole codebase".

## Design policy: search broadly, narrow by verification

The responsibility of the search stage is **not to miss anything** (minimizing false negatives).
False positives mixed into the candidates are expected, and removing them is the responsibility of Phase 3 (context verification).

- Between a pattern that is "too strict and misses things" and one that is "too loose and produces more candidates", **fall to the loose side**
- That said, an indiscriminate pattern (for example, one matching every function call in the language) makes verification cost explode. As a guide, a pattern producing **more than 50 candidates** is made one step more specific

## Choosing a tool

Choose by the nature of the problem. When in doubt, Grep (always available).

| The nature of the problem | Tool | Examples |
|-----------|--------|-----|
| How a particular function or API is called | Pattern search (regular expressions) | Calling `JSON.parse(` without a try, passing a variable to `exec(` |
| Syntactic structure (nesting, an omission, a combination) | ast-grep | An empty catch clause, a Promise without await, a useEffect without cleanup |
| Every use of a particular symbol | The language server (reference search) | Enumerating every caller of a dangerous utility function, the uses of a deprecated type |

### Confirming availability, and the fallback

Never presume an external tool is available. Always **confirm existence → fall back if absent**:

```bash
which ast-grep || echo "NOT_AVAILABLE"
```

- **ast-grep absent** → fall back to a Grep regular expression approximating the syntactic pattern (make up for multi-line matching with the `-A`/`-B` context lines). Record in the candidate list's `tool` field that the approximation increases false positives (`"tool": "grep (ast-grep fallback)"`)
- **LSP unusable** (no server configured, an unsupported language) → fall back to a Grep of the symbol name. Because a different symbol with the same name can slip in, add checking the import statements to the Phase 3 checklist

## How to write a signature

### Grep patterns

1. Extract from the problem site's code **the minimal token sequence expressing the essence of the problem** (strip the site-specific parts such as variable names)
2. Generalize the site-specific parts with `\w+` / `[^)]*` and the like
3. Absorb notational variance with OR (for example, `"` versus `'`, with or without a space)

```
The original site: const data = JSON.parse(userInput);
A bad pattern:     grep "JSON.parse(userInput)"        ← depends on the variable name. It cannot pick up other sites
A good pattern:    grep "JSON\.parse\("               ← picks up broadly; whether it sits inside a try is judged in Phase 3
```

### ast-grep patterns

Match on syntactic structure. Generalize the site-specific parts with metavariables (`$X`).

```
Example: sweeping for empty catches
  ast-grep --pattern 'try { $$$ } catch ($E) {}'

Example: an asynchronous call that is not awaited
  ast-grep --pattern '$PROMISE.then($$$)'
```

### LSP reference search

Identify the definition site of the target symbol first, then enumerate every reference.

1. Jump to the definition to pin down the symbol's identity
2. Enumerate every use with a reference search
3. Convert each site in the output into a candidate list entry

## The search scope

- The default is **the whole repository** (the range specified in Phase 0 is "the range in which to look for the problem", not the range of the sweep)
- Excluded: `.git/`, `node_modules/`, build artifacts, lockfiles, vendored code. As a rule, whatever the project's `.gitignore` covers is excluded
- Test code is **not excluded** (a problem of the same kind inside tests is worth reporting too. Whether to fix it depends on the Phase 3 verdict and the severity)

## Recording into the candidate list

Create one file per problem at `.claude/tmp/sweep-fix/{problem_id}_candidates.json`.
Always record `pattern_used` and `tool` — so that the Phase 5 report guarantees the reproducibility of the search and
lets the user verify after the fact whether "the search was too narrow or too broad".

```json
{
  "problem_id": "P1",
  "pattern_used": "JSON\\.parse\\(",
  "tool": "grep",
  "scope": "the repo root (excluding node_modules and the like)",
  "candidates": [
    { "file": "api/handler.ts", "line": 88, "excerpt": "const body = JSON.parse(req.body);" }
  ]
}
```

## Anti-patterns

| Anti-pattern | The problem | Instead |
|--------------|------|---------|
| A strict pattern containing variable names or literals | It matches only that site, so it is no sweep at all | Generalize the site-specific parts |
| An excessively strict pattern "to save on verification" | It only increases false negatives. Verification cannot be skipped | Search broadly and narrow in Phase 3 |
| Using ast-grep without an existence check | In some environments it fails immediately | Confirm with `which` and fall back |
| Finishing the judgment from the search-result excerpt alone | The judgment is Phase 3's responsibility. An excerpt does not include the guard conditions | Record it as a candidate and hand it to Phase 3 |
