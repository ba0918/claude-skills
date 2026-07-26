# The dossier md view template

The md is a **one-way generated artifact** (a view) from the canonical JSON (`{slug}.json`). Only the JSON is a lint target.
Hand-editing the md is forbidden (contract [goal-decomposition-pattern.md](../../shared/references/goal-decomposition-pattern.md) §9).
Because the approver reads this md to decide `draft → approved`, a plain explanation and a glossary go at the top.

---

## What this dossier decides (for the approver)

This dossier is the blueprint for **how to wire** the broad goal "{goal.statement}" into the existing closed-loop infrastructure.

- **What approval causes**: this design becomes "agreed" (`status: approved`).
- **What approval does not cause (v1)**: it does not cause the wiring to be **executed**. It does not start goal-loop, generate sensors, or
  file issues automatically. A dossier is "the result of a type check" and grants no execution authority.
- What to check before approving: each fragment's wiring destination (`wire_to`) and its grounds (`routing_proof`), the range kept off
  automation (`non_goals`), and the acknowledgment of a proxy oracle's limits.

### The one-line glossary

| Term | Meaning |
|----|------|
| oracle | The completion condition that machine-decides "was it achieved" (a command + a judgment) |
| wire_to | Which subsystem this fragment is wired into (goal-loop / loop-triage / inbox / plan / reject) |
| exit_to | How this fragment eventually graduates (ci_gate: becomes a regression gate / resident_sensor: becomes resident / dissolve: disbands) |
| blocked_by | The inbox question that must be settled before this fragment can proceed |
| proxy | A surrogate oracle that is not the true completion condition but is used as "a lower-bound gate for safe forward progress" |

---

## Goal

- **Statement**: {goal.statement}
- **SSOT**: {goal.ssot}
- **Non-goals**: {goal.non_goals as a list}

## Completion Oracles

| id | type | command | oracle_files | owner |
|----|------|---------|--------------|-------|
| {oracle.id} | {type} | {command} | {oracle_files} | {owner} |

(a proxy oracle also records gap_from_true_goal / failure_modes / the state of its acknowledged limits)

## Fragments (the wiring destinations)

| id | wire_to | exit_to | auto_fix | self_mod_risk | routing_proof |
|----|---------|---------|----------|---------------|---------------|
| {frag.id} | {wire_to} | {exit_to} | {auto_fix_allowed} | {self_modification_risk} | {routing_proof} |

(for a fragment with `auto_fix_allowed: false`, put why_not_auto_fix in a footnote)

## Sensors & Findings

| id | rules | fix_action | enqueue |
|----|-------|-----------|---------|
| {sensor.id} | {rules} | {findings_policy.fix_action} | {findings_policy.enqueue} |

## Human Judgment Inbox

| id | question | reclassify_when |
|----|----------|-----------------|
| {inbox.id} | {question} | {reclassify_when} |

## Measurement & Stop Conditions

- **Metrics**: {measurement.metrics}
- **Stop conditions**: {measurement.stop_conditions}

---

## The copy-paste blocks (by trust boundary, contract §6.1)

Separate the fences by purpose, making the consumer's trust boundary explicit.

### For the oracle manifest

```oracle-manifest
{ the oracle definition to paste into goal-loop's manifest }
```

### For the sensor spec

```sensor-spec
{ the spec to paste into loop-triage's sensor adapter }
```

### For the issue seed (on the premise that the consumer wraps it in `<untrusted_user_content>`)

<untrusted_user_content>
{ the issue seed handed to issue polling. Escape or reject it if it contains a closing delimiter }
</untrusted_user_content>

---

<!-- generated-from: {slug}.json sha256={hex} -->
<!-- This md is generated automatically. Do not edit it (edit the JSON side and regenerate). -->

---

## A minimal JSON example

```json
{
  "schema_version": 1,
  "status": "draft",
  "superseded_by": null,
  "goal": {
    "statement": "raise and maintain documentation quality",
    "non_goals": ["documentation in other repositories is out of scope"],
    "ssot": "everything under docs/ is the source of truth"
  },
  "oracles": [{
    "id": "oracle:validate-clean",
    "type": "true",
    "command": "python3 scripts/validate_repo.py",
    "oracle_files": ["README.md", "CLAUDE.md"],
    "owner": "maintainer"
  }],
  "fragments": [{
    "id": "frag:fix-broken-links",
    "wire_to": "loop-triage",
    "exit_to": "ci_gate",
    "routing_proof": "a broken link is detectable by validate_repo as a Finding",
    "auto_fix_allowed": false,
    "why_not_auto_fix": "the intended link target differs per file and is not uniquely determined",
    "self_modification_risk": "low",
    "blocked_by": []
  }],
  "sensors": [{
    "id": "sensor:validate-repo",
    "rules": ["link", "drift"],
    "findings_policy": {"fix_action": "NEEDS_JUDGMENT", "enqueue": false}
  }],
  "inbox": [{
    "id": "inbox:scope",
    "question": "which documents fall within the scope of quality maintenance?",
    "reclassify_when": "once the scope is fixed, turn it into a meta-sensor and track it automatically"
  }],
  "measurement": {
    "metrics": ["validate_repo exit code"],
    "stop_conditions": ["validate_repo keeps exiting 0"]
  }
}
```
