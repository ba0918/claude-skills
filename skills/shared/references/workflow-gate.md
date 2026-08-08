# Workflow Gate — pre-execution enforcement of the trunk discipline

The canonical contract for the workflow enforcement gate: a check that an agent's
execution environment runs **immediately before a shell command executes**, guarding the
trunk workflow's transition points (direct commits to the default branch, pushes without
verification evidence, inspection-bypass flags). The decision core ships as
`skills/shared/scripts/workflow_gate.py`; this file defines what the gate decides and why.
Where wiring differs per environment, the wiring names live in the distribution manifests
and the repository README — never here.

Scope: the gate binds **agents only**. A human running git with their own hands is outside
the gate — the gate lives in the agent's execution environment, not in the repository's
git configuration, and it writes nothing into the consumer project except the two
human-approved artifacts defined below (the declaration file and the amnesty record).

## The Three Verdicts

Every intercepted command maps to exactly one verdict:

| Verdict | Meaning | Surface behavior |
|---|---|---|
| `allow` | The command conforms to the discipline (or is out of the gate's scope) | Pass through with **zero output** — no message, no context pollution |
| `escalate` | A discipline violation that a human may pardon | Ask the human, showing the gate's reason text. Human approval is the one legitimate pardon |
| `deny` | An inspection-bypass maneuver by the agent | Refuse execution. The reason text doubles as a just-in-time reminder of the broken rule |

The principle: **an agent can request a pardon but can never issue one.** On environments
whose pre-execution hook cannot express a human-confirmation response, `escalate` degrades
to a refusal carrying the same reason text — still an escalation in substance, not a
bypass verdict: the reason text spells out the human-approval procedure (the human either
performs the operation themselves or approves, after which the pardon is recorded and any
declaration is persisted as defined below). The README records which environments degrade.
`deny` never degrades to anything weaker.

## Decision Table

Row precedence: a bypass flag is checked **first** and its `deny` is never displaced by
any other row — a declared permission does not neutralize a bypass maneuver. When one
command carries several git operations, the strictest verdict wins
(`deny` > `escalate` > `allow`). The bypass row applies to git invocations: the same
character sequence appearing in a non-git command is not a bypass.

| Condition | Verdict |
|---|---|
| Bypass flag detected in a git invocation: `--no-verify`, `-n` on `git commit` (its short form), a hook-path override (`-c core.hooksPath=...`), or kindred hook-disabling options | `deny` |
| `git commit` on the default branch, no declared permission for it | `escalate` |
| `git commit` on the default branch, permission declared | `allow` |
| `git push`, trunk adoption declared, both evidence proofs (verification slice + doc-alignment record) valid and bound to `HEAD` | `allow` |
| `git push`, trunk adoption declared, either proof absent, SHA-mismatched, or invalid | `escalate` |
| `git push`, trunk adoption declared `not_adopted` | `allow` (the project opted out of trunk evidence requirements) |
| `git push`, no declaration present | `escalate` (the reason text walks through creating the declaration — ask-then-persist below) |
| git tokens detected but the command structure cannot be interpreted (multiplexed, wrapped, aliased shells) | `escalate` |
| Any other command | `allow` |

Interpretation is **conservative**: the gate parses the command string, never evaluates or
expands it. A `git commit` / `git push` token inside a structure the parser cannot decompose
(command substitution, `sh -c` wrapping, eval-style indirection) falls to `escalate`, not
`allow`. A command with no git write operation is always `allow`, silently.

## Declaration File — `.agents/config/trunk.yml`

Trunk adoption is a **human decision**, expressed as an explicit declaration in the tracked
configuration tree. The gate never assumes it.

```yaml
# Workflow gate declaration (written only after a human approved it)
trunk: adopted            # adopted | not_adopted
allow_main_commit: false  # true | false — permit agent commits on the default branch
```

Parsing rules (fail to the safe side):

- Only the two keys above are meaningful; each takes exactly the listed values.
- A missing file, a missing key, an unknown value, or an unparsable file counts as
  **undeclared** for the affected decision → the corresponding row of the table applies
  (`escalate`, never a silent `allow` and never a silent `deny`).
- **Ask-then-persist**: when an operation needs a declaration that does not exist, the gate
  escalates once and its reason text invites the human to answer. Once the human has
  answered explicitly, the agent persists exactly that answer into this file — persisting
  a human answer is permitted; creating or editing the file on the agent's own initiative
  is not. The file contains no secrets, no absolute paths, no environment-specific values.

## Evidence Requirement for `push`

Under a declared trunk (`trunk: adopted`), a push requires **two proofs**, both bound to
the current `HEAD` SHA. (Binding to `HEAD` is a deliberate v1 approximation of "the
commit being pushed": a push of a ref other than the checked-out `HEAD` passes the same
check, no finer.)

1. **The canonical verification slice** — both states (`machine_verified` and
   `semantic_reviewed`) per the [quality-gate-contract](quality-gate-contract.md) and the
   [evidence format](evidence-format.md), judged by the shipped verifier
   `skills/shared/scripts/evidence_check.py`. This is the review station's proof.
2. **A doc-alignment record** — `doc_aligned.json` in the same evidence directory, using
   the same record shape as the canonical states (`schema_version` 1, `state` equal to
   the basename `doc_aligned`, a full 40-hex `target_sha`, a non-empty `grounds` naming
   the doc-alignment run that produced it). This is the gate's own extension — the
   canonical contract does not define this state, so the gate validates it itself: the
   record must parse, name its state, match `HEAD` exactly, and carry grounds. This is
   the doc-alignment station's proof; it exists because the canonical slice alone does
   not testify that documentation was aligned (consumer projects typically run without a
   conformance profile, and no profile obligation covers doc alignment).

- Both proofs hold → `allow`.
- The verifier says not publishable (exit 1: a state's evidence is absent, expired —
  meaning its SHA no longer matches — or invalid) → `escalate`, and the reason text names
  which state failed and why.
- The verifier cannot run (exit 2) → `escalate` (a gate that cannot see evidence must not
  wave a push through).
- The doc-alignment record is absent, malformed, SHA-mismatched, or missing grounds →
  `escalate`, naming the defect.

When escalating, the reason text presents **what the existing evidence claims as its
grounds** (the `grounds` field), so the human pardons with the evidence in view, not
blind.

## Amnesty Records

A pardon (human approval of an escalated operation) is recorded so that normalization of
pardons — the gate rotting into a rubber stamp — stays auditable. Records append to a
single ledger inside the decisions kind of the agent artifact store
([artifact-store.md](artifact-store.md)):

```text
.agents/artifacts/decisions/workflow-gate-amnesties.jsonl
```

One JSON object per line, append-only:

```json
{"recorded_at": "2026-08-09T12:00:00Z", "gate": "main_commit", "command": "git commit -m ...", "reason": "the gate's reason text at escalation time", "grounds": "what the human saw and why they approved"}
```

- `gate` is one of `main_commit` / `push_evidence` / `push_undeclared` /
  `uninterpretable` — the decision-table row that escalated.
- `grounds` is required and non-empty: a pardon that cannot say why it was granted is not
  a record (the same Iron Law as evidence grounds in
  [evidence-format.md](evidence-format.md)).
- One line per pardon makes counting and slicing by `gate` mechanical (`wc -l`, any JSON
  line filter). Rot-detection thresholds over these counts are deliberately out of scope
  until real data accumulates.
- The decisions kind has local visibility per [artifact-store.md](artifact-store.md) — the
  ledger stays on the machine that granted the pardons and never enters version control
  (the same posture as the evidence directory). The audit this enables is per-environment,
  which matches its purpose: the pardons that need watching are the ones granted here. A
  pardon is a recorded human decision, which is what the decisions kind holds.
- The record is written **after** the human approves, as part of honoring the approval —
  it is a record of a human decision, not an agent's.

## Security Posture

- The decision core is a pure function: command string plus an environment snapshot in,
  verdict plus reason out. It executes nothing, expands nothing, and never shells out —
  all I/O (branch lookup, declaration read, evidence verification) is injected by a thin
  wrapper.
- Every parse failure — command, declaration, evidence — lands on `escalate`, never on
  `allow`.
- Detecting an agent that disables the gate itself (rewiring its own execution
  environment) is a **non-goal**: an agent that can write files can in principle undo any
  self-hosted guard. The gate raises the bar and guarantees violations reach human eyes;
  it does not promise unforgeability.
