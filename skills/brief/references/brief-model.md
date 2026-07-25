# Brief Model

The contract between model generation (a language model writes it) and rendering (a
deterministic script consumes it). Everything the page shows comes from this structure; the
renderer adds no content of its own.

## Top level

```text
metadata                  required
summary                   required
groups[]                  required, at least 1
deferred[]                optional
comprehension_questions[] required, exactly 3
```

### metadata

| Field | Required | Notes |
|-------|----------|-------|
| `schema_version` | yes | Integer. Currently `1` |
| `run_id` | yes | Identifies the run; used in artifact filenames |
| `view` | yes | `change` / `document` / `orientation` / `discussion` |
| `source_kind` | yes | Where the material came from, e.g. `unstaged`, `branch`, `plan`, `handoff`, `session` |
| `source_ref` | no | Revision range, file path, or absent for `session` |
| `perspective` | no | The invocation argument, verbatim |

### summary

| Field | Required | Notes |
|-------|----------|-------|
| `one_liner` | yes | One utterance-sized line. What happened, in plain words |
| `purpose` | yes | Why this exists |
| `scope_note` | yes | What is covered and what is explicitly not |

### groups[]

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Unique within the model |
| `title` | yes | Reader-facing. No internal vocabulary |
| `kind` | yes | See per-view vocabulary below |
| `intent` | yes | Why this group exists as one unit |
| `plain_explanation` | yes | The explanation a reader who has not opened the source can follow |
| `risk` | yes | `low` / `medium` / `high` |
| `confidence` | yes | `low` / `medium` / `high` |
| `evidence_refs` | yes | At least one. Ids from the collected input |
| `items` | yes | One entry per line. Never a comma-joined paragraph |
| `concerns` | no | Anything noticed but not established. Ungrounded claims land here |

### deferred[]

Material deliberately kept out of the initial view. Never a way to make something disappear —
the count stays visible and each entry is reachable.

| Field | Required |
|-------|----------|
| `ref` | yes |
| `reason` | yes |
| `kind` | no |

### comprehension_questions[]

Exactly three strings. Not scored, no input field, never blocks anything. Their only job is to
let a reader notice on their own that they cannot answer.

## Evidence rules

- `evidence_refs` entries must exist in the collected input. A dangling reference fails
  validation — it means the model invented material.
- A group with no evidence fails validation.
- A claim that cannot be grounded must not appear in `intent` or `plain_explanation`. Move it
  to `concerns`.

## Attribution completeness

Grouping is a judgement call and cannot be checked mechanically. **Whether anything was
dropped can be.** This is the load-bearing guarantee of the format.

| View | Rule |
|------|------|
| `change` | Every collected hunk belongs to **exactly one** group. Unassigned fails; assigned twice fails. `deferred` is not an escape hatch here |
| `document` | Every top-level section is either in a group or in `deferred` with a reason |
| `orientation` | Every open item from the input is either in a group or in `deferred` |
| `discussion` | No mechanical input exists, so attribution cannot be checked. Instead **at least one group must have kind `undecided`**, and no `deferred` entry may be of kind `undecided` |

The `discussion` rule targets the specific failure mode of conversation summaries — settled
points are easy to write down and survive, unsettled ones are vague and quietly vanish, leaving
the reader believing everything was decided.

## Per-view `kind` vocabulary

| View | Allowed kinds |
|------|---------------|
| `change` | `feature`, `fix`, `refactor`, `docs`, `test`, `chore` |
| `document` | `goal`, `design`, `constraint`, `risk`, `step`, `acceptance` |
| `orientation` | `done`, `inflight`, `next`, `blocked` |
| `discussion` | `topic`, `decided`, `undecided`, `option` |

## Reader-facing language

- Lead with plain wording. Internal terms (`view`, `evidence`, `deferred`, `attribution`) never
  appear in initial labels.
- Expand an abbreviation or project-specific term the first time it appears.
- Being short is not the goal — being understood is. A compressed fragment that drops a
  guarantee or a scope limit is a failure, not a summary.
- `discussion` is comprehension support, not a ruling. Approval vocabulary must not appear on
  that page.
