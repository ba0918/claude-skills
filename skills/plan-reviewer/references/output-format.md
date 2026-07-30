# Output Format - Implementation Reviewer

Output format definition for review results.

---

## Individual Dimension Report

Each review dimension outputs results in the following JSON structure:

```json
{
  "dimension": "security",
  "confidence": 75,
  "verdict": "WARN",
  "issues": [
    {
      "severity": "critical",
      "task": "1-1",
      "title": "Insufficient escapeHtml() coverage",
      "description": "There may be additional locations where user input is inserted into the DOM beyond error display",
      "location": "src/content/index.ts",
      "suggestion": "Enumerate all innerHTML assignment locations and verify comprehensive escapeHtml() coverage"
    }
  ],
  "positives": [
    "Consistent XSS defense via sanitizeHTML()",
    "Appropriate CSP configuration"
  ]
}
```

### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| dimension | string | Review dimension name |
| confidence | 0-100 | Issue severity (higher = more severe) |
| verdict | PASS/WARN/BLOCK | Verdict result |
| issues[] | array | Detected issues |
| issues[].severity | critical/important/minor | Issue importance |
| issues[].task | string | Task number in the plan |
| issues[].title | string | Concise issue description |
| issues[].description | string | Detailed issue description |
| issues[].location | string | Affected file/location |
| issues[].suggestion | string | Fix suggestion |
| positives[] | array | Good points and sound decisions |

---

## Final Summary Report

Final report integrating results from all dimensions:

```
================================================================================
IMPLEMENTATION REVIEW COMPLETE
================================================================================

📋 Plan: {plan filename}
📅 Date: {YYYY-MM-DD HH:MM}

┌─────────────────────┬────────┬────────┐
│ Dimension           │ Score  │ Verdict│
├─────────────────────┼────────┼────────┤
│ Correctness         │   25   │ ✅ PASS │
│ Security            │   75   │ ⚠️ WARN │
│ Performance/Memory  │   40   │ ✅ PASS │
│ Architecture/Design │   30   │ ✅ PASS │
│ Completeness        │   60   │ ⚠️ WARN │
│ Spec Conformance    │   85   │ 🛑 BLOCK│
└─────────────────────┴────────┴────────┘

Overall Verdict: 🛑 BLOCK (Max score: 85, driven by Spec Conformance)

────────────────────────────────────────

🛑 BLOCK Issues (must fix):
  [Spec Conformance] Task 2-1: Implementation does not match agreed acceptance criterion
    → Adjust implementation to match the agreed spec

⚠️ WARN Issues (recommended fix):
  [Security] Task 1-1: Possibly insufficient escapeHtml() coverage
    → Recommend enumerating all innerHTML assignment locations
  [Completeness] Task 2-2: Risk of MutationObserver disconnect leak
    → Add cleanup on component unmount

🔄 Spec Escalation (requires brainstorm re-agreement):
  (If any finding requires changing an AGREED ledger row or clause)
  [Spec Conformance] The acceptance criterion for X is insufficient — needs re-agreement

✅ Positives:
  - Sound decision to prioritize security fixes
  - Design conforms to layer architecture
  - Tests cover each implemented change

🤖 Codex Second Opinion:
  [Codex] Task 2-1: Consider using streaming instead of buffered approach
    → Streaming would reduce memory footprint for large payloads
  (If Codex unavailable: "⚠️ Codex second opinion unavailable")

────────────────────────────────────────

📝 Recommended Actions:
  1. Fix BLOCK items in the implementation
  2. Escalate spec issues to brainstorm for re-agreement
  3. Consider WARN items
  4. Review Codex second opinion for additional perspectives
================================================================================
```

---

## Verdict Thresholds

| Max Score | Verdict | Meaning | Action |
|-----------|---------|---------|--------|
| 80-100 | 🛑 BLOCK | Critical issues found | Fix implementation before proceeding |
| 50-79 | ⚠️ WARN | Room for improvement | Review warnings, fix if necessary |
| 0-49 | ✅ PASS | No issues | Implementation is sound |

### Overall Verdict Rules

- Overall verdict = verdict based on the maximum score across all dimensions
- If any dimension is BLOCK, overall is BLOCK
- If no BLOCK but one or more WARN, overall is WARN
- If all PASS, overall is PASS

**Verdict emoji usage (consistent per-dimension and overall):**
- ✅ for PASS, ⚠️ for WARN, 🛑 for BLOCK
- The overall verdict emoji must match the rule above — never let example text and rules disagree.

### Dimension Table When UI/UX Is Skipped

When Step 2.5 determines UI/UX review is not triggered, **omit the UI/UX row entirely** from the dimension table (do not render it as N/A). The table shows only dimensions that were actually evaluated. The column width stays the same; no placeholder row.

Explicitly note the skip once near the top of the report, e.g. `UI/UX Review: SKIPPED (no UI/UX signals detected)`.
