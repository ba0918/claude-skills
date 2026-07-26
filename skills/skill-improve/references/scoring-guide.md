# Scoring Guide

The friction scoring criteria. Compute each skill's friction score from the output of collect.py and decide the improvement action.

## Friction score formula

Each skill's friction score (0-10) is a weighted sum:

```
friction_score = min(10, (
    retry_rate × 3.0 +
    correction_rate × 2.0 +
    abandonment_rate × 3.0 +
    error_rate × 2.0
))
```

### Rate calculation

| Rate | Formula | Description |
|--------|--------|------|
| retry_rate | retry_count / invocation_count | retry rate (0-1) |
| correction_rate | correction_turns / (invocation_count × 5) | correction rate (saturates at 5 turns or more) |
| abandonment_rate | session_abandoned_count / invocation_count | abandonment rate (0-1) |
| error_rate | tool_error_count / max(total_turns_to_completion, 1) | error rate (0-1, saturates at 1) |

### When invocation_count is 0

A skill with invocation_count 0 (never invoked) is excluded from score calculation.

## Threshold table

| Score range | Verdict | Meaning |
|-----------|------|------|
| 0.0 - 0.9 | **Excellent** | No friction. No improvement needed |
| 1.0 - 1.9 | **Good** | Minor friction. Monitor only |
| 2.0 - 2.9 | **Acceptable** | Within tolerance. Record it in the report |
| 3.0 - 4.9 | **Needs Attention** | Improvement recommended. A Small iterate can handle it |
| 5.0 - 6.9 | **Problematic** | Improvement required. Handle with iterate |
| 7.0 - 10.0 | **Critical** | Urgent. Fix at the root with cycle |

## Action mapping

| Friction score | Action | Delegate to |
|-----------|-----------|--------|
| 0 - 2 | report only | none (emit friction-report.md and finish) |
| 3 - 5 | Small improvement | delegate to `claude-skills:iterate` |
| 6+ | Large improvement | build a plan from the improvement hypothesis → delegate to `claude-skills:cycle` |

## Dry-run rule

**Always perform a dry-run at every level.**

A dry-run displays the following and makes no actual change:

1. the list of skill files targeted for improvement
2. an outline of the changes (a diff preview)
3. the expected change in the friction score

Only in `improve` mode does it proceed to the actual implementation after the dry-run display.
In `analyze` mode it ends at the dry-run display.

## Accounting for confidence

| invocation_count | Confidence | Note |
|-----------------|--------|------|
| 1-2 | Low | Insufficient sample. The score is indicative only |
| 3-9 | Medium | A tendency is visible but statistically insufficient |
| 10+ | High | A trustworthy score |

Skills with Low confidence are excluded from improvement targets and only recorded in the report.
