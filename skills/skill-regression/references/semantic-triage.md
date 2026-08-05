# Semantic triage: judging a diff so a rerun can be talked down

Hash comparison detects "did the file change", which over-approximates "did behavior change".
Deleting one duplicated instruction currently puts every scenario that *might* be affected back on the bill,
and the only ways to clear it are an expensive run or a human eyeballing the diff. Semantic triage is the
layer in between: a judge reads the diff against a skill's requirements and decides whether it can say
"this does not affect the outcome". The canonical statement of the design is `docs/spec/semantic-triage.md`;
this document is the operating procedure.

## The permission boundary — read this before anything else

**The judge has no execution authority in any direction.**

- An `affected` verdict **never starts a rerun**. It prints a recommendation. Whether to rerun, or to accept
  anyway, stays exactly where it was: with the human.
- An `unaffected` verdict enables **one** thing — recording it in the ledger. That is a record, not control
  over execution.
- What the ledger gate means (something that changed does not go green without a recorded judgement) is
  unchanged. This layer makes a judgement cheaper and faster; it is neither a new enforcement nor a new loophole.

The reason: rerun cost is the root problem, so a judge with enforcement power would turn its own errors into
expensive reruns. It also keeps information confidence and mechanical authority aligned — the same principle
that lets the zero-possibility human declaration (`exercises`) feed the ledger while a probabilistic judgement
may only record.

## Where it applies

Only stale entries whose severity is `[contract-change]`. `prose-change` and `contract-addition` already have a
deterministic, cheap route (`--update <skill> --accept`, which records `accepted-prose` / `accepted-addition`),
and stacking a probabilistic judgement on a proof buys nothing. `semantic_diff.py` refuses the other severities
for that reason and names the cheaper route.

## Step 1 — build the judge input

```bash
python3 {skill_dir}/scripts/semantic_diff.py <skill> --skeleton <judgment.json> {repo_root}
```

It prints the canonical `diff_sha256`, the unified diff of every changed surface file, the impacted scenario
ids, and a judgment-file skeleton (also written to `--skeleton`). The base content comes from git history,
matched **by content hash against the ledger entry** rather than by commit position.

Add to the prompt, for each impacted scenario, only its **title and requirement texts** from `fixtures.json`.
Do not paste the whole fixture and do not paste the scenario's situation prompt: what the judge decides is
"could this diff change the pass/fail call on each requirement", and requirement texts fit in a few kilobytes.

One judging call covers **one diff x one skill**, and returns a per-scenario verdict table.

## Step 2 — judge

| Verdict | Use it when | What follows |
|---|---|---|
| `unaffected` | You read the whole diff and can say, requirement by requirement, why the pass/fail call is unchanged | May be recorded as `accepted-semantic` |
| `unclear` | You cannot see the whole diff, or the change touches something a requirement depends on and you cannot tell which way | Advisory display only. The human decides |
| `affected` | A requirement's pass/fail call could flip | Advisory display only — a rerun is recommended, never started |

**When torn between two values, take the heavier one** (`unclear` over `unaffected`, `affected` over `unclear`).
The whole mechanism is built so that the safe error is cheap and the unsafe one is not.

### Criteria

`affected` — the diff does any of these to something a requirement checks: negates a rule, changes a number,
changes the order of steps, deletes a non-duplicated instruction, adds an obligation the requirement measures
compliance with, or changes the vocabulary the requirement matches on.

`unaffected` — the diff is confined to one of these, and the requirements do not reach it: rewording that
leaves every machine-parsed token, command, number and ordering intact; an added example that only instantiates
a rule already stated; an edit inside a section none of the requirements test.

`unclear` — anything else, and always when the diff itself is not fully visible.

### Gray-zone adjudications

These are edits where reasonable readers disagree; the maintainer's ruling is recorded here, and the
calibration corpus measures whether the judge reproduces it.

| Edit | Ruling (2026-08-05) | Boundary |
|---|---|---|
| A duplicated instruction is deleted while an equivalent one stays in force in the same document | `unaffected` | If the deleted copy was the only one on the path the executor actually reads — the survivor sits behind a link nothing tells them to open — it is `affected` |
| A local restatement of a linked contract is deleted | `unaffected` | Only when the procedure tells the reader to follow that link |
| A purely illustrative example is removed and the rule it illustrated stays | `unaffected` | If a requirement matches on the example's wording, it is `affected` |
| A date or version in prose changes and no requirement matches on it | `unaffected` | — |

Note the asymmetry: rewording is **not** a mutation. Never treat a rephrasing as behavior-changing to look
cautious; that makes the judge look worse than it is and tightens the line for no gain.

## Step 3 — fill in the judgment file

```json
{
  "skill": "<skill>",
  "diff_sha256": "<from semantic_diff.py — do not edit>",
  "model": "<identifier of the judging model, as the runtime reports it>",
  "scenarios": {
    "<scenario id>": {"verdict": "unaffected", "rationale": "1-3 lines: which requirement, and why"}
  }
}
```

- **A prefilled `unclear` must never be overwritten.** `semantic_diff.py` prefills it when the base content
  could not be restored, which means the diff was never visible. Overwriting it would let the judge declare
  something safe that it has not read.
- `rationale` may not be empty. A judgement nobody can audit later is not a judgement.
- The model identifier is mandatory: calibration is model-specific, so changing the model invalidates the gate
  until it is recalibrated. Do not hard-code a model name into this document or into any fixture — the value
  belongs in `calibration.json`, written by measurement.

## Step 4 — advisory display

Show every verdict, including the ones nothing acts on, and make it visible that no rerun was launched:

```
semantic triage — <skill> (diff 9486430d162c)
  unaffected  cy-002  the deleted line duplicated the rule still stated above it
  unclear     cy-007  base content unrestorable; diff not visible
  affected    cy-011  the iteration cap this requirement checks changed from 3 to 10
recorded 1 / advisory 2 — no rerun was started by this judgement
```

## Step 5 — record (only `unaffected`)

```bash
python3 {skill_dir}/scripts/ledger.py --update <skill> --partial --semantic <judgment.json> {repo_root}
```

Combine it with `--scenario <id>` for scenarios you really did rerun. The ledger refuses the **whole** update,
writing nothing, when any of these holds — the same all-or-nothing rule `--partial` already has:

- a required field is missing, `model` is not a non-empty string, a verdict is outside the three values, or a
  rationale is empty
- a verdict names a scenario id that is not in `fixtures.json` — otherwise a typo would surface only as "that
  scenario has no verdict", pointing at the wrong thing
- `diff_sha256` does not match the current difference (an old judgement reused on a different change)
- the judging model has no calibration record, its `must_flag_fn` is above 0, its record was measured on a
  different corpus revision, or the corpus holds fewer than 20 cases on either side
- an impacted scenario has no verdict, or its verdict is `unclear` / `affected`
- an impacted scenario's `scenario_sha256` moved: when the acceptance criteria themselves changed, only a real
  run can settle it
- an impacted scenario's previous record is neither `pass` nor `accepted-semantic`: a judgement says "this diff
  does not change the behavior you last verified", so it needs a real run underneath to stand on. An entry with
  no per-scenario records at all is named as such and points at `--seed-scenarios`, not at a rerun — the
  missing thing is the bookkeeping, not the verification

`--semantic` cannot be combined with `--accept`, and requires `--partial`.

### What the ledger does not check here

**The severity band.** The `[contract-change]`-only rule of [Where it applies](#where-it-applies) lives in
`semantic_diff.py`, the script that builds the judge input. `ledger.py` does not re-check it, so a hand-written
judgment file can route a `prose-change` or `contract-addition` diff through this path. That misuse does not
point in one direction: on the record being written it is the safe direction — a weaker `accepted-semantic`
lands where the mechanically proven `accepted-prose` / `accepted-addition` would have. It reverses on the
*next* record. `accepted-prose` decays to `accepted-without-run` at the following `--accept` (a light class
demands a real run underneath it), while `accepted-semantic` is the one light class allowed to stand on
itself. So the same misuse turns a one-time discount into a standing one. Whether to add the band check to
`--partial --semantic` is to be re-evaluated on reaching stage 3, when automatic recording is unlocked.

## Calibration

The corpus lives in `skills/skill-regression/calibration/`, `must_flag/` and `must_pass/`, at least 20 cases per
side. Each case is `{id, expected, before, after, requirements[], mutation?, label?, notes?}`.

```bash
python3 {skill_dir}/scripts/semantic_calibration.py --validate {repo_root}
# judge every case exactly as in Step 2, collect the verdicts into
# {"model": "<identifier>", "results": {"<case id>": "<verdict>"}}
python3 {skill_dir}/scripts/semantic_calibration.py --score <results.json> {repo_root}
```

Scoring records the measurement honestly whether or not it passes — including how many cases each side was
measured on, so the weight behind a zero is auditable later. `ledger.py` is what decides whether the gate opens
(`must_flag_fn == 0`, the corpus fingerprint still matches, **and** each side still holds at least 20 cases). So a
corpus revision, a model change, and a thinned corpus all close the gate again, mechanically, with no prose rule
to remember. `--min-cases` lowers the validator for local experiments; it cannot lower the gate.

A false negative is a `must-flag` case judged `unaffected`. `unclear` on a `must-flag` case is not a false
negative — it routes to a human, which is the intended safe outcome. On the `must-pass` side anything other than
`unaffected` counts against the saving, so both `affected` and `unclear` are scored as false positives.

Measuring is a staged rollout, not a switch: run the judge alongside normal operation as an advisor first, then
calibrate, and only then does recording become reachable. The `must_flag_fn == 0` line is provisional by design —
it may be revisited once there is operating data.

## What `accepted-semantic` means in the ledger

Not "proof that behavior did not change" — **"a judge calibrated to the maintainer's rulings said it does not
affect the outcome"**. It never calls itself `pass`, and `--check` counts it on its own line so over-reliance
stays readable.

Each such scenario record keeps its own `semantic` block — the judging model, the diff hash, the verdict and the
rationale. The provenance sits on the record rather than on the entry because a record made by one judgement is
later carried over into entries that have no judgement of their own; on the entry it would be lost at the first
carry-over. A record with no `semantic` block was produced by a real run or a mechanical carry-over, which is
what makes the accumulated judge-driven records selectable for a spot audit. Runs performed later for other
reasons double as that audit.

## Related

- [partial-rerun.md](partial-rerun.md) — scenario-granular impact, carry-over, and the `--partial` route this rides on
- [fixture-schema.md](fixture-schema.md) — where scenario titles and requirement texts come from
- [verification-gate.md](../../shared/references/verification-gate.md) — the evidence rule a judgement never replaces
