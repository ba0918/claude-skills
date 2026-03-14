# Output Format - Plan Reviewer

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
PLAN REVIEW COMPLETE
================================================================================

📋 Target: {plan filename}
📅 Date: {YYYY-MM-DD HH:MM}

┌─────────────────────┬────────┬────────┐
│ Dimension           │ Score  │ Verdict│
├─────────────────────┼────────┼────────┤
│ Feasibility         │   25   │ ✅ PASS │
│ Security            │   75   │ ⚠️ WARN │
│ Performance/Memory  │   40   │ ✅ PASS │
│ Architecture/Design │   30   │ ✅ PASS │
│ Completeness        │   60   │ ⚠️ WARN │
│ Alternatives        │   85   │ 🛑 BLOCK│
└─────────────────────┴────────┴────────┘

Overall Verdict: ⚠️ WARN (Max score: 85 → BLOCK)

────────────────────────────────────────

🛑 BLOCK Issues (must fix):
  [Alternatives] Task 2-1: Using ETag/Last-Modified headers is more efficient than SHA-256 hash comparison
    → Consider an approach that compares ETags via fetch HEAD request

⚠️ WARN Issues (recommended fix):
  [Security] Task 1-1: Possibly insufficient escapeHtml() coverage
    → Recommend enumerating all innerHTML assignment locations
  [Completeness] Task 2-2: Risk of MutationObserver disconnect leak
    → Specify cleanup on component unmount

✅ Positives:
  - Sound decision to prioritize security fixes
  - Design conforms to layer architecture
  - Test plan included for each task

────────────────────────────────────────

📝 Recommended Actions:
  1. Fix BLOCK items before starting implementation
  2. Consider WARN items during implementation
================================================================================
```

---

## Verdict Thresholds

| Max Score | Verdict | Meaning | Action |
|-----------|---------|---------|--------|
| 80-100 | 🛑 BLOCK | Critical issues found | Modify plan before starting implementation |
| 50-79 | ⚠️ WARN | Room for improvement | Review warnings, modify plan if necessary |
| 0-49 | ✅ PASS | No issues | OK to start implementation |

### Overall Verdict Rules

- Overall verdict = verdict based on the maximum score across all dimensions
- If any dimension is BLOCK, overall is BLOCK
- If no BLOCK but one or more WARN, overall is WARN
- If all PASS, overall is PASS
