# Partial rerun: scenario-granular re-verification and ledger carry-over

Re-running used to have one unit: the skill. Editing one line of a shared contract put every scenario of every
referring skill (20 of them for `cycle`) on the bill, even when 2 or 3 scenarios actually touch that contract.
This document is the contract for narrowing the unit to the **scenario**, and for advancing the ledger when only
part of the set was re-run (#243).

Every rule below fails safe. Whenever the machine lacks the material to decide, it falls back to "re-run
everything" — never to "carry it over".

## The `exercises` declaration

A scenario may declare which behavior-surface files it exercises:

```json
{ "id": "cy-002", "prompt": "...", "requirements": [],
  "exercises": ["skills/shared/references/artifact-paths.md"] }
```

- **It is a complete claim.** A declaring scenario asserts that, of the behavior surface, it touches *only* the
  listed files plus two implicit ones: `skills/<skill>/SKILL.md` (every scenario reads it) and
  `skills/<skill>/fixtures.json` (the scenario's own definition, handled by content hash — see below).
- **An empty list is a declaration**, not an omission: it claims "nothing beyond SKILL.md".
- **No declaration is the safe side.** A scenario without `exercises` is impacted by any change to the surface —
  identical to the behavior before this mechanism, so existing fixtures keep working unchanged.
- **A declaration that misses the surface is discarded.** If any declared path is absent from the current
  behavior surface (a typo, or a reference that moved), the whole claim is distrusted and the scenario returns to
  always-re-run. A single typo must never buy a carry-over.
- **It is excluded from `scenario_sha256`.** The declaration is impact metadata, not part of what the scenario
  measures. Because the hash ignores it, adding declarations to an existing fixture costs **zero reruns** — the
  ledger advances through `--partial` with everything carried over. That is what makes adoption free, and the
  canonical hash lives in `fixture_setup.py` so the rerun guard and the carry-over rule can never disagree.

## Which scenarios a change impacts

`ledger.py --impact-scenarios <files>... <root>` prints `skill<TAB>scenario_id`. The rules, in order:

| Changed file | Impacted scenarios |
|---|---|
| nothing on the behavior surface | none |
| `skills/<skill>/SKILL.md` | all |
| a file that left the surface (a deletion) | all |
| `skills/<skill>/fixtures.json` | only those whose `scenario_sha256` moved, or that are new. With no per-scenario record in the ledger: all |
| any other surface file `f` | the scenarios declaring `f`, plus every scenario with no declaration (or a discarded one) |

`--check` appends the same breakdown to each `[stale]` line (`→ scenarios: cy-002,cy-007 (2/20)`), so the size of
the bill is visible where the failure is reported. The verdict itself is unchanged: stale stays stale until the
ledger is updated.

## Carrying a scenario over

A carry-over is valid by **induction on the previous entry**, which is why no per-scenario file hashes are stored:

> Scenario `s` carries over into a new entry **iff** its `scenario_sha256` is unchanged and every file in its
> dependency set has the same hash as in the previous entry. The dependency set is `exercises` plus `SKILL.md`
> when declared, and the whole surface (minus `fixtures.json`) when not. In the previous entry `s` was valid —
> it was either really run or carried over under this same rule — so if nothing it depends on moved, it is valid now.

`fixtures.json` is deliberately kept out of the hash comparison and handled through `scenario_sha256`. Comparing
it as a file would mean another scenario's edit, or merely adding a declaration, breaks every carry-over — and
that would contradict the impact rule above.

A dependency recorded as `MISSING` in the previous entry (a reference with no file behind it) blocks the
carry-over: a broken reference is not a foundation to induct from.

## Operating `--partial` and `--seed-scenarios`

```bash
# Re-ran cy-002 and cy-007; carry the rest over
python3 ledger.py --update cycle --partial --scenario cy-002 --scenario cy-007 .

# Declaration-only fixture edit: nothing was run, everything carries over
python3 ledger.py --update cycle --partial .

# One-shot migration for an entry that predates per-scenario records
python3 ledger.py --seed-scenarios cycle .
```

- Naming **zero** scenarios is legitimate: it records "nothing needed re-running, and here is the machine-checked
  reason". Even then the skill-level `result` stays `pass`, because validity was confirmed mechanically rather
  than asserted. If any scenario record is not a real `pass` (a seeded acceptance, say), the skill level drops to
  `accepted-without-run` — a set containing something never run may not call itself passed.
- If even one scenario can neither be run nor carried over, **the whole update is refused** and the blockers are
  listed with their reasons. A partial write would leave the ledger unable to say how much of it is still valid.
- `--partial` cannot be combined with `--accept`. Acceptance means "judged without running"; partial means
  "these were run". Mixed, the recorded `result` would no longer have a single meaning.
- `--seed-scenarios` refuses a stale entry, and refuses an entry that already has records. It is bookkeeping, not
  verification: it distributes the skill-level guarantee ("every scenario passed at this surface") down to the
  scenarios and leaves the verification date untouched. Allowing a re-seed would let a skill-level `pass`
  overwrite scenario records that were never actually run.
- The existing `--accept` route, including its refusal when `fixtures.json` changed, is untouched. `--partial` is
  a separate path. Note the consequence at scenario granularity: an acceptance stamps **every** scenario record with
  the accepted value, so the skill cannot return to `pass` through partial reruns alone — a full run has to re-earn
  it. That is deliberate. Inheriting `pass` into the records would turn a skill-level judgement made without running
  into per-scenario evidence, and the whole point of the records is that they carry only what was actually verified.

## Guarantee boundary

**An omitted declaration cannot be detected mechanically.** If a scenario really exercises a contract but does
not list it, a change to that contract will not mark it impacted, and its stale pass will be carried over. Nothing
in this mechanism can catch that; the fallbacks only cover declarations that are *absent* or *point off the
surface*. So:

- Adding or editing `exercises` is a review item. Read it against the scenario's prompt and requirements, not
  just against the diff.
- When run evidence is insufficient to say what a scenario exercises, **leave it undeclared**. An undeclared
  scenario merely costs a rerun; a wrong declaration silently skips one.
- A declaration is a claim about behavior, so it ages with the scenario. When a scenario's prompt or requirements
  change, revisit its declaration in the same edit.
- The likeliest way a declaration goes stale is **the surface growing behind a file it already lists**: a declared
  reference gains a link, the linked file joins the surface one hop out, and the declaration does not follow. The edit
  that adds the link changes the declared file too, so that rerun is forced — but a later edit to the *new* file alone
  reaches no declaring scenario. When a change adds a file to the surface, extend the declarations that route to it in
  the same edit.

## Relation to the quality gate contract §2

Narrowing rerun granularity does not touch
[quality-gate-contract.md §2](../../shared/references/quality-gate-contract.md#2-evidence-validity)
(adjudicated 2026-08-04, issue #243): the regression ledger is an internal input to the `machine_verified`
entry point, not §2 evidence, so its freshness rules are its own policy. The full statement of that adjudication
is in [fixture-schema.md § Relation to the quality gate contract](fixture-schema.md#relation-to-the-quality-gate-contract);
it is not restated here, to keep one canonical wording.
