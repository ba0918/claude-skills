# Baseline Format (suppressing intentional differences)

The baseline that suppresses false positives arising from intentional differences. It lives at `.claude/context-audit-baseline.json`.

## Why it is committed / why it is treated differently from tmp

The baseline exists **to be shared by the team** (the agreement that "this finding is intentional in our project"), so it is **committed to the repository** rather than placed under `.claude/tmp/` (git-ignored). Intermediate JSON and reports are written to `.claude/tmp/context-audit/` (git-ignored), but the baseline alone is tracked.

## Only opaque finding IDs are stored

**Never store detected values, body text, or the content of a line.** What is stored is only the opaque finding ID (a hash). This guarantees that no secret can leak from a committed baseline (an invariant that holds in the v2 hash format as well).

### The composition of a finding ID (v1)

Computed by `aggregate_report.finding_id`:

```
finding_id = sha256(f"{id}|{where}|{what}")[:16]
```

- `what` has already been secret-redacted, and it is hashed, so it is opaque.
- The triple of `id` (the CA-* rule ID) + `where` (file:line) + `what` uniquely identifies one finding.

## Schema

```json
{
  "version": 1,
  "suppressions": [
    "3f2a1b0c9d8e7f60",
    "a1b2c3d4e5f60718"
  ]
}
```

- `version`: the version of the baseline format (v1 = a plain ID list).
- `suppressions`: the array of finding IDs to suppress.

## Operation (--update-baseline)

- If the baseline is absent on the first run, present the first-run flow (baseline the current state / triage / the full report).
- `--update-baseline` fixes the current findings into the baseline (thereafter only new findings are presented). The implementation is `aggregate_report.py --update-baseline PATH` (the `build_baseline` pure function, writing out only opaque IDs):

  ```bash
  python3 skills/context-audit/scripts/aggregate_report.py \
    .claude/tmp/context-audit/findings-{ts}.json \
    --update-baseline .claude/context-audit-baseline.json
  ```
- A suppressed finding is **shown in the report as a count only** (`M suppressed`). Silent truncation is forbidden.

## The risk of stale suppression (a known limitation of v1)

Because the v1 finding ID includes `where` (file:line), **moving a line changes the ID and the suppression comes off** (that is, it reappears — the safe-side behavior). Conversely, a collision in which a different finding happens to produce the same ID is effectively zero thanks to sha256.

- **A v2 candidate**: a normalized claim hash (independent of line numbers) + an expiry (automatic lapse after a set period). That would offer suppression robust to line movement, plus automatic cleanup of stale suppressions. v1 prioritizes simplicity.
