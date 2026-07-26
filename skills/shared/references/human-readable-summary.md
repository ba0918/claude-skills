# Human-Readable Summary Shared Contract

The shared contract for the "utterance-sized human-readable summary" that the **completion report** of
report-producing skills (brainstorm wrap / issue create / handoff save / doc-write /
design-guide and others) must carry.

A skill that embeds a summary block in its completion display links to this contract with a relative md link and
follows the required elements, presentation, anti-patterns, and degradation rules below.

## The principle of separating readers (the central proposition of this contract)

```
The canonical artifact (the saved file) = for the LLM. It may prioritize density, completeness, and machine readability
The completion report (the surface a human reads) = for the human. Make it a decision-dense summary readable in a few minutes
```

Never compress the canonical artifact. Make **only the surface a human reads** plain. Do not conflate the two by
thinning the canonical artifact, or by reproducing it verbatim in the completion report.

What lowers cognitive load is **plainness of explanation, not compression of line count**. Being short is
meaningless if it is a pile of fragments and jargon. Solve it by making the words easier, not by adding lines.

## Required elements

The summary block satisfies the following.

1. **Utterance-sized bullets on what was made / done** — state the core of the artifact in one to a few lines.
2. **Explicit points the human should confirm or rule on** — list the points needing approval or judgment, and what is undecided.
   If there are none, state 「確認事項: なし」 explicitly (do not omit it).
3. **It must be a plain, digestible explanation** — not a pile of technical terms, internal abbreviations, or file paths;
   write it in words that let someone who has not read the artifact grasp "so what is it" in one read.
   This is the **acceptance criterion** for the summary, and the before/after worked example below
   anchors it so implementers do not drift into subjectivity.
4. **An upper bound of about 10 lines** — bloat defeats the purpose. Ten lines is **an upper bound, not a lower bound**.
5. **A digestible explanation is a first-class requirement** — the same point as 3. Do not settle for
   over-compressed fragments or a list of noun-ended phrases.

## Shared presentation and placement (summary-first)

- The summary block begins with the fixed label **`📝 つまり:`**.
- Place it at the **very top** of the completion display (before file paths and Next Steps). The placement is
  visually unified across the six skills (the summary-first placement contract).

## Before / After worked example (an anchor for a subjective criterion)

"Graspable in one read" is an un-testable subjective criterion, so at least one before/after is
built into the contract to calibrate the implementers of the six skills onto the same level.

**Before (boilerplate only — the substance does not reach the human):**

```
✅ アイデアを保存しました!
📄 File: .agents/artifacts/ideas/20260721_foo.md
📋 Index: .agents/artifacts/ideas/idea-status.md
```

**After (with a summary — someone who has not read it can grasp "so what is it"):**

```
📝 つまり: 完了報告を「✅ + パス」だけにせず、生成物の中身を数行で人間に
   伝える案。承認が儀式化して中身が読まれない問題への対策。
   確認してほしい点: 対象スキルを 6 個に絞ってよいか。

✅ アイデアを保存しました!
📄 File: .agents/artifacts/ideas/20260721_foo.md
📋 Index: .agents/artifacts/ideas/idea-status.md
```

The After does not reproduce the saved artifact verbatim. It states **only the core and the points to rule on** in plain
words, and leaves the file paths after the summary block as before.

## Rules for degradation and missing material

- When there is little substance to summarize, **fold it short** rather than filling up to the limit (a corollary of the ban on padding with boilerplate).
- Do not fabricate items that cannot be filled; state 「なし / 未決定」 explicitly.
- If summary generation fails, do not emit a success summary.
- An echo is a **safe paraphrase**, not a verbatim transcription. Secret-looking values (tokens, keys,
  personal data) are kept out of the summary — omit them or replace them with a category name.

## Anti-patterns

- Verbatim reproduction or exhaustive enumeration of the artifact
- Padding with boilerplate (forcing the text up to the limit)
- Over-compressed fragments, a list of noun-ended phrases
- Using jargon and internal abbreviations without explanation
- Substituting a list of file paths for an explanation of the substance
- Creating a new transcription path for secrets

## It is an "echo", not a "regeneration"

The summary merely rephrases, at utterance size, information the LLM already holds just before completion
(the saved content itself). It requires no additional investigation or re-reading of files (which would make the
completion report heavy).

## Good existing precedents

- **decision-journal** (content-echo type): echoes in one line the success criteria declared in the completion message.
- **codebase-review** (summary-first display type): displays `summary.txt` at the top on completion.

## Being referenced from the plan skills (the dependency-inversion anchor)

The completion display of the plan skills (plan-create / plan-implement / cycle) is implemented by
agreement-ledger plan (`20260721082248`) Phase B2 **by referencing this contract**.
This contract is the canonical source for the summary format, and B2 is subordinate to it.
