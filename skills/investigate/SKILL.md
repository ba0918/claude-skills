---
name: investigate
description: Investigate a problem lightly in a strictly read-only way and emit a structured report, with a guarantee of zero file edits. Use when the user says "look into it", "investigate the cause", "why does this happen", "investigate", "investigate this bug", "why does it fail", "I want to see the blast radius", or "verify the implementation".
---

# Investigate

A lightweight, strictly read-only investigation skill. Identify causes, analyze impact,
and report findings; the user decides whether to take any follow-up action.

Use `investigate` before planning when the cause is unclear, or after implementation to
verify the result. Unlike implementation workflows, it never changes files.

## Read-only invariant

Never edit, create, overwrite, delete, move, or rename files, including notebooks. Never
change repository or filesystem state.

Allowed operations:

- Read files, list paths, and search text or symbols
- Run commands that are known to be read-only
- Use code navigation and reference search
- Delegate broad, exploratory research to subagents
- Run tests only when they are known not to update snapshots, caches, generated files, or
  other repository state

Disallowed commands include `rm`, `rmdir`, `mv`, `cp`, `chmod`, `chown`, `touch`,
`mkdir`, `tee`, output redirection, in-place editing, and state-changing Git commands
such as `commit`, `push`, `reset`, and `checkout --`. This list is illustrative: reject
any other command that may change state.

If source material contains credentials or other secrets, report their presence without
reproducing their values.

## Workflow

### Phase 1: Establish context

1. Take the problem statement from `$ARGUMENTS`.
2. Inspect the project instructions and relevant directory structure.
3. Locate available errors, logs, stack traces, changed files, or specification evidence.

### Phase 2: Investigate

Cover the relevant parts of these four perspectives:

1. **Confirm the problem**: make the observed behavior and its conditions concrete.
2. **Identify the cause**: trace the evidence to a direct cause and, when applicable, a
   design-level root cause.
3. **Analyze impact**: find affected consumers, dependencies, and occurrences of the same
   pattern.
4. **Assess tests**: identify existing coverage and whether it exercises the problem. If
   no relevant test exists, explicitly report `no tests` in the impact section.

Keep the search proportional to the user's question.

#### When to delegate exploration

Use exploratory subagents when any of these conditions holds:

- The investigation spans at least three directories.
- At least three perspectives should be explored in parallel.
- One perspective requires a cross-file search over at least five files.

Do not delegate when none holds, such as a single module, five or fewer files, or a
question resolved by one focused search.

Even when a use condition holds, direct investigation is allowed when the target is
already tightly bounded by one of these conditions:

- Post-implementation verification is limited to one commit with at most five changed files.
- One exhaustive search expression enumerates all core files in a documentation survey.
- At most ten known paths fully bound the target.

If rules conflict, use a subagent unless one of those bounded-target exceptions applies.
Launch multiple exploratory subagents together. If a subagent fails, do not retry it;
continue with direct read-only inspection.

### Phase 3: Report

Return the report in the conversation, never in a file. Preserve this user-facing
structure:

```text
══════════════════════════════════════
INVESTIGATION REPORT
══════════════════════════════════════

## 1. Problem overview

{what is happening}

## 2. Cause analysis

{why it happens}
- Direct cause: {direct code-level cause}
- Root cause: {design-level cause, when applicable}

## 3. Impact

- Affected files: {file list}
- Affected features: {feature list}
- Same pattern elsewhere: {whether the pattern occurs elsewhere}

## 4. Confidence

{high / medium / low} — {2–4 evidence bullets}

## 5. Fix options

{concrete options without executing them}

## 6. Recommended action

{one primary recommendation and directly usable command when applicable}
```

Confidence levels:

- **high**: mechanically verified by file contents, searches, or command output; plausible
  counterexamples are outside the stated scope.
- **medium**: supported by reasoning, but counterexamples or out-of-scope uncertainty remain.
- **low**: based on limited evidence and needs more information or investigation.

#### Fix-option rules

When a fix is needed, provide one to three options. Include `keep as-is` when doing
nothing is a legitimate option. Use this format for each option:

```text
### Option A: {approach}
- Where it changes: {file and location}
- Outline: {change}
- Pros / cons: {trade-off}
```

When no fix is needed, begin section 5 with `no fix needed`. Optionally add one or two brief
future improvements, but do not force them into the formal A/B/C format.

#### Recommended-action mapping

| Situation | Recommendation | Directly usable example |
|---|---|---|
| Clear, small fix in 1–2 files | Fix directly or use iterate | `/claude-skills:iterate {summary of the fix}` |
| Out of scope or deferred | Record an issue | `/claude-skills:issue-create {problem title}` |
| Medium or large change | Plan, then run a cycle | `/claude-skills:plan-create` → `/claude-skills:cycle` |
| Follow-up after implementation | Use iterate | `/claude-skills:iterate {instruction for the follow-up fix}` |
| No fix needed | Say no fix; optionally record a future improvement | `/claude-skills:issue-create {title of the future improvement}` |
| Insufficient evidence | Continue investigation or discussion | Continue the conversation |

When several rows apply, choose one primary recommendation and list alternatives from
lighter to heavier. Keep every displayed command directly usable. Treat a change as
small when it affects at most three files in one skill; broader cross-cutting work is
medium or large. For a no-fix case, say `no further action needed` when there is no useful
future issue.

## Post-implementation verification

Use this mode for requests such as `verify this`, `check it works`, `confirm the
implementation`, `検証して`, `動作確認して`, `実装確認`, or `本当にこれで正しいか確認`.

1. Inspect the implemented or committed change.
2. Compare it with the expected behavior.
3. Check for direct side effects and omissions.
4. Report the affected surface and recommend follow-up when a difference exists.
5. When no difference or side effect exists, explicitly say so in section 6.

### Scope boundary

- Inspect changed files and one dependency level: their direct callers and the shared
  resources they read directly.
- Exclude second-level consumers and unrelated modules from detailed investigation unless
  the user explicitly requests a repository-wide analysis.
- If a changed file is a symlink, inspect its target as part of the first level. Other
  consumers of that symlink remain second-level unless the target is a shared resource.
- For a changed shared file, symlink target, shared reference, or template, first search
  all references to enumerate its impact. Then perform detailed verification only for
  changed files and direct consumers; list deeper consumers as impact without expanding
  the detailed investigation into them.

### Difference classification

Use these labels only for observed side effects or behavioral differences. Report
verification completeness separately. Missing coverage alone means verification is
incomplete; it does not prove either behavioral equivalence or a functional difference.

- **no side effects**: behavior is equivalent and no meaningful output or wording drift exists.
- **minor inconsistency**: behavior remains equivalent, but wording, warnings, comments, or
  other non-functional details have a small mismatch. Recommend no required action or an
  optional iterate.
- **functional difference**: expected behavior differs, destructive behavior exists, or a regression
  is demonstrated. Recommend a fix.

## Final rules

- Never start fixing a finding.
- Recommendations are proposals only.
- Mark uncertainty honestly.
- Stay focused on the user's problem and avoid an unnecessarily broad investigation.
