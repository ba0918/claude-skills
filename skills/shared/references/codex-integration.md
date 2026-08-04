# Codex Second Opinion Integration

Shared reference: the invocation pattern, fallbacks, and security rules for the Codex second opinion that several skills reference.

## Invocation pattern

### Agent Tool Parameters

```
subagent_type: "codex:codex-rescue"
mode: bypassPermissions (or default)
```

**Parallel execution**: achieved by dispatching several delegations concurrently in one batch.

### Prompt structure

1. **Provide context** — pass the plan file / code / diff / conversation text explicitly
2. **Instruct** — "point out design problems, oversights, and alternatives"
3. **Specify the output format** — JSON or structured text (differs per skill)

## Bias control

The value of a second opinion lies in its independence. Without the following it becomes an agreement machine: the cost is paid and the blind spots remain.

### What may be passed / what must not be passed

| May be passed | Must not be passed |
|-----------|----------------|
| The artifact (plan file / diff / conversation text) | Your own (caller-side) review results or list of findings |
| The constraints and requirements to satisfy (specification, user instructions) | Your own conclusion or verdict ("I think it is fine, but please check") |
| The output-format specification | Self-assessments such as "this should be…" / "this is correct" |

Passing your own conclusion pulls Codex toward agreeing with it (anchoring).
Codex must judge **whether the artifact satisfies the constraints** independently.
Reconciliation with your own review results happens only in the integration phase, after Codex's response comes back.

### Adversarial framing

Write the prompt in the "find issues" form. The "is this good?" form is forbidden.

- ✅ "Point out design problems, oversights, edge cases, and alternatives in this diff. If you find no problems, say so explicitly"
- ❌ "Check whether this diff is fine" / "I think this approach is good, but I would like your opinion"

### Detecting doubt theater (a Red Flag in the integration phase)

When Codex returns substantive findings and the integration phase **keeps dismissing every one of them as "duplicate" or "noise from missing context"**, that is a sign of verification theater (doubt theater) rather than verification. If two consecutive rounds adopt nothing, enumerate the reasons for dismissal explicitly and present them to the user — do not quietly bury them.

The reverse holds too: adopting every Codex finding without verification is not a second opinion but an abdication of responsibility. Decide adoption for each finding only after collating it against the text of the artifact.

## Fallbacks

Check the task result of the Codex agent and handle it by these rules:

| State | Action |
|------|-----------|
| Success | Integrate the result into the existing review (after deduplication) |
| Error | Show a warning and continue with the existing processing only |
| Timeout | brainstorm uses 10 seconds; others depend on the delegation mechanism's default timeout |
| Malformed response format (JSON parse error, etc.) | Show a warning and continue with the existing processing only |

### Warning message templates

```
⚠️ Codex second opinion unavailable — proceeding with existing review only.
```

On the first failure in brainstorm:
```
⚠️ Codex unavailable — proceeding without a second opinion
```

## Security

- Limit the context passed to Codex to **the plan file / diff / conversation text**
  - Exception: in a fix-loop re-review (github-issue and similar), "Codex's own previous findings + the fix diff" may be passed. It is the context needed to confirm that the findings were addressed, and it is not the target of bias control (a caller-side conclusion)
- When passing source code directly (codebase-review), exclude the following from `target_files`:
  - Files covered by `.gitignore`
  - Secret files such as `.env`, `credentials.*`, `*.key`, `*.pem`
- Use Codex's response **only as a review result**; never execute it directly

## Result integration patterns

### Review skills (plan-reviewer, codebase-review, iterate)

- Add Codex's findings to the existing review results
- Deduplication: skip a finding that points at the same file and the same problem as the existing review
- Prefix findings unique to Codex with `[Codex]`

### Sounding-board skills (brainstorm)

- Append Codex's opinion to your own response as a `💡 Codex's perspective:` section
- The caller produces an integrated answer that takes Codex's response into account
