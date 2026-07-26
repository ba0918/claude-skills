# Goal Decomposition — Shared Contract (the translation layer from a broad goal to a Loop Readiness Dossier)

> **⚠️ Warning:** This contract is the **upstream "translation layer"** for the existing 4
> closed-loop contracts ([loop-engineering.md](loop-engineering.md) supply /
> [convergence-pattern.md](convergence-pattern.md) convergence /
> [polling-pattern.md](polling-pattern.md) consumption /
> [measurement-identity.md](measurement-identity.md) measurement). It does not redefine the
> existing contracts; it **maps** each dossier field onto their vocabulary (§7 mapping table).
> Do not add vocabulary of its own. When changing the Dossier Schema / decision tree / rule
> table, update `skills/goal-decomposition/`'s SKILL.md, `scripts/dossier_lint.py`, and
> `references/dossier-template.md` in sync within the same PR.

Where the classification axes are defined:
[fix-action-taxonomy.md](fix-action-taxonomy.md) (AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY) /
[severity-and-verdicts.md](severity-and-verdicts.md).

---

## 1. Goals and Non-goals

**Goal**: compile a natural-language broad goal (e.g. "scrutinize the whole codebase and see
the refactoring through") into a machine-verifiable **Loop Readiness Dossier** (the result of
type-checking for self-drivability). The primary output is **mechanically explaining and
stopping the fragments that must not be self-driven** — do not let a wish flow into automation
while it is still a wish.

**Non-goals (out of scope for v1):**

- It does not **execute** the wiring (starting goal-loop / generating sensor adapters /
  auto-filing into inbox). A dossier is a "type-check result" and grants no execution authority
  (§6). In particular, inbox is a route result of loop-triage — do not add another writer
- It does not turn a dossier into an event on `.agents/runtime/loop/events.jsonl` (out of scope
  for v1 because it would require revising the closed enum of the measurement-identity contract)

---

## 2. Dossier Schema v1 (the single source for the contract, tests, and lint)

To keep the contract, the fixtures, and the lint implementation from drifting on an implicit
schema, the canonical key hierarchy is fixed here. **Unknown fields are ignored** (forward
compatibility). A dossier has **2 layers — canonical JSON plus an md report** — and lint targets
the JSON only, treating the md as a view (a generated artifact). They live at
`.agents/artifacts/loop/dossiers/{timestamp}_{slug}.json` plus an `.md` of the same name.

```jsonc
{
  "schema_version": 1,               // int, required
  "status": "draft",                 // enum: draft | approved | superseded | rejected
  "superseded_by": null,             // required when status is superseded (the successor dossier's filename)
  "goal": {
    "statement": "…",
    "non_goals": ["…"],              // GD302 warn if empty
    "ssot": "…"                      // SSOT declaration (what the authoritative source is)
  },
  "oracles": [{
    "id": "oracle:slug",             // ids are unique across all blocks (GD006)
    "type": "true",                  // enum: true | proxy
    "command": "…",                  // judgement command (maps to convergence-pattern's oracle)
    "oracle_files": ["docs/x.md"],   // explicit repo-relative enumeration (empty/glob-only -> GD301 warn, absolute path/secret -> GD203 error)
    "owner": "…",                    // ownership
    "proxy": {                       // required when type is proxy (§5 -> GD201)
      "gap_from_true_goal": "…",     // the gap from the true completion condition
      "failure_modes": "…",          // the cases where it breaks
      "human_limit_approved": false, // human approval of the limitation
      "hash_lock": true,             // hash-lockable
      "post_completion_human_check": true,
      "judge_type": "mechanical"     // "llm_subjective" is a GD201 error
    }
  }],
  "fragments": [{
    "id": "frag:slug",
    "wire_to": "goal-loop",          // enum: goal-loop | loop-triage | inbox | plan | reject
    "exit_to": "ci_gate",            // enum: ci_gate | resident_sensor | dissolve
    "routing_proof": "1-line grounds", // missing when approved -> GD102 error
    "auto_fix_allowed": false,
    "why_not_auto_fix": "…",         // required when auto_fix_allowed is false (§4 -> GD102)
    "self_modification_risk": "low", // enum: low | high. high x auto_fix_allowed=true -> GD202 error
    "blocked_by": ["inbox:q1"]       // reference integrity is GD005
  }],
  "sensors": [{
    "id": "sensor:slug",
    "rules": ["…"],                  // explicit list of adopted rules (prevents the scope of responsibility from becoming unbounded)
    "findings_policy": {
      "fix_action": "REPORT_ONLY",   // enum: AUTO_FIX | NEEDS_JUDGMENT | REPORT_ONLY (maps to fix-action-taxonomy)
      "enqueue": false               // fix_action REPORT_ONLY together with enqueue true -> GD101 error
    }
  }],
  "inbox": [{
    "id": "inbox:q1",
    "question": "…",
    "reclassify_when": "…"           // reclassification condition (when this question can be promoted to an oracle/sensor)
  }],
  "measurement": {
    "metrics": ["…"],                // written with the names of existing measurements (maps to measurement-identity)
    "stop_conditions": ["…"]
  }
}
```

The required blocks are the **5 kinds `goal` / `oracles` / `sensors` / `inbox` / `measurement`
plus `schema_version`** (GD001).

---

## 3. The First-question Decision Tree (deriving each fragment's wiring target)

Split the broad goal into **fragments** and ask each fragment **this first**:

```
Q1. Is this fragment a "completion condition" / a "shortfall detector" / a "human judgement"?
    ├─ Completion condition (once true, you can say it is achieved)
    │     → Q2. Can it be made a machine-verifiable oracle?
    │            ├─ Yes                → wire_to: goal-loop (convergence-pattern's oracle)
    │            └─ The oracle is too big to split into units of work (decomposition gap)
    │                                  → wire_to: plan (cannot even be split into intermediate oracles; go straight to a manual plan/cycle)
    ├─ Shortfall detector (something that keeps detecting "not achieved yet")
    │     → Q3. Does it conform to the Finding Schema (loop-engineering §2)?
    │            ├─ Conforms          → wire_to: loop-triage (supplied as a sensor)
    │            └─ Does not conform  → wire_to: inbox (held until a human designs the detection method)
    └─ Human judgement (cannot be automated / must not be)
          → Q4. Is it a judgement it is **acceptable** to automate?
                 ├─ Acceptable (holding it now allows mechanization later) → wire_to: inbox (with reclassify_when)
                 └─ Must not be sent into automation                       → wire_to: reject (goes to non-goals)
```

**Auto-fixability (AUTO_FIX and friends) is an attribute of a finding, not of a fragment**.
Evaluate the fragment's `auto_fix_allowed` / `self_modification_risk` **after** the first
question has decided the wiring (§4). Starting oracle-first ("is it observable?") throws away
fragments that could have become sensors, so always start from "completion condition / shortfall
detector / human judgement".

Deriving the 5 values of `wire_to`:

| Value | Exit of the decision tree | Meaning |
|----|-------------|------|
| `goal-loop` | Q2 = yes | Turn the completion condition into a machine-verifiable oracle and converge on it with goal-loop |
| `loop-triage` | Q3 = conforms | Supply the shortfall detector to loop-triage as a Finding-Schema-conformant sensor |
| `inbox` | Q3 = does not conform / Q4 = acceptable | Wait for human judgement and design (state the later promotion condition with reclassify_when) |
| `plan` | Q2 = decomposition gap | The oracle is too big and cannot be split into intermediate oracles → go straight to a manual plan/cycle |
| `reject` | Q4 = must not be sent | Goes to non-goals. A fragment not put on automation |

> **Note on field naming**: a fragment's wiring target is named `wire_to`. It is **distinct**
> from `route` in loop-engineering §4 (a finding's destination enum: enqueue/inbox/digest/…).
> `wire_to` is goal fragment → subsystem selection; `route` is finding → queue selection. To
> avoid a name collision, `route` is not used here.

---

## 4. The 5-axis routing proof

Each fragment is evaluated on 5 axes and carries **a 1-line routing proof, not a score table**:

| Axis | Dossier field | Used for |
|----|-------------------|------|
| Machine verifiability | the oracle's `command` / `type` | decision tree Q2 |
| Finding-ability | the sensor's `rules` / `findings_policy` | decision tree Q3 |
| Auto-fix tolerance | `auto_fix_allowed` + `why_not_auto_fix` | admission (loop-engineering §4) |
| Self-modification risk | `self_modification_risk` | dangerous-combination check (GD202) |
| Measurability | `measurement.metrics` | observing the stop condition |

- `routing_proof` states in 1 line per fragment "why this `wire_to`" (required when
  `status: approved` = GD102)
- **A non-AUTO_FIX fragment must state "why it is not AUTO_FIX"** (`auto_fix_allowed: false` →
  `why_not_auto_fix` required = GD102). This forces "held back for safety" to be written down
  and prohibits implicit holds
- **Dangerous combination** (mechanizing the 5-axis check): `self_modification_risk: high`
  together with `auto_fix_allowed: true` is a GD202 error. Do not put self-modification without
  a regression net onto auto-fixing (the stage before loop-engineering §5's self-modification
  gate)

### 4.1 wire_to × exit_to compatibility matrix (GD103)

`exit_to` (how a fragment ultimately "graduates") must be consistent with `wire_to`. **Only ✓
is permitted**:

| wire_to \ exit_to | ci_gate | resident_sensor | dissolve |
|-------------------|:-------:|:---------------:|:--------:|
| `goal-loop`       |    ✓    |        ✗        |    ✓     |
| `loop-triage`     |    ✓    |        ✓        |    ✗     |
| `inbox`           |    ✗    |        ✗        |    ✓     |
| `plan`            |    ✗    |        ✗        |    ✓     |
| `reject`          |    ✗    |        ✗        |    ✓     |

Derivation:

- `goal-loop` (a completion condition) becomes, after achievement, either **ci_gate** (handed
  over to a permanent regression gate) or **dissolve** (disbanded if the achievement was
  one-off and needs no upkeep). resident_sensor is an exit for sensors and does not fit a
  completion condition
- `loop-triage` (a shortfall detector) becomes either **resident_sensor** (resident polling) or
  **ci_gate** (promoted to a CI gate). A detector dissolving (= ceasing to detect) is a
  contradiction
- `inbox` / `plan` / `reject` are temporary fragments that do not become resident in a
  downstream subsystem, so **dissolve** only. In particular `inbox × ci_gate` and any
  non-dissolve exit for `reject` are stopped by GD103 as wirings that contradict the decision
  tree

> This table is the single source of truth for the matrix; `_COMPAT` in `dossier_lint.py` and
> the catalog-sync test in `test_dossier_lint.py` guarantee they agree.

---

## 5. The status Lifecycle and the Conditions for Allowing a proxy Oracle

### 5.1 The status Lifecycle (the human gate stops things by state)

A dossier carries a `status` (`draft` / `approved` / `superseded` / `rejected`). **Do not widen
the places where user confirmation is mandatory** (headless compatibility). Approval is a human
directly editing the dossier to transition it `draft → approved`.

- **compile always outputs `draft`** (compile never emits approved)
- Lint enforces the state invariants: `approved` yet `routing_proof` is missing (GD102) /
  `approved` yet unresolved `blocked_by` remains (GD104) / `superseded` yet `superseded_by` is
  missing (GD104) / a fragment of a dossier with status `rejected` still carries an `exit_to`
  wiring (GD104)
- **approved does not approve execution** (§6)

### 5.2 Conditions for Allowing a proxy Oracle

A proxy oracle (`type: proxy`) is permitted only as a "**lower-bound gate for safe forward
progress**". It must satisfy **all** of the following (GD201):

1. `human_limit_approved: true` — a human has granted limit approval: "this is not the true
   completion condition, but I approve it as a lower bound"
2. `hash_lock: true` — hash-lockable (oracle-gaming can be blocked by convergence-pattern's
   hash lock)
3. `post_completion_human_check: true` — connects to human judgement after achievement
4. `judge_type: "mechanical"` — mechanical judgement. **`"llm_subjective"` (subjective
   evaluation by an LLM judge) is prohibited** (GD201 error)
5. `gap_from_true_goal` / `failure_modes` stated explicitly as required fields ("the gap from
   the real completion condition", "the cases where it breaks")

Write in `failure_modes` that the damage under Goodhart (satisfying the proxy but not the true
goal) is limited.

---

## 6. approved Grants No Execution Authority (the trust boundary)

**In v1, `status: approved` grants no execution authority whatsoever**. Executing the wiring
(starting goal-loop / generating sensors / filing issues) is the job of a separate future gate,
and cycle and friends must not silently connect an executor to the approved transition. Lint is
read-only; compile is the only writer.

### 6.1 Fence Conventions for the Trust Boundary of Copy-paste Blocks

Copy-paste blocks inside a dossier (a manifest / sensor spec / issue seed meant to be pasted
into another system) **use a separate fence per purpose to make the trust boundary explicit**.
The fence tokens are:

| Purpose | Fence token |
|------|---------------|
| For an oracle manifest | ` ```oracle-manifest ` |
| For a sensor spec | ` ```sensor-spec ` |
| For an issue seed | `<untrusted_user_content>` … `</untrusted_user_content>` |

- An issue seed assumes the consuming side (issue polling) wraps it in
  `<untrusted_user_content>`. **The wrapping happens at the consumer's boundary**
- If the fence content contains a closing delimiter (`</untrusted_user_content>` etc.), escape
  or reject it (blocking boundary breaks via prompt injection)

---

## 7. Mapping Table onto the Existing 4 Contracts

Map every non-native field onto the existing contracts' vocabulary, one line each (to prevent
proliferation of bespoke vocabulary):

| Dossier field | Maps to | Notes |
|-------------------|--------|------|
| `oracles[].command` / `type` | the Oracle definition of [convergence-pattern.md](convergence-pattern.md) | maps to goal-loop's judgement command |
| `oracles[].oracle_files` | convergence-pattern's oracle_files (the hash-lock target) | follows the writing convention of §8 |
| `fragments[].exit_to = ci_gate` | the validate_repo CI gate (the Verifier layer of [loop-engineering.md](loop-engineering.md)) | handed over to the regression gate |
| `fragments[].exit_to = resident_sensor` | the Sensor Adapter contract of [loop-engineering.md](loop-engineering.md) §7 | registered as a resident sensor |
| `sensors[].findings_policy.fix_action` | [fix-action-taxonomy.md](fix-action-taxonomy.md) (AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY) | input to admission |
| `sensors[].findings_policy.enqueue` | route = enqueue in [loop-engineering.md](loop-engineering.md) §4 admission | REPORT_ONLY is never enqueued (invariant) |
| `measurement.metrics` | the measurement-series names of [measurement-identity.md](measurement-identity.md) | written with the names of existing measurements |
| `fragments[].wire_to` | **(new)** — distinct from finding.route (see the note in §3) | goal fragment → subsystem selection |
| `status` (lifecycle) | **intentionally-new** | a dossier-specific human gate. No counterpart in the existing contracts |
| `exit_to = dissolve` | **intentionally-new** | a dossier-specific terminal meaning "does not become resident downstream; disbanded" |

---

## 8. Writing Conventions for oracle_files

Do not write "the whole directory is locked, so new additions are detected too". The
`goal_loop.py verify` CLI has the implementation limit of being **centered on the paths recorded
in the manifest**, so a glob or directory specification misses newly added files.

- Write a dossier's `oracle_files` as an **explicit enumeration of the files to lock** (an
  enumeration of `docs/x.md`; `docs/**` is not allowed)
- An empty array or glob-only is a GD301 warn (prompting explicit enumeration)
- An absolute path (`/home/…` etc.) or a mixed-in secret is a GD203 error (§9)

---

## 9. Secret Redaction and the GD203 Defense in Depth

Pass the dossier through `skills/shared/scripts/secret_detect.py` before writing it out (the
same operation as loop-triage). It applies in 2 stages:

1. **Free-text fields** (`goal.statement` / `inbox[].question` / `routing_proof` etc.) are
   masked with `mask_secrets`
2. **Structural fields** (`oracle_files` / hash values / each `id`) use `detect_secrets` and
   **abort the compile on a hit** (do not silently destroy them by masking. This prevents a hash
   value misfiring as `generic_long_key`, or an absolute path as `home_path`, from breaking the
   safety gate itself. Requiring `oracle_files` to be repo-relative also serves to avoid this
   misfire)

Because the compile layer's detect-and-abort can be bypassed by directly committing a
hand-written dossier, **the same check is also held on the enforcing-gate side (lint → CI) as
GD203** (defense in depth). GD203 is an error if `oracle_files` / `command` / any `id` contains
an absolute path or a `detect_secrets` hit.

The md view is generated one-way from the redacted JSON and carries the JSON's sha256 marker at
the end (closing the path by which a secret could enter the md alone). In v1 the hash marker is
tamper-evident (a clue for detecting tampering) and is not machine-verified (a CI check that
recomputes the marker is a v1.1 candidate).

---

## 10. The 3-way supply gap Playbook

When the loop stalls, determine the failure kind from existing measurements (oracle truth ×
ready count × inbox count × finding_id recurrence). Because the decision formula can be written
in existing measurements, supply-gap detection can itself be turned into a sensor.

| # | Kind | Decision formula | Response |
|---|------|--------|------|
| ① | sensor coverage gap | oracle false **and** ready empty **and** inbox empty | Add a sensor (there is no detector and nothing is moving forward) |
| ② | Human-judgement backlog | inbox is piling up (inbox count >> 0) **and** ready consumption is progressing | **Not a loop failure**. A human works off the inbox |
| ③ | decomposition gap | oracle false for a long stretch **and** the same finding_id recurs **and** the oracle is too big to split into units of work | **Do not weaken the oracle**. Add an intermediate oracle (move to `wire_to: plan`) |

> Weakening the oracle in ③ to make it pass is oracle-gaming (exactly what
> convergence-pattern's `oracle_tampered` halt blocks). Adding an intermediate oracle is the
> legitimate route.

---

## 11. Dossier Lint Rule Catalog (GD*)

The `RULES` registry of `scripts/dossier_lint.py` and **this table are a dual source of truth**,
and the catalog-sync test in `scripts/test_dossier_lint.py` mechanically verifies that the IDs
and severities agree (drift prevention).

**ID band convention**: `GD0xx` = structure/schema, `GD1xx` = routing/proof, `GD2xx` =
proxy/safety, `GD3xx` = advisory (warn).

| Rule ID | Severity | What is checked |
|---------|----------|---------|
| GD001 | error | Presence and type of the 5 required blocks (goal / oracles / sensors / inbox / measurement) plus `schema_version` |
| GD002 | error | `status` is within the enum (draft/approved/superseded/rejected). Missing or wrongly typed is also an error |
| GD003 | error | Each fragment's `wire_to` is within the enum (goal-loop/loop-triage/inbox/plan/reject). Missing or wrongly typed is also an error |
| GD004 | error | Each fragment's `exit_to` is within the enum (ci_gate/resident_sensor/dissolve). Missing or wrongly typed is also an error |
| GD005 | error | Reference integrity of `blocked_by` (the fragment/inbox id it points at exists in the dossier) |
| GD006 | error | Uniqueness of ids (no duplicates across oracles/fragments/sensors/inbox) |
| GD101 | error | REPORT_ONLY wiring violation: `findings_policy.fix_action == "REPORT_ONLY"` yet `enqueue: true` |
| GD102 | error | `status: approved` yet `routing_proof` is missing / a fragment with `auto_fix_allowed: false` is missing `why_not_auto_fix` |
| GD103 | error | An incompatible `wire_to` × `exit_to` combination (violating the §4.1 compatibility matrix) |
| GD104 | error | State invariants: `approved` yet unresolved `blocked_by` remains / `superseded` yet `superseded_by` is missing / a fragment of a status `rejected` dossier still carries an `exit_to` wiring |
| GD201 | error | A proxy oracle is missing one of the 6 required fields (§5.2), or has `judge_type: "llm_subjective"` |
| GD202 | error | Dangerous combination: `self_modification_risk: high` together with `auto_fix_allowed: true` |
| GD203 | error | A structural field (`oracle_files` / `command` / any `id`) contains an absolute path or a mixed-in secret |
| GD301 | warn | `oracle_files` is an empty array or glob-only (no explicit enumeration) |
| GD302 | warn | `goal.non_goals` is empty (risk of a wish expanding without bound) |

**Finding schema** (per finding): `{rule, severity, file, locator, message, fix}`. `locator` is a
fragment/oracle/inbox id or a JSON path (e.g. `fragments[2].why_not_auto_fix`). `message` carries
the what/why, and `fix` a concrete proposed correction.

**Exit codes**: `0` = pass (**warn-only is 0**) / `1` = an error-level finding exists / `2` = a
precondition failed (JSON parse failure, duplicate keys, an invalid path, a missing file, size
exceeded).

---

## 12. References

- [convergence-pattern.md](convergence-pattern.md) — Oracle / hash lock / oracle-gaming blocking
- [loop-engineering.md](loop-engineering.md) — Finding Schema / admission / Sensor Adapter / the self-modification gate
- [polling-pattern.md](polling-pattern.md) — Queue / Executor consumption
- [measurement-identity.md](measurement-identity.md) — the measurement series
- [fix-action-taxonomy.md](fix-action-taxonomy.md) / [severity-and-verdicts.md](severity-and-verdicts.md) — the classification axes
