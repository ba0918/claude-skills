# Fix-Action Taxonomy Shared Contract

The axis, shared by doc-audit / context-audit, for "how to handle a detected finding".
This is **a separate axis, orthogonal to severity (BLOCK/WARN/INFO/PASS, [severity-and-verdicts.md](severity-and-verdicts.md))**;
it decides "may this finding be fixed automatically". It originated as a local classification in doc-audit's
`references/checks.md`, and was promoted to a shared contract once context-audit became the third consumer.

## The two axes are orthogonal

| Axis | Values | Meaning | Defined in |
|----|----|------|--------|
| severity | BLOCK / WARN / INFO / PASS | How serious the problem is (how much trouble it causes) | [severity-and-verdicts.md](severity-and-verdicts.md) |
| fix action | AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY | Whether the fix can be automated (how to fix it) | This file |

Example: a WARN can be AUTO_FIX, and it can equally be REPORT_ONLY. Do not conflate the two.

## The three fix actions

### AUTO_FIX

Conditions: **mechanically verifiable + idempotent + no risk of data loss**.
Running the same operation any number of times yields the same result (idempotent). The tool presents the diff
and applies it after confirmation. **Never make deletion or semantic rewriting of body text AUTO_FIX.**

Examples: replacing an obvious path typo pointing at a real file (a unique candidate), normalizing a frontmatter key (body unchanged).

### NEEDS_JUDGMENT

Conditions: **semantic interpretation is required / the user's intent is ambiguous**.
The tool presents the finding and a recommended action, and **the user makes the decision**.
When in doubt, fall to this rather than AUTO_FIX (fail-safe).

Examples: several path candidates with no unique resolution, a coverage difference in a skill list (the omission may be deliberate).

### REPORT_ONLY

Conditions: **informational only**. No automatic action is taken.
It is presented as an actionable report covering what / why / how, but nothing is fixed.

Examples: vocabulary that permits destructive operations, leaked tool vocabulary, contradiction candidates, suspected secrets (auto-masking is forbidden).

## Difference from doc-check's `OK`

doc-check (code ⇔ docs) is binary — "match = `OK` / mismatch = needs fixing" — a different system from the three fix actions.
`OK` means "no problem (no finding is raised at all)", which differs from REPORT_ONLY ("a finding is raised but not fixed").
Once a finding occurs, it is classified into one of the three values.

## Gate Function

```
Before assigning a fix action to a finding, ask:

1. Is this fix mechanically verifiable, and does it give the same result however many times it runs? (is it idempotent?)
   NO  → do not make it AUTO_FIX
2. Does it involve data loss (deletion, semantic rewriting of body text)?
   YES → do not make it AUTO_FIX
3. Is the intent uniquely determined? (are there multiple candidates / is semantic interpretation needed?)
   NO  → NEEDS_JUDGMENT
4. Is it actionable at all? (or does it stop at providing information?)
   Information only → REPORT_ONLY

When in doubt, fall to the safe side (conservative in the order REPORT_ONLY > NEEDS_JUDGMENT > AUTO_FIX).
```

## Skills that reference this

- `doc-audit` (`references/checks.md`) — classification of docs ⇔ docs inconsistencies
- `context-audit` (`references/rule-catalog.md`) — classification of the CA-* rules for instruction files and memory
- `doc-check` (`references/content-checks.md`) — shares AUTO_FIX / NEEDS_JUDGMENT while keeping
  its binary `OK` system (see the "Difference from doc-check's `OK`" section)
