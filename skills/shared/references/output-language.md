# Output Language Contract

The rule for which language appears in a skill's output artifacts and messages.

> **Consuming skills**: brief, decision-journal, doc-write, handoff
> (any skill that produces reader-facing artifacts or completion messages)

## The rule

A skill's output contains two kinds of text. Each follows a different rule.

| Kind | Rule | Examples |
|------|------|----------|
| **Contract tokens** | Stay in English as specified, regardless of the reader's language | Field names in templates and frontmatter keys, `kind` and `status` enum values, `evidence_refs` identifiers, slug components |
| **Reader-facing content** | Written in the language of the request | Summaries, explanations, field values, descriptions, the body of a completion message |

**"The language of the request"** means the language the user used when they invoked the
skill. When the material being explained is in a different language from the request,
follow the request — the reader is the one who asked.

## Template section headings

Section headings in output templates occupy the boundary between the two kinds.
Each skill decides whether a heading is a contract token or reader-facing text and
documents the decision in its own SKILL.md or template file.

The default classification:

- **Markdown headings (`## …`) in artifact files** → contract tokens (keep in English).
  They serve as stable anchors for cross-referencing, resumption, and machine parsing.
- **Labels in completion messages** → contract tokens (keep in English).
  They are fixed-format output, not prose.

## Authoring convention vs output language

SKILL.md files and shared references are written in English as an authoring convention
for a multi-agent repository. That convention says nothing about what language the
skill's output is in. Do not conflate the two.

## Relation to other contracts

- [lang-detect.md](lang-detect.md) detects the *programming* language of a project.
  This contract governs the *natural* language of a skill's output. They are independent.
