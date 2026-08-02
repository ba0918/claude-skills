# Evidence States and Coverage Semantics

Layer 2 of the two-layer decision table: given what was actually looked at, what may and may not be claimed.
Layer 1 (change kind → which evidence to read and which cheap checks to run) lives in
[SKILL.md](../SKILL.md).

The coverage vocabulary `reviewed` / `skipped` / `unsupported` / `inconclusive` is defined in
[coverage-ledger.md](../../shared/references/coverage-ledger.md), and this file only says how a skill-artifact
review picks among them. The five evidence states below are a separate axis: they describe **the health of an
existing run record**, not the scope of this review.

## Why run evidence is read rather than produced

Running an LLM sensor — a skill-regression run, a trigger-eval dynamic evaluation, an empirical tuning loop — costs
real money and real time, so requiring one on every review is not a thing that can hold. skill-reviewer therefore
runs only deterministic, cheap verification (repository validators, unit tests of scripts) and **reads** run
evidence others already paid for. Missing run evidence is not a defect to report; it is a limit on what this review
can conclude. Say so, and let the human decide when to pay.

## The five states of a run record

The regression ledger (`skills/skill-regression/ledger.json`) already records, per skill, the `surface` (the files
that constitute the behavioral surface), a `surface_sha256` over them, the `result`, and the `verified` date.
Classification is a comparison, not a measurement.

| State | What it means | How it is decided |
|-------|---------------|-------------------|
| `current_pass` | A real run passed, and it still applies to the current surface | `result` is a pass **and** the recomputed surface hash equals the recorded `surface_sha256` |
| `accepted_without_run` | Re-evaluation was explicitly judged unnecessary; nothing was run | `result` is `accepted-without-run` |
| `stale` | A real run passed, but the surface has changed since | `result` is a pass and the recomputed surface hash differs |
| `uncovered` | There is no fixture, so there is nothing to be stale about | The skill has no `fixtures.json`, or the ledger has no entry |
| `invalid` | A record exists but cannot be used | The entry is malformed, or its `surface` names files that no longer exist |

Obtain the current classification from the ledger tooling rather than by hand:

```bash
python3 skills/skill-regression/scripts/ledger.py --status .
python3 skills/skill-regression/scripts/ledger.py --impact <changed files> .
```

`--impact` answers the question that matters when a shared contract is touched: which skills have that file on
their behavioral surface, and therefore whose evidence just went `stale`.

### The one display rule

`accepted_without_run` is **not** run evidence and must never be shown as though it were. It is the record of a
judgement that a run was unnecessary, which is a different thing from a run that happened. Presenting them alike
makes the diagnosis look stronger than it is — the exact failure this skill exists to avoid. The validator's
`classify_evidence` keeps them apart with distinct labels, so use its output rather than composing a label
yourself.

`stale` is genuine run evidence that no longer applies. Report it as such: something was measured, and the thing
measured has since changed.

## What each kind of claim may rest on

A skill artifact is natural-language instructions. Some properties of it are decidable by reading; others only show
up when a model executes it. Mixing the two is how a static PASS inflates into a dynamic guarantee.

| Kind of claim | Decidable statically? | Coverage value when there is no run evidence |
|---------------|----------------------|---------------------------------------------|
| Structural conformance (frontmatter, layout, link targets resolve) | Yes — validators decide it | `reviewed` |
| Contract consistency (the body agrees with the contracts it links to; shared vocabulary used with its defined meaning) | Yes — refutable from the text | `reviewed` |
| Script behavior (exit codes, pure-function results) | Yes — the unit tests decide it | `reviewed` |
| Execution quality (does a model actually follow these instructions; is a step skipped) | No | `unsupported` — promoted by a regression run |
| Firing accuracy (does the description fire on the right requests, does it collide with a sibling skill) | No | `unsupported` — promoted by a trigger-eval run |
| Salience (does a low-signal instruction survive in a long body) | No | `unsupported` — promoted by empirical tuning |

Rules that follow from the table:

- Never claim PASS for an area whose value is `unsupported` or `inconclusive`. An area not looked at is not an area
  without problems ([coverage-ledger.md](../../shared/references/coverage-ledger.md), The Iron Law).
- A finding about an `unsupported` area is at most a WARN in `diagnostics`, because the evidence that would qualify
  it as a control candidate does not exist.
- When you recommend paying for a run, attach the blast radius (which skills' surfaces are affected) and a rough
  cost (how many scenarios, at which executor tier). A recommendation without those two is not actionable, and it
  is a recommendation either way — never a gate.

## The coverage ledger in the output

Every review states its coverage, including the areas it structurally cannot see. Keeping the default
`unsupported` rows in the template is what stops those areas from silently reading as "fine":

```json
"coverage": [
  { "target": "skills/example/SKILL.md", "value": "reviewed", "reason": "Body checked against every contract it links to" },
  { "target": "skills/example/scripts/", "value": "reviewed", "reason": "Unit tests run; output recorded" },
  { "target": "Execution quality", "value": "unsupported", "reason": "No LLM sensor is run here. A skill-regression run over the 3 scenarios promotes this to reviewed" },
  { "target": "Firing accuracy", "value": "unsupported", "reason": "No dynamic evaluation is run here. A trigger-eval run promotes this to reviewed" }
]
```
