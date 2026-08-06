# Spec Generation — Reference

How brainstorm wrap generates and maintains human-readable specs in the consumer project's `docs/spec/` directory.

## When It Runs

Spec generation runs only when the exit contract status is `CONVERGED`. If the session is exploratory (no exit contract) or `BLOCKED`, skip spec generation entirely.

## Domain Matching

The agent autonomously decides which spec file to target:

1. List existing files in `docs/spec/` (if the directory exists).
2. Read each file's content and compare it with the brainstorm agreements.
3. Decide:
   - **Match found**: prepare an append draft for the matching file.
   - **No match**: create a new domain file with a descriptive kebab-case name (e.g., `auth.md`, `workflow.md`, `data-pipeline.md`).
   - **Directory absent or empty**: `mkdir -p docs/spec/` and create the first domain file.

State the matching rationale in the draft presentation (e.g., "Appending to `auth.md` because OAuth2 token refresh belongs to the authentication domain").

## Line Count Advisory

Before appending, count the current lines of the target file and estimate the total after appending. If the projected total exceeds 300 lines, present an advisory:

```
⚠️ docs/spec/{file}.md will be ~{projected} lines after this append (currently {current} lines). Consider splitting into smaller domain files.
```

This is an advisory flag, not a hard constraint or automatic split trigger. The human decides whether to split.

## Draft Presentation

Present the spec draft to the human for approval before writing. The presentation differs by operation type:

### New File

```
📝 Spec draft — new file: docs/spec/{domain}.md

{full draft content}

Write this file?
```

### Append to Existing File

```
📝 Spec draft — appending to docs/spec/{domain}.md
Reason: {matching rationale}

### Added section:
{only the new content to append}

📁 Changed files:
- docs/spec/{domain}.md

Full spec available at: docs/spec/{domain}.md
```

### Multiple Files Changed

When a single brainstorm session affects multiple domain files:

```
📝 Spec draft — {N} files affected

📁 Changed files:
- docs/spec/{domain-a}.md (append)
- docs/spec/{domain-b}.md (new)

### docs/spec/{domain-a}.md — added section:
{new content}

### docs/spec/{domain-b}.md — full content:
{full content}

Full specs available at the paths above.
Write these files?
```

## Human Gate

Wait for the human's approval before writing. Pre-approval in the prompt (e.g., "approve the spec draft") counts as valid approval — a separate interactive turn is not required when the user has already signaled consent. The human may:
- **Approve**: write the file(s).
- **Request changes**: adjust the draft and re-present.
- **Change domain assignment**: move content to a different file.
- **Reject**: skip spec generation for this session.

When interaction is impossible (headless mode), do NOT write directly to `docs/spec/`. Instead, save the draft to `.agents/artifacts/ideas/{slug}_spec_draft.md` and state the assumption in the completion message. In an autonomous flow that ends in a pull request, the flow promotes the draft to `docs/spec/` inside the PR and flags the addition in the PR body — the human's merge approval serves as the spec approval. Outside such a flow, the human reviews the draft and moves it to `docs/spec/` later. Either way the human gate contract holds: `docs/spec/` content only lands with explicit human approval.

## Spec File Format

Specs are human-readable prose with tables and code blocks as supplements. No frontmatter, no machine-consumable metadata. The spec is the source of truth for what to build; the plan references it but does not copy its content.

"Human-readable" here means the audience defined in [Target audience](../../shared/references/human-readable-summary.md#target-audience): a non-specialist or beginner who must be able to follow the spec without opening another file. So unpack every technical term, internal abbreviation, and code name at first use, and write each reference to an issue or an earlier decision so it still carries its meaning on its own. Before presenting the draft, run that section's proxy criterion and show the result.

```markdown
# {Domain Name}

## {Feature or Subsystem}

{Human-readable description of the requirements, constraints, and design decisions.}

### {Sub-section as needed}

{Details, examples, edge cases.}
```

## Integration with Plan

After spec generation, the wrap completion message includes the spec path. When `plan-create` runs later, it detects the spec in `docs/spec/` and populates the `**Spec:** {path}` field in the plan header automatically.
