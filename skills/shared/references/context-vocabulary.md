# CONTEXT.md (Shared Vocabulary Layer) Contract v1

The contract for the **shared vocabulary layer** that sits beneath the agreement ledger
([agreement-ledger.md](agreement-ledger.md)). A ledger claim (`claim`) depends on words, and
when a word's meaning drifts the agreement drifts with it. CONTEXT.md pins down "what this
word refers to in this project", and ledger rows reference it through `term_refs`.

The ledger holds "the state of claims"; CONTEXT.md holds "the state of words" — a two-layer
structure.

## Vocabulary Entry Format (human-facing CONTEXT.md)

Each vocabulary entry in the human-facing CONTEXT.md carries the following (borrowed from the
CONTEXT.md notation of rigortype/rigor):

- The **term** and an **entry ID** (the stable ID that `term_refs` references)
- A **usage / behaviour declaration**: separates "a promise about how the word is used" from
  "a definition of behaviour"
- **Vocabulary-specific state**: `settled` / `tentative` / `conflicting` / `retired` (next section)
- A **Trapped terms section**: explicitly quarantines words whose meaning splits easily or is
  prone to misreading
- An **implementation-reality flag**: attached to words where the definition and the current
  implementation have diverged
- **Cross-references to related rulings**: from the word to the related ledger row IDs

## Vocabulary-specific State

| State | Meaning |
|------|------|
| `settled` | The meaning has been ruled on. Safe to depend on |
| `tentative` | A tentative meaning. Still open to reconsideration |
| `conflicting` | Multiple meanings are in conflict and unresolved. Claims depending on this word are unstable |
| `retired` | A retired word. References to it should be resolved away |

## Machine-readable Vocabulary File (the format `ledger_lint` reads)

The undefined-`term_refs` check in `ledger_lint.py` reads a vocabulary file in the JSON format
below. It lives separately from the human-facing CONTEXT.md, as a projection for machine
verification (the human-facing CONTEXT.md is the source of truth; drift in the projection is
managed operationally — docgen-style generation is a future consideration).

The top level is an object with exactly these 2 keys:

| Field | Type | Required | Description |
|-----------|-----|------|------|
| `schema_version` | `integer` | `required` | Fixed at `1` for v1 |
| `terms` | `array[object]` | `required` | The array of vocabulary entries |

Each `terms[]` entry:

| Field | Type | Required | Description |
|-----------|-----|------|------|
| `id` | `string` | `required` | Vocabulary entry ID. A ledger row's `term_refs` references this ID |
| `term` | `string` | `required` | The word itself |
| `state` | `string` | `required` | Vocabulary-specific state. enum: `settled` / `tentative` / `conflicting` / `retired` |

Given a vocabulary file, `ledger_lint` verifies via O(1) membership that each ledger row's
`term_refs` is contained in the set of vocabulary `id`s (when `--context PATH` is not given,
`term_refs` verification is skipped). Beyond the vocabulary `id`, the lint also reads `state`
(the vocabulary-specific state) and treats an `AGREED` row that depends on a `conflicting` / `retired`
word as a derived detection of pending-vocabulary (see the pending-vocabulary section and the
dual-state consistency rule in [agreement-ledger.md](agreement-ledger.md)).

**Enforcement of the `state` enum**: the loader does not reject an out-of-enum value. A
vocabulary file is auxiliary input, and one bad state must not abort the whole ledger run.
Instead the enum is enforced **at the point of use**: when an `AGREED` row depends on a term
whose `state` falls outside the enum, `ledger_lint` emits the `unknown-term-state` advisory
(report-only). Without this check an unrecognised state would drop out of the unstable-dependency
detection silently, and the vocabulary layer would look clean precisely where it is unreadable.
The advisory is also the migration path off the pre-v1 Japanese state values
(`確定` / `暫定` / `競合中` / `廃語`), which are no longer part of the enum.

## Vocabulary Generation Flow (a by-product of extract — one pass, two streams)

Vocabulary is not "static input a human fills in beforehand"; it is generated as a
**by-product of extract archaeology**. A single extract pass emits two streams: **agreement
candidates** (ledger rows) and **vocabulary candidates** (CONTEXT entries). Words are the
premise layer of agreement, and an agreement containing unknown words cannot be safely
depended on until the vocabulary is settled.

Generation has 2 modes, treated as batch application and streaming application of the same
detector:

- **cold-start (batch)**: run vocabulary extraction as a batch over the existing corpus
  (documents, code, conversation logs) and mechanically select the **top N words that are both
  high-frequency and load-bearing** (words you would proceed on false premises without
  knowing). Extract them mechanically by frequency and load-bearing-ness rather than
  hand-picking them. The LLM proposes a definition for each word, and **the human only confirms
  or edits** (the LLM does not finalize definitions).
- **steady-state (streaming)**: grow the vocabulary from **comprehension-repair events** during
  operation. A complete vocabulary detector is the pair of human and LLM — the human's "what is
  that?" (catching the human's gap) and the LLM's "I am treating this word as meaning X, is
  that right?" (catching the LLM's gap, i.e. the silent side). It picks up classes of
  comprehension-repair events, not regular expressions.

**Admission filter**: promoting every word picked up into the vocabulary makes it bloat. Only
**recurring words** or **load-bearing words** pass through as candidates.

### Out-of-session Auto-growth (candidates and freshness are automated; confirmation is human)

Because domain knowledge can be updated at any time, **harvesting and freshness management of
the vocabulary are automated**:

- Detect new words via **incremental re-runs** of the extract batch and push them onto the
  candidate queue.
- **Repurpose the undefined-word detection of `ledger_lint --context` for candidate harvesting**
  (an undefined reference is a signal of "a load-bearing word not yet turned into vocabulary").
- Automatically mark **retirement candidates by reference record** (words no longer `term_refs`-ed
  by any ledger row) and **`conflicting` candidates by divergence between definition and reality**.

However, **what may be automated stops at "candidates (tentative) and freshness"**. Finalizing
vocabulary is **always done by a human** (even for vocabulary, the LLM is a proposer and cannot
become the approver). Candidates are worked off (confirm / edit) at the start of a ruling
session, or at the plan-creation gate. Do not build out auto-promotion logic or admission
threshold tuning; adjust them with iterate after pilot measurements
(consistent with §E of [agreement-ledger.md](agreement-ledger.md)).

## Dual-state Consistency Rule (PROVISIONAL)

An `AGREED` row referencing a `conflicting` / `retired` word cannot be protected from drift by
cross-references alone, so **lint / status detect it as a re-ruling candidate** (derived
detection (b) of pending-vocabulary; see the pending-vocabulary section of
[agreement-ledger.md](agreement-ledger.md)). This detection rule is PROVISIONAL in v1 and
**stays advisory (report-only)**. It will be finalized after the pilot results from
automation-visualize. By contrast, detecting an `AGREED` row whose `term_refs` points at a
CONTEXT-undefined entry (derived detection (a)) is a **finalized implementation**.

## The Boundary Question (CONTEXT.md or the ledger)

Whether something belongs in CONTEXT.md or in the ledger is decided by this question:

> **Is it an explanation of interpretation, or a ruling on a choice?**

- **Sharing an interpretation** — "this word means this" → CONTEXT.md
- **Ruling on a choice** — "do we take A or B" → a ledger row (which carries state)

## Survival Management by Reference Record

Left alone, vocabulary bloats. A word **no longer `term_refs`-ed by any ledger row** becomes a
candidate for re-examining its survival (a "is this still needed?" check, not a deletion). Keep
resident only the words involved in "decisions you would get wrong without knowing them";
everything else is an index lookup (the practical reality of the LLM-side context budget).
