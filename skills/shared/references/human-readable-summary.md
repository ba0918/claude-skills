# Human-Readable Summary Shared Contract

This contract has two tiers, and a document that links here takes on only the tier it links for.

1. **The target-audience definition (general).** Who a human-facing document is written for, and
   when it is good enough. It governs every surface produced for a human to read — a spec, the
   human-facing sections of a plan, a completion report. A section whose primary consumer is an
   agent (such as a plan's implementation sections) sits outside this tier even when a human may
   audit it; the human-facing layer must then carry everything the human needs in order to decide.
   The tier runs from here through the "Target audience" section below.
2. **The completion-report summary block (specific).** The extra requirements for the
   utterance-sized summary block that the five report-producing skills (brainstorm wrap /
   issue create / handoff save / doc-write / design-guide) carry in their completion display.
   It runs from "Required elements" to the end.

Linking here for tier 1 does **not** impose the tier-2 obligations (the `📝 In short:` label, the
roughly-10-line bound, the summary-first placement). Those bind the listed report-producing skills only.

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

## Target audience

The reader of a human-facing document is **a non-specialist or a beginner** who holds none of the
project's background knowledge. The acceptance criterion: that reader can follow *what* and *why*
from this document alone, without opening any other file.

1. Unpack a technical term, an internal abbreviation, or a code name **on the spot, at first use**.
   Write a pointer to an issue number or a past decision so that it still carries its meaning
   without opening the thing it points at.
2. Technical subject matter is fine. What is banned is **unexplained assumed knowledge**, not
   technical content.
3. When plainness collides with a length bound, **drop the word, not the explanation**. Rephrase a
   term you cannot unpack within budget into everyday language. Keeping the term and deleting its
   explanation to fit the bound fails this criterion.
4. The real test is handing the document to a reader outside the project. Inside an automated loop,
   where no human is reachable, judge by the **proxy criterion**: enumerate every technical term,
   internal abbreviation, code name, issue number, and file path in the text, and show that each is
   unpacked at first use. One unexplained item fails. The proxy is a pre-filter, not a substitute —
   a human still makes the final call.

## Required elements

The summary block satisfies the following.

1. **Utterance-sized bullets on what was made / done** — state the core of the artifact in one to a few lines.
2. **Explicit points the human should confirm or rule on** — list the points needing approval or judgment, and what is undecided.
   If there are none, state "To confirm: none" explicitly (do not omit it).
3. **It must be a plain, digestible explanation** — not a pile of technical terms, internal abbreviations, or file paths;
   write it in words that let someone who has not read the artifact grasp "so what is it" in one read.
   Do not settle for over-compressed fragments or a list of noun-ended phrases.
   This is the **acceptance criterion** for the summary, and the before/after worked example below
   anchors it so implementers do not drift into subjectivity.
4. **An upper bound of about 10 lines** — bloat defeats the purpose. Ten lines is **an upper bound, not a lower bound**.

## Shared presentation and placement (summary-first)

- The summary block begins with the fixed label **`📝 In short:`**.
- Place it at the **very top** of the completion display (before file paths and Next Steps). The placement is
  visually unified across the five skills (the summary-first placement contract).

## Before / After worked example (an anchor for a subjective criterion)

"Graspable in one read" is an un-testable subjective criterion, so at least one before/after is
built into the contract to calibrate the implementers of the five skills onto the same level.

**Before (boilerplate only — the substance does not reach the human):**

```
✅ Idea saved!
📄 File: .agents/artifacts/ideas/20260721_foo.md
📋 Index: .agents/artifacts/ideas/idea-status.md
```

**After (with a summary — someone who has not read it can grasp "so what is it"):**

```
📝 In short: a proposal to stop making the completion report just "✅ + a path", and instead
   convey the substance of the artifact to the human in a few lines. A countermeasure to
   approval becoming a ritual in which the substance goes unread.
   To confirm: is narrowing the target skills down to 5 acceptable?

✅ Idea saved!
📄 File: .agents/artifacts/ideas/20260721_foo.md
📋 Index: .agents/artifacts/ideas/idea-status.md
```

The After does not reproduce the saved artifact verbatim. It states **only the core and the points to rule on** in plain
words, and leaves the file paths after the summary block as before.

## Rules for degradation and missing material

- When there is little substance to summarize, **fold it short** rather than filling up to the limit (a corollary of the ban on padding with boilerplate).
- Do not fabricate items that cannot be filled; state "none / undecided" explicitly.
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

## Creation-side leads (a distinct consumer class)

The echo rule above governs **completion summaries** — text restating what was just
produced. A second consumer class borrows only the reader standard: skills that write a
fresh human-readable lead into an artifact at creation time (the two-layer issue bodies
of the issue skill and the github-issue skill). For those leads this contract defines
**who must be able to read the text** ([Target audience](#target-audience)), not how the
text is produced — composing a creation-side lead may well require reading the source
material, so the no-extra-investigation rule does not apply to it.

## Good existing precedents

- **decision-journal** (content-echo type): echoes in one line the success criteria declared in the completion message.
- **codebase-review** (summary-first display type): displays `summary.txt` at the top on completion.

## Being referenced from the plan skills (the dependency-inversion anchor)

The completion display of the plan skills (plan-create / plan-implement / cycle) is implemented
**by referencing this contract**. This contract is the canonical source for the summary format,
and the plan skills' completion displays are subordinate to it.

Creation-side leads reference the [Target audience](#target-audience) section only:
the issue skill (create — body composition and `--summary` default) and the
github-issue skill (create — two-layer body composition).
