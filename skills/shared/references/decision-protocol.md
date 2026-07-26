# Decision Protocol (decision-making protocol v1)

The shared contract for operating architecture and technology-selection decisions in a "case law rather than a constitution" style.
Instead of writing universal normative rules up front, it accumulates precedents from real decisions and promotes to a
provisional norm only those rejection reasons that recur across several precedents — an inductive construction.

Every clause of this document is **a "process hypothesis v1", not a "norm"**. It was generated from five cases from a single
person (a retrospective interview of precedents) and is no more than a hypothesis to be tried next in a falsifiable form.
Do not call it a norm until it has been validated by prospective application (actually using it on a new project and observing
whether its predictions hold). Do not count the number of cases as supporting votes
(the samples are not independent; they are a case series from the same person, a nearby period, and the same development environment).

## Positioning — juxtaposed, not superordinate

This protocol is **not a layer above** [design-principles.md](./design-principles.md) (testability),
[testing-anti-patterns.md](./testing-anti-patterns.md), or
[information-placement.md](../../../rules/information-placement.md) (the four quadrants of information placement).
It is a juxtaposed contract that applies in a different situation. They cross-reference each other but are not layered.

- Code philosophy (design-principles) works by deduction from the single objective function of "testability"
  (high frequency, low context, deducible).
- Decision-making is the exact opposite: low frequency, high context, not deducible. "Decision Iron Laws" in the same form
  would be either too abstract to decide anything or a mistaken absolutization. This protocol therefore has no Iron Law;
  its minimal core is only **the up-front rejection of bad bets and the guarantee of falsifiability**.
- Its origin is the homelessness of architectural rationale, which does not fit the four quadrants of information placement
  (Code=How / Tests=What / Commit log=Why / Comments=Why not). That calls for a fifth home (precedents / decision records).

## Do not keep it resident (a countermeasure to instruction dilution)

The body of this protocol, the precedents, and the per-language addenda **must not be placed in resident context**. Load them when needed.
The only thing that may be resident is a one- or two-line router such as the following (intended to be pasted into each project's `AGENTS.md` or equivalent).

> Before ruling on a technology-selection or architectural bet, collate it once against the three passing conditions and the
> one-line pre-start protocol of decision-protocol.md. For a low-stakes bet, a few lines of record are enough.

Keeping the whole body resident dilutes the other resident instructions and lowers collation accuracy instead.

## Process hypotheses

### 1. The one-line pre-start protocol — declare the success criterion

Before starting, pick one success criterion from the four categories **"play / learning / product / business"** and leave one line about it.
This is an encoding that prevents the same quiet abandonment from becoming either "a failure" or "legitimate exploration".
If the success criterion is not fixed in advance, either narrative can be written after the fact, and the quality of the decision becomes impossible to evaluate.

- Keep the options at four (excessive classification becomes friction at start).
- The most important survival variable of a personal project is motivation, and "does it look fun" is a legitimate first-class criterion.
  Declaring "play" is not inferior. A low-stakes choice made out of curiosity can stand on its own.

### 2. For a product purpose, validate the enabling condition up front with the cheapest E2E spike

If the success criterion is "product" or "business", validate the product's **indispensable enabling condition**
(the premise without which the product is meaningless) up front, with the cheapest end-to-end spike. This avoids the failure in which
investment skews toward enjoyable, immediately rewarding work (the game part, elaborate design) and the goal is lost
while the enabling condition goes unvalidated.

- Give the spike staged pass conditions: one fetch → E2E → repeated runs and restarts → environment differences and long durations.
  Do not confuse "it worked once" with "it holds stably".
- For environment-dependent tooling (crossing operating systems or display stacks), put a spike that pushes real data across the
  boundary before detailed language-level design. That said, "language selection is always low in importance" is an over-generalization
  (counterexamples: hard real time, resident services where memory safety is the essence, dependence on a specific SDK,
  business systems where hiring and handover dominate).

### 3. The three passing conditions (uniqueness of the right answer is not required)

A bet must pass the following three conditions. **Accept that there is no unique right answer among the options that pass**
(proving a unique optimum in advance is not required).

1. **Survivability** — even on failure the loss stays within tolerance (a ceiling on regret is drawn).
2. **Verifiability** — success or failure can be observed within a deadline (there is a means of observation and a deadline).
3. **Exitability** — the time, cost, and owner of withdrawal are stated explicitly.

**Bad bets can be rejected up front by these three conditions** — unmet constraints, no comparison against the status-quo option,
no means of observation, no withdrawal condition. Do not make reversibility itself the maximization goal
(it breeds abstraction layers for interchangeability, dual operation, and deferred decisions, and it cannot account for the benefit of
deliberate irreversibility — deep optimization for a specific technology).
Treat reversibility not as a property at a point in time but as a quantity that decreases over time (the speed of lock-in).

### 4. Asymmetric design — the reason for choosing may be intuitive; only the rejection condition must be falsifiable

- **The reason for choosing** may be intuitive (curiosity, enjoyment). Especially when the stakes are low and withdrawal is possible.
- **Only the rejection condition** must be observable and falsifiable. Write in advance what observation would make you walk away from this bet.

This asymmetry is the heart of it. Rather than interrogating the quality of the reason, fix in advance the condition under which you will know it went wrong.

### 5. The closing procedure — do not make it binary

Do not reduce the ending to "continue or discard". A binary structure strengthens attachment (the stagnation of "too good to throw away").
Include the following among the options.

- **Shrink** (keep it at a smaller scale, e.g. as an internal library)
- **Freeze + a re-evaluation date** (stop for now, with an explicit date)
- **Partial salvage** (keep only the technical assets and the failure cases, and disable the functionality)

And **leave a one-line note at the end**: why it was stopped, and the condition for resuming. In a fade-out with no moment of decision,
"on what grounds it was set aside, and the condition for resuming" is not left behind, and the knowledge of the ending is lost
(a definite loss observed repeatedly in the precedents).

- Make the re-evaluation trigger paired with a condition: "if this threshold is not exceeded, stop again". A quality improvement does not
  automatically invalidate the rejection reason. If the rejection reason was not "quality" but "frequency, familiarity", the arrival of a new
  version is not grounds for returning to regular use (a weak bet). Use the recorded rejection reason directly when evaluating the resumption trigger.

### 6. The one question about a subordinate language

When an upper-level choice (framework, dependency) drags a language along with it, insert exactly one question before starting:
**"can I spend long hours with that language, and will it become an asset to my own learning?"**

The cost of compatibility with a subordinate language is not evaluated at selection time; it surfaces only after use begins. Technology selection in a
personal project has the composite purpose of "for this project" and "for my own learning assets", and a lack of learning value can become a continuation cost
(damage to motivation). Even when a language does not determine *technical* success or failure, it affects *continuation* through the motivational path.

### 7. Making the scope explicit — separate personal projects from corporate ones

A hypothesis being promoted **must always state its scope (personal / corporate)**, because the survival variables differ.

- **Personal projects**: the survival variable is motivation. Interruption is the normal condition (tolerance to being left alone and the cost of relearning become selection axes).
- **Corporate projects**: the survival variable is operations, hiring, and personnel to whom it can be handed over. External compulsion guarantees continuation, so it "does not stop",
  but the influence of motivation does not disappear — its output shifts to the quality of the work, the speed, and the quality of maintenance (hypothesis).

**Unified hypothesis (HYPOTHESIS)**: what technology selection is really asking is "is this a choice under which the human resources that keep this system going will not run dry" —
motivation for an individual, operable personnel for a company. Generalizing across the two scopes is nevertheless forbidden.

## The separation principle for records

When writing a precedent or a decision record, do not mix the following (for the detailed field layout, see
[decision-record-template.md](../../decision-journal/references/decision-record-template.md) of the decision-journal skill).

- **Separate decision quality from outcome quality**. Do not make a reckless bet that happened to succeed into a model case.
- **Separate the prediction from the after-the-fact evaluation (a two-point record)**. At selection time, leave only the candidates, the stakes, the expectations, the concerns,
  and the rejection conditions; append the outcome and the losses later.
- **Make the provenance of the reason a required field**: stated at the time / traces from the time / recalled afterwards / a present-day guess.
  **Accept "unrecoverable" as a legitimate conclusion** (the moment a blank is filled with a guess, archaeology turns into after-the-fact rationalization).
- **Do not judge success or failure with a single value per project**. Record residual value and the withdrawal decision separately, per feature and per channel.

The obligation to record is triggered by the stakes. Judge the stakes not by the size of the code but by the impact axes (data sensitivity, external impact, exitability,
the effort to rewrite). Low stakes may be recorded in a few lines, or not at all.

## Where records are stored

Decision records are stored in the `decisions` kind of the Agent Artifact Store (the `decisions/` directory, local visibility,
outside Git management). Always resolve the path through the contract of [artifact-store.md](./artifact-store.md).
Do not embed `docs/` paths.

## References

- Procedures and templates for recording and interviewing: the decision-journal skill (`skills/decision-journal/SKILL.md`)
- The storage contract: [artifact-store.md](./artifact-store.md)
- Juxtaposed philosophies: [design-principles.md](./design-principles.md) /
  [testing-anti-patterns.md](./testing-anti-patterns.md) /
  [information-placement.md](../../../rules/information-placement.md)
