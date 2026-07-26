# Similarity Detection — choosing detection tools by role

Used in refactor Phase 3 (SWEEP). The procedure for choosing a tool, confirming it exists, and falling back, when searching the codebase for cases similar to each `REFACTOR_CANDIDATE` from Phase 2.

## Design policy: choose by role (not a pure staged fallback)

The tools have different purposes. Choose by the **nature** of the candidate and by the **language**.
Search broadly (avoiding false negatives); narrowing down is the responsibility of Phase 4 (context verification).

| Tool | Role | Supported languages | When to choose it |
|--------|------|---------|---------|
| `similarity-ts` / `similarity-rs` | **Structural** detection of duplicated blocks and code clones | TS/JS (ts) and Rust (rs) only | You want to pick up duplicated logic (C7) or copy-pasted blocks by structure |
| `ast-grep` | Enumerating every instance of a known **syntactic pattern** | Multilingual (specify the language) | The syntactic form is clear, such as nested ternaries (C3) or boolean flags (C4) |
| `Grep` | A broad **literal** search | Every language | The above are unusable, or literal tokens suffice |

## Existence check and fallback

Never presume an external CLI is available. Always **confirm existence with `which` → fall back if absent**.

```bash
which similarity-ts || echo "NOT_AVAILABLE"
which ast-grep || echo "NOT_AVAILABLE"
```

The fallback priority:

```
similarity-* (structural clone detection)
  └─ absent → ast-grep (syntactic patterns)
       └─ absent → Grep (literal)
```

- When a fallback occurs, record `fallback_reason` and put it in the REPORT
  (for example, `"tool": "grep", "fallback_reason": "similarity-ts not installed; ast-grep unavailable"`)

## The asymmetry of language coverage (important)

| Language | similarity-* | ast-grep | How the sweep is operated |
|------|:---:|:---:|------|
| TS / JS | ✅ similarity-ts | ✅ | Structural detection is available, so normal operation |
| Rust | ✅ similarity-rs | ✅ | The same |
| Python / Go / PHP / Dart, etc. | ❌ | ✅ (where the language is supported) | Only literal or syntactic search. **Operate conservatively, because the false-positive risk rises** |

**In languages without similarity-\* support**:
- Because structural clone detection is unavailable, treat Grep / ast-grep results on the premise that they contain many false positives
- Perform the Phase 4 verification more carefully and emit UNCERTAIN more generously (fail-safe)
- State explicitly in `fallback_reason` that a literal search was used because the language lacks similarity-* support

## Limiting the search range

- **Limit it to the same language and related directories as the Phase 0 scope.** Never sweep "the whole codebase" unconditionally
  (a full similarity-* sweep of a huge monorepo is heavy, and candidates in unrelated languages are noise)
- Excluded: `.git/` / `node_modules/` / build artifacts / lockfiles / vendored code
- Do not exclude test code (a similar improvement inside tests has candidate value too)

## Example commands (all read-only)

```bash
# similarity-ts: duplicate block detection (--threshold sets the similarity; no write flags are used)
similarity-ts --threshold 0.85 "src/services"

# ast-grep: enumerating a syntactic pattern (--pattern. Rewrite flags are not used in Phase 3)
ast-grep --pattern '$C ? $A : $B ? $D : $E' --lang ts "src"

# Grep: the literal fallback (generalize the specific parts)
# origin: doExport(true)  → picks up flag-argument calls broadly
grep -rEn 'doExport\((true|false)\)' src
```

> Phase 3 is **detection only**. Rewrite flags such as `ast-grep`'s `--rewrite` / `-U` are not used here
> (mechanical transformation is used conditionally in Phase 5's Rule of 500).

## The structure of the candidate list

```json
{
  "improvement_id": "R1",
  "pattern_used": "doExport\\((true|false)\\)",
  "tool": "grep",
  "fallback_reason": "similarity-ts not installed",
  "scope": "src/services (limited to the same language, TS)",
  "origin": { "file": "src/services/order.ts", "line": 42 },
  "sweep_candidates": [
    { "file": "src/services/invoice.ts", "line": 88, "excerpt": "doExport(true)" }
  ]
}
```

Always record `pattern_used` / `tool` / `fallback_reason` — so that from the REPORT the user can verify after the fact both the reproducibility of the search and the limits of its coverage (the conservative operation in unsupported languages).
