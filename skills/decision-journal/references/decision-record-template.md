# The decision-record template

The form of a precedent / decision record for a decision or a technology choice. For the canonical protocol, see
[decision-protocol.md](../../shared/references/decision-protocol.md).

The purpose of this form is **not to mix observation, testimony, and conjecture**. The moment a blank is filled with conjecture, the record turns from archaeology into
post-hoc rationalization. **"Unrecoverable" is accepted as a legitimate conclusion.**

## Evidence-strength labels

Attach one of the following to each field and each claim, making the grade of the evidence explicit.

- **OBSERVED** — a fact confirmable directly from logs, commits, or physical evidence
- **REPORTED** — the person's own testimony (memory). Not a record made at the time
- **INTERPRETATION** — an interpretation or analysis by the interviewer or the writer
- **HYPOTHESIS** — a hypothesis. Causation unconfirmed. The more attractive the story, the more firmly this label stays on

## Two-point recording

Do not mix the prediction with the after-the-fact evaluation. Fill **the selection-time section** when work begins, and append **the outcome section** later.
The Start Workflow fills only the selection-time section and leaves the outcome section empty.

---

## The template proper

```markdown
# Decision record: {title}

**Created:** {YYYY-MM-DD HH:MM:SS}
**Success criterion:** {play | learning | product | business | unset (Start not run) | unrecoverable}
**Reach:** {a personal project (survival variable = motivation) | a company project (survival variable = operable headcount)}
**State:** {selection-time only | outcome appended | closed}

## The sealed section (Interview Workflow only. Fixed before the interview begins; never rewritten regardless of what the interview yields)

- **The current tentative hypothesis**: {what the interviewer expects going in}
- **Refutation and limiting conditions**: {what, if said, would retract or narrow the expectation}
- **What is unknown before the interview**: {what is to be confirmed}
- **The predicted ending category**: {if it turns out wrong, record that it was wrong}
- **Bias self-awareness**: {write down the pressure toward a shape or story you want the testimony to converge on}

## The selection-time section (fixed when work begins; never rewritten afterwards)

- **Candidates**: {every option that came up. Include the status-quo option and the rejected ones}
- **Constraints**: {premises and requirements. Record the investment ceiling (time, money) for play/learning here too}
- **The reason for the ruling**: {why this one was chosen}
- **The provenance of the reason**: {stated at the time | traces from the time | recalled afterwards | conjectured now}
- **Confidence**: {high | medium | low}
- **The stake** (by axis of impact — not by code size):
  - Data sensitivity: {…} / External impact: {…} / Ability to withdraw: {…} / Effort to rewrite: {…}
- **The rejection condition (made refutable)**: {what, if observed, means walking away from this bet. "Unset" if there is none}
- **The one question about a dependent language** (where applicable): {can you spend long hours with that language; does it become a learning asset}

## The outcome section (appended later; never mixed with the prediction)

- **The outcome vector** (do not collapse it into a single success/failure; split it per feature and per channel):
  - {axis 1}: {result} / {axis 2}: {result} …
- **Decision quality vs outcome quality**: {evaluate the soundness of the decision separately from whether the result was good. Do not hold up a lucky success as a model}
- **The closing form**: {continue | scale down | freeze + a re-evaluation date | partial recovery | natural fade (no explicit decision)}
- **A one-line note at the end**: {why it was stopped, and the conditions for resuming}

## The holding, its reach, and counterexamples

- **The holding**: {the reusable judgment extractable from this precedent}
- **Reach**: {which facts, if different, make it inapplicable}
- **Counterexamples**: {the conditions under which the holding does not hold, and any counterexample observed}
- **The re-evaluation trigger (with its counter-condition)**: {write it in the form "unless this threshold is crossed, stop again"}

## The evidence strength of each claim

{attach OBSERVED / REPORTED / INTERPRETATION / HYPOTHESIS to each major claim}

## Unverified / unrecoverable

- **Unverified**: {what should be confirmed by future cross-checking}
- **Unrecoverable**: {fields with no memory and no record that cannot be filled. Do not fill them with conjecture}
```

---

## Cautions when filling it in

- **The sealed section** is used only in the Interview Workflow. Omit it in Start / Capture.
- **How to choose the state**: for a record whose outcome was recovered by an Interview, use
  "closed" if the activity in question has already ended, and "outcome appended" if it is ongoing.
- **In a Start record made before work begins (with the technology not yet chosen)**, write the object of the decision itself in the "Candidates" field (for example, whether to build it at all, with adoption = build it), and record the technology candidates as "not yet chosen". Append them with capture once the technology choice is settled.
  Fields that presuppose a technology choice, such as "Confidence", may be "not applicable".
- **Do not judge success or failure with a single value at the project level.** Split residual value and the withdrawal decision per feature and per channel
  (a secondary feature can survive even when the central idea is rejected).
- **A quality improvement does not automatically invalidate the reason for rejection.** If the reason for rejection was "frequency or familiarity", the arrival of a new version is no grounds for returning to everyday use. Use the recorded reason for rejection as-is when evaluating a resumption trigger.
- When the stake is low (a small loss ceiling, an observable withdrawal point, little external impact, no exposure of confidential data, no lock-in of other systems),
  there is no need to fill in every field. A few lines of notes, or no record at all, is permitted. The duty to record is triggered by the stake.
