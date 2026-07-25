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
| `intent` | yes | Why these things belong together as one unit. **Not the author's motive** — see below |
| `plain_explanation` | yes | The explanation a reader who has not opened the source can follow |
| `risk` | yes | `low` / `medium` / `high`. See the scales below |
| `confidence` | yes | `low` / `medium` / `high`. See the scales below |
| `evidence_refs` | yes | At least one. Ids from the collected input |
| `items` | yes | One entry per line. Never a comma-joined paragraph |
| `concerns` | no | Anything noticed but not established. Ungrounded claims land here |
| `excerpts` | no | Verbatim source lines worth showing inline. See below |

### groups[].excerpts[]

A reader who has to leave the page to see what actually changed will not go. An excerpt puts
the lines themselves next to the explanation. Only ever a quotation of collected input — the
renderer escapes it and never interprets it.

| Field | Required | Notes |
|-------|----------|-------|
| `path` | yes | File the lines came from |
| `added` / `removed` | no | Line counts shown in the excerpt header |
| `hunk_header` | no | The `@@ ... @@` line, when the source is a diff |
| `lines` | yes | At least one entry |

Each entry in `lines`:

| Field | Required | Notes |
|-------|----------|-------|
| `text` | yes | The line, verbatim and unescaped. Never pre-escaped by the writer |
| `marker` | no | `+`, `-`, or a space. Defaults to a space |
| `old` / `new` | no | Line numbers. `null` on a side where the line does not exist |

Excerpts are quotation, not narration: a claim that rests on an excerpt still needs its
`evidence_refs`, and an excerpt never replaces `plain_explanation`.

### deferred[]

Material deliberately kept out of the initial view. Never a way to make something disappear —
the count stays visible and each entry is reachable.

| Field | Required | Notes |
|-------|----------|-------|
| `ref` | yes | The collected identifier. Machine-side only; attribution is checked against it and **it is never shown to the reader** |
| `label` | yes | What was withheld, named the way a reader would name it |
| `reason` | yes | Why it is not in the initial view |
| `kind` | no | Free-form. Not displayed |

`ref` and `label` are split because one identifier cannot serve both jobs. Attribution needs a
token that matches the collected input exactly; the reader needs to know what was left out.
Collapsing them means either the check loses its anchor or the page shows the reader something
like `s001-b4`, which is the internal vocabulary this format exists to keep off the page.

### comprehension_questions[]

Exactly three strings. Not scored, no input field, never blocks anything. Their only job is to
let a reader notice on their own that they cannot answer.

## What `intent` is not

`intent` answers **why these items form one group** — a statement about how the page is
organised, which you can always ground because you did the grouping. It reads like "the value
changed in one call site and nothing else moved, so it stands apart from the change that alters
which sources get processed".

It is not *why the author did this*. That question is usually unanswerable from the material,
and answering it anyway is the exact failure this format is built to prevent. When you know the
motive because the input states it, it belongs in `plain_explanation` with the evidence that
states it. When you only suspect it, it belongs in `concerns` as unverified. It never belongs
in `intent`, where it would be indistinguishable from the grounded part.

## The two scales

`risk` and `confidence` are required on every group, so leaving them to feel means the same
material gets a different reading on every run. Both are decided by a question with an
observable answer, not by impression. They measure different things and move independently: a
change can be well understood and still dangerous.

### risk — how costly it is for the reader to skim past this group

| Level | The group qualifies when |
|-------|--------------------------|
| `high` | Behaviour visible outside the system changes; data, schema or configuration changes in a way that is not straightforward to undo; authentication, permissions, money or personal data are touched; or deciding later closes off options that are open now |
| `medium` | Internal behaviour changes but is reversible, or the effect reaches beyond the files this group covers |
| `low` | Behaviour does not change (wording, documentation, tests, pure restructuring), and the effect stays inside this group |

Take the highest level any single item in the group reaches. A group is as risky as its worst
element — averaging hides exactly the item the reader needed to see.

### confidence — how far this explanation is carried by the input alone

| Level | The group qualifies when |
|-------|--------------------------|
| `high` | Every claim in `intent` and `plain_explanation` is readable directly from what `evidence_refs` points at |
| `medium` | The main claims are readable, but some part rests on material outside the input (a convention, a neighbouring file, general knowledge) |
| `low` | A central claim has no support in the input. Move the unsupported part to `concerns` and keep the level at `low` — lowering confidence is not a substitute for that move |

Confidence is about the explanation, not about the work being explained. A change you are sure
you understand gets `high` even when it worries you; that worry belongs in `risk` or
`concerns`.

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

**Which language to write in.** Everything a reader sees — `summary`, group fields, `deferred`
reasons, the questions — is written in the language of the material being explained and of the
request that started the run. When those differ, follow the request; the reader is the one who
asked. This document and `SKILL.md` are in English as an authoring convention for a
multi-agent repository, and that convention says nothing about what language the page is in.
Field names, `kind` values and `evidence_refs` identifiers are contract tokens and stay as
specified regardless.

- Lead with plain wording. Internal terms (`view`, `evidence`, `deferred`, `attribution`) never
  appear in initial labels.
- Expand an abbreviation or project-specific term the first time it appears.
- Being short is not the goal — being understood is. A compressed fragment that drops a
  guarantee or a scope limit is a failure, not a summary.
- `discussion` is comprehension support, not a ruling. Approval vocabulary must not appear on
  that page.
