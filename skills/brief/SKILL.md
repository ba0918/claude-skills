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

Run the candidate scan:

```
python3 {skill_dir}/scripts/brief_collect.py candidates --repo {repo_root}
```

1. Session context is always a candidate, so **the candidate set is never empty** — never
   answer that there is nothing to show.
2. Exactly one candidate — proceed, and state in one line which target was chosen.
3. Several candidates — ask once, listing each with its concrete size (file counts, item
   counts). Do not ask twice, and do not pick for the reader.
4. If the argument clearly names the conversation ("this chat", "what we just discussed"),
   take `discussion` without asking.

If the base revision cannot be resolved, drop the branch-range candidate and say so. A huge
diff computed against the wrong base is worse than an absent option.

The argument is the **perspective**, not the target. It steers emphasis ("focus on the risky
parts") and is carried into the model as `metadata.perspective`.

### Step 2 — Build the model

Collect and normalise the input, then write a model conforming to
[references/brief-model.md](references/brief-model.md). You produce the model **and nothing
else** — no markup, no styling, no colour choices.

Writing rules, in priority order:

- **Ground every claim.** `intent` and `plain_explanation` need `evidence_refs` pointing at
  real hunks or sections. A claim you cannot ground does not belong in the body — move it to
  `concerns` as unverified.
- **Plain and complete are separate requirements.** Text that reads easily because it dropped
  a precondition, a scope limit or a guarantee is a failure, not a summary. Whatever you leave
  out goes to `deferred` with a reason, never into silence — and name it there the way a reader
  would name it, not by the identifier the collector produced. The identifier stays in `ref`
  for the attribution check and never reaches the page.
- **Keep internal vocabulary off the page.** `view`, `evidence`, `deferred` and `attribution`
  are contract words; readers get plain labels. Expand any abbreviation on first use.
- **One item per line.** Never join items into a comma-separated paragraph.
- **Quote what matters.** When a claim rests on specific lines, put them in `excerpts` so the
  reader does not have to leave the page. Pass the source text verbatim — escaping is the
  renderer's job, and pre-escaping it corrupts the output.
- **Rate risk and confidence from the scales, not from impression.** Both are required on every
  group, so deciding them by feel gives the same material a different reading each run. The
  scales in [references/brief-model.md](references/brief-model.md) turn each into a question
  with an observable answer. They move independently — well understood and still dangerous is a
  normal combination.
- **Write in the reader's language.** Reader-facing text follows the language of the material
  and of the request. This file being in English is an authoring convention for a multi-agent
  repository; it is not the output language.
- **Exactly three comprehension questions.** Not scored, no input field, they block nothing.
  Write questions that cannot be answered without having read the page.

### Step 3 — Validate, then render

Validation is deterministic and runs first. It enforces the schema, reference integrity and
**attribution completeness** — the mechanical guarantee that nothing silently fell out of the
page.

```
python3 {skill_dir}/scripts/brief_render.py validate --model {model.json} --inputs {inputs.json}
python3 {skill_dir}/scripts/brief_render.py render --model {model.json} --inputs {inputs.json} --out {out.html} --open
```

`--inputs` carries the collected identifiers and is required on **both** commands for every
view except `discussion` — rendering validates first, so omitting it there fails the same way
validation does. `discussion` has no mechanical input to check against and takes neither.

Fix reported violations by fixing the model. **Never loosen the check** — an unassigned hunk
is a hole in the page, and `deferred` is not an escape hatch for it.

If a credential-shaped string is detected, rendering stops. Show the reader what was found and
let them decide; only pass `--allow-secrets` after a human has looked. Do not add the flag to
get past the message.

Artifacts go to the resolved store:

```
{artifacts}/reviews/{run_id}_brief-model.json
{artifacts}/reviews/{run_id}_brief.html
{artifacts}/reviews/brief-log.md
```

### Step 4 — Show it and close the loop

**Opening the page is part of the job, not a bonus.** Handing over a path ends with the page
unread, which defeats the whole measurement.

- The renderer detects the platform's opener. If it reports that it could not open the page,
  and the command environment confines execution, **retry outside that confinement before
  giving up** — a restricted environment blocks the opener while leaving the rest working, so
  a single failed attempt is not evidence that opening is impossible.
- If it genuinely cannot open, say so explicitly and give the path. Never let a silent
  downgrade to path-handover pass as success.

Then let the reader talk back in this same session — that is the whole feedback path, and the
reason no export machinery exists.

Append one line to the run log:

```
| 日時 | view | 対象 | 読んだか | 指摘が出たか | ★画面がなければ出なかった指摘か |
```

The ★ column is the decisive one. At five entries it settles three different outcomes that
otherwise get confused: ★ twice or more means the page earns its wiring into other workflows;
★ never means the page is not the answer; frequently forgetting to invoke means the page is
fine and the trigger is what is missing.

## Design system

Visual quality is settled once, as an asset, so it does not vary per run. The page is styled
from `assets/tokens.css` plus the code-surface extension in `assets/tokens.brief.json`, and
the renderer holds no colours or dimensions of its own.

`assets/tokens.css` is a distribution copy — the authoring source is `DESIGN.md` and
`.design/` at the root of this repository, which do not exist where the skill is installed. A
repository check requires the two to stay byte-identical, so **never hand-edit the copy**:
change the design source, regenerate, and let the check confirm.

## References

- [references/brief-model.md](references/brief-model.md) — model schema, per-view differences,
  evidence, excerpts and attribution rules
