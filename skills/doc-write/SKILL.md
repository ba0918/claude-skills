---
name: doc-write
description: LLMとのやり取り・調査結果・Web調査をリーダブルなドキュメントに昇華するスキル。Mermaid図付きの構造化ドキュメントを生成する。「ドキュメント書いて」「まとめてドキュメントに」「doc-write」で起動。
---

# Doc-Write

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

Turn LLM exchanges, investigation results, and web research into readable documents.
The skill adjusts granularity to the intended audience, selects a template automatically,
generates Mermaid diagrams, and raises quality through a feedback loop.

## Boundary with neighbouring skills

| Skill | Role | Output |
|--------|------|------|
| `brainstorm-wrap` | Lightweight notes from a sparring session | `.agents/artifacts/ideas/` |
| `investigate` | Investigation report on a problem | Printed in the conversation |
| **`doc-write`** | **Turning knowledge into a readable document** | **`docs/writings/`** |

Feeding investigate's output into doc-write is an intended combination.

## Workflow selection

The leading keyword of $ARGUMENTS selects the workflow:

- `resume` → **Resume workflow** (re-edit an existing document)
- (none, or a theme string) → **Write workflow** (the main workflow)

---

## Write workflow (main)

### Phase 1: Requirements

1. **Confirm the intended audience** (mandatory question)
   - Always ask the user: 「このドキュメントの想定読者は誰ですか？（例: 自分用メモ / チームメンバー / 外部発表）」
   - Adjust granularity and how much terminology you explain to that audience

2. **Identify the theme**
   - If $ARGUMENTS carries a theme, use it
   - Otherwise infer the theme from the current context (the conversation)
   - If you cannot infer it, ask the user

3. **Determine the input source**
   Decide between these three:
   - **(a) Current context**: summarising discussion or investigation from the conversation
   - **(b) Existing files**: consolidating past notes or reports (get the path from
     $ARGUMENTS or from the user)
   - **(c) Web research**: researching a given theme and documenting it
     - Judge the depth from context:
       - 「調べて」「まとめて」 → light research (a few primary sources)
       - 「徹底的に調べて」「深く調査して」 → deep research (comprehensive, multiple sources)
     - **When web research fails**: notify the user and propose switching to manual input

4. **Select the template automatically**
   Pick by content:
   - **Tech note**: technical knowledge, procedures, explanations → [references/tech-note-template.md](references/tech-note-template.md)
   - **ADR (Architecture Decision Record)**: a record of a decision → [references/adr-template.md](references/adr-template.md)
   - **Discussion summary**: a summary of a discussion → [references/discussion-summary-template.md](references/discussion-summary-template.md)
   - If the choice is ambiguous, ask the user

### Phase 2: Generating the document

1. Load the template
2. Collect and organise the information from the input source
3. Generate the document under these rules:
   - Write at the granularity the intended audience needs
   - Insert Mermaid diagrams where they help (follow [references/mermaid-guidelines.md](references/mermaid-guidelines.md))
   - Mermaid diagrams are not mandatory — insert one only when a diagram earns its place
   - Embed metadata in the frontmatter (title, audience, template, created, updated)
4. Generate the slug: `yyyymmddhhmmss_{kebab-title}` (date +%Y%m%d%H%M%S)
5. Output path: `docs/writings/{slug}.md`
   - Create `docs/writings/` with `mkdir -p` if it does not exist

### Phase 3: Feedback loop

1. Show an outline of the generated document:
   ```
   📄 ドキュメントを生成しました: docs/writings/{slug}.md

   ## 構成
   {見出し一覧}

   修正・追加したい点はありますか？（「OK」で確定）
   ```
2. Take the user's feedback
3. If there is feedback, revise and confirm again (loop)
4. End the loop on 「OK」「問題ない」「大丈夫」 or similar
5. Completion message. Lead with a summary block per the
   [human-readable summary contract](../shared/references/human-readable-summary.md),
   summary-first, stating in one plain line what this document explains (the outline was
   already shown in the feedback loop, so keep this minimal — just echo the gist in plain
   words). Keep confidential values out of the summary:
   ```
   📝 つまり: {この文書を読んでいない人にも「つまり何を説明する文書か」が伝わる平易な 1 行}

   ✅ ドキュメントを保存しました!
   📄 File: docs/writings/{slug}.md
   ```

### Error handling

- **Empty input**: ask the user to re-enter
- **Web research failure**: notify the user and propose switching to manual input
- **Ambiguous template choice**: ask the user

---

## Resume workflow (re-editing an existing document)

### Steps

1. Identify the target from the $ARGUMENTS following the `resume` keyword
   - A file path: load that file
   - A slug: load `docs/writings/{slug}.md`
   - Nothing specified: list the files under `docs/writings/` and have the user choose
   - `docs/writings/` does not exist, or holds no files: show 「まだドキュメントがありません」 and stop
   - The specified file does not exist: show the file list under `docs/writings/` and exit
     with an error

2. Read the metadata from the file's frontmatter (audience, template, ...)

3. Summarise the document and show it:
   ```
   📄 ドキュメント "{title}" を読み込みました。
   👥 想定読者: {audience}
   📝 テンプレート: {template}

   何を修正・追加しますか？
   ```

4. Take the user's revision instructions

5. Revise the document accordingly
   - Update `updated` in the frontmatter to today's date
   - Add or revise Mermaid diagrams as needed (following the guidelines)

6. Feedback loop (same as Phase 3 of the Write workflow)

---

## File structure (generated in the project using this skill)

```
docs/writings/
  yyyymmddhhmmss_{slug}.md  - individual documents
```

## Templates

- **Tech note:** [references/tech-note-template.md](references/tech-note-template.md)
- **ADR:** [references/adr-template.md](references/adr-template.md)
- **Discussion summary:** [references/discussion-summary-template.md](references/discussion-summary-template.md)

## Mermaid diagram guidelines

- [references/mermaid-guidelines.md](references/mermaid-guidelines.md)

## Notes

- Start with the three template types and add more as needed
- Start with minimal Mermaid guidelines and grow them through use
- investigate's output can serve as an input source
- The frontmatter holds the document's metadata (intended audience, template type, updated
  date)
