---
name: brief
description: 変更・実装計画・引き継ぎ・進行中の会話を、人間の判断順に再構成した自己完結 HTML として可視化しブラウザで開くスキル。LLM 向けに書かれた長い文書や大きな差分を「つまり何が起きたか」から読める形へ組み替え、意図別グループ・平易な解説・根拠・確認の質問を提示する。既存ワークフローへ配線せず手動起動だけで動く。「brief」「わかりやすく教えて」「解説画面」「今の会話を整理して」「変更内容を可視化」「実装計画を解説して」で起動。
---

# Brief

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md).
Resolve and validate the store before reading or writing artifacts.

Turn work that is written for machines into a page a human actually reads.

The problem this owns is **ceremonial approval**. When plans, diffs and handoffs are written
for LLM consumption, the human stops reading them and approves anyway. Every downstream
machine check is then anchored to a rubber stamp. This skill rebuilds that material in the
order a human decides things, explains it in plain language with evidence, and puts it on a
page the reader is willing to open.

**Manual invocation only.** This skill is not wired into any other workflow. That is
deliberate — the manual phase exists to separate two different failures that look alike once
automated: *the reader opens it and still does not read* (the page is not the answer) versus
*the reader never remembers to open it* (the page is fine, the trigger is missing).

## Scope

| In | Out (deferred) |
|----|----------------|
| Target resolution from repository state | Auto-invocation from other skills |
| Model generation, validation, rendering | Persisted approval state |
| Opening the page in a browser | Approval side effects such as commit or merge |
| Feedback through conversation | Feedback export files and copy text |
| One log line per run | Shadow auto-pass |

## Views

The model carries a `view` discriminator. Group semantics differ per view; **the renderer does
not branch**. Writing a separate template per view multiplies maintenance by the number of
views, so all view differences live in the model.

| View | Input | A group means |
|------|-------|---------------|
| `change` | A diff (unstaged, staged, branch range, commit range, document before/after) | A set of edits sharing one intent |
| `document` | A plan, idea memo or other structured document | A section regrouped into something a human can rule on |
| `orientation` | A handoff file or branch state | Where the work stands and what comes next |
| `discussion` | The current session context | A topic, with what is settled and what is not |

`discussion` needs no input collection — the material is already in context. It therefore runs
without `brief_collect` and is the first view to work end to end.

## Workflow

### Step 1 — Resolve the target

Never infer the target from the wording of the argument. A phrase like "explain what we did"
does not distinguish unstaged edits from a branch range from a plan, and the reader is not
thinking in those terms either. Decide from repository state instead.

1. Scan for candidates. Session context is always a candidate, so **the candidate set is never
   empty** — never answer that there is nothing to show.
2. Exactly one candidate — proceed, and state in one line which target was chosen.
3. Several candidates — ask once, listing each with its concrete size (file counts, item
   counts). Do not ask twice.
4. If the argument clearly names the conversation, take `discussion` without asking.

The argument is the **perspective**, not the target. It steers emphasis ("focus on the risky
parts"), and is carried into the model as `metadata.perspective`.

### Step 2 — Build the model

Produce a model conforming to [references/brief-model.md](references/brief-model.md).

- Every `intent` and `plain_explanation` must be backed by `evidence_refs` pointing at real
  hunks or sections. A claim you cannot ground does not belong in the body — record it under
  `concerns` as unverified.
- Plain language and information preservation are **separate** requirements. Output that reads
  easily because it dropped a precondition or a scope limit fails.
- Do not expose internal vocabulary in reader-facing labels.
- Write exactly three comprehension questions. They are not scored and take no input.

### Step 3 — Validate and render

Validation is deterministic and runs before rendering. It enforces schema, reference integrity
and **attribution completeness** — the mechanical guarantee that nothing silently fell out of
the page. Rendering produces a single self-contained file with no network references, styled
only from tokens.

### Step 4 — Show it and close the loop

Open the page with the platform's default opener. If opening fails, still report success and
give the path. Then let the reader talk back in this same session — that is the whole feedback
path, and the reason no export machinery exists.

Append one line to the run log. The decisive column is **whether a remark would have surfaced
without the page**. That column, not overall impressions, decides whether this gets wired into
other workflows later.

## Design system

The rendered page follows [DESIGN.md](../../DESIGN.md) and consumes design tokens. The renderer
must not hardcode colours or dimensions — visual quality is settled once, as an asset, so it
does not vary per run.

## References

- [references/brief-model.md](references/brief-model.md) — model schema, per-view differences,
  evidence and attribution rules
