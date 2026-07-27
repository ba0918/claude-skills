# Loop Engineering — Shared Contract (sensor → triage → queue admission)

> **⚠️ Warning:** This contract is the central specification of the closed loop that
> "autonomously discovers problems in the repository and supplies them as work to the existing
> polling loop". Changes can affect the sensor / triage implementations
> (`skills/loop-triage/` and others) and every adapter of
> [polling-pattern.md](polling-pattern.md). When changing the schema, the admission table, or
> the gate rules, update the references and SKILL.md of the referencing skills in sync within
> the same PR.

---

## 1. Overview — the 5 layers of responsibility

Connects an Osmani-style self-driving loop (discover → delegate → verify → learn) **upstream**
of this repository's existing contracts.

| Layer | Responsibility | Implementation |
|---|---|---|
| Sensor | Detect problems in the repository and emit JSON per the §2 Finding Schema | validate_repo.py / ledger --check / context-audit etc. (§7) |
| Triage | Assign identity → deduplicate → classify admission → enqueue/demote | `skills/loop-triage/` (pure functions + a thin orchestrator) |
| Queue | Durable queue of work | `.agents/artifacts/issues/ready/` ([polling-pattern.md](polling-pattern.md) FS adapter) |
| Executor | Consume the queue and implement | issue polling → parallel-cycle (existing) |
| Verifier | Verify the changes | validate_repo CI + skill-regression ledger + trigger-eval (existing) |

**Triage does not edit**. It only generates issue files and appends to inbox / digest;
fixing code or docs is always the Executor's (cycle's) job.

---

## 2. Finding Schema

One finding emitted by a sensor. The field set is immutable (adding to it requires a revision
of this contract).

```
Finding {
  sensor:          str            # sensor identifier (e.g. "validate-repo", "context-audit", "ledger-check")
  rule:            str            # rule ID within the sensor (e.g. "CA-D001", "sync", "stale")
  severity:        BLOCK | WARN | INFO           # follows the definitions in severity-and-verdicts.md
  fix_action:      AUTO_FIX | NEEDS_JUDGMENT | REPORT_ONLY   # follows the definitions in fix-action-taxonomy.md
  where:           { path: str, line?: int }     # detection location. identity uses path only (§3)
  what:            str            # what the problem is (1 line, must already be secret-redacted)
  why?:            str            # why it is a problem (optional)
  suggested_title: str            # proposed title if turned into an issue
  affected_paths:  [str]          # files the fix is expected to touch (input to the self-modification gate, §5)
}
```

- The semantics of severity / fix_action follow their defining documents
  ([severity-and-verdicts.md](severity-and-verdicts.md) /
  [fix-action-taxonomy.md](fix-action-taxonomy.md)) and are not redefined here
- `what` must not contain secrets or PII (the sensor's responsibility;
  `skills/shared/scripts/secret_detect.py` is available)
- A finding with an unknown or missing fix_action is **normalized to REPORT_ONLY** (fail-safe)

---

## 3. Finding Identity & Deduplication

Sensors re-detect the same finding every run. Without deduplication the loop piles up the same
issue every morning.

### 3.1 Stable Finding ID

```
finding_id = sha256(f"{sensor}|{rule}|{where.path}|{what}")[:16]
```

- **Do not include the line number** (a countermeasure to the known limitation of context-audit
  baseline v1, where the ID changes when lines move. Findings of the same kind within one file
  are distinguished by their differing `what`)
- Because `what` is already redacted and then hashed, the ID is opaque (committing it to a
  baseline leaks nothing confidential)

### 3.2 Double-admission Prevention (queue dedup)

- Always record `finding_id: <hex16>` in the frontmatter of the issue being enqueued
- Before enqueuing, Triage scans under `.agents/artifacts/issues/` (`ready/`, `running/`,
  `failed/**`, and `*.md` at the top level) and, if an open issue with the same `finding_id`
  exists, **does not enqueue it as a duplicate** (reports the count only)
- `archives/` is **not** included in the comparison (if a resolved problem has recurred, a new
  issue is correct)

### 3.3 Baseline suppression (intentional differences)

- Store suppressed finding_ids in `.agents/config/loop-baseline.json` (**opaque IDs only — never put
  detected values or body text in it**. The format and operation follow the same philosophy as
  [the context-audit baseline](../../context-audit/references/baseline-format.md), with the
  same `{version, suppressions[]}` schema)
- Suppressed findings are **reported by count only** (silent truncation is prohibited)

---

## 4. Admission Policy (fix_action × severity → route)

Where a finding flows is decided by the following **pure-function routing**. No LLM discretion
is involved.

| fix_action \ severity | BLOCK | WARN | INFO |
|---|---|---|---|
| `AUTO_FIX` | enqueue | enqueue | digest |
| `NEEDS_JUDGMENT` | inbox | inbox | digest |
| `REPORT_ONLY` | digest | digest | digest |

| Route | Meaning |
|---|---|
| `enqueue` | Generate an issue in `.agents/artifacts/issues/ready/` and make it consumable by the polling loop |
| `inbox` | Append to `.agents/artifacts/loop/inbox.md` and wait for human judgement (never proceed automatically) |
| `digest` | Record it in the run report only |
| `duplicate` / `suppressed` | Not enqueued; report the count only (§3) |

**Invariants:**

1. `REPORT_ONLY` is never enqueued under any condition (inheriting from fix-action-taxonomy the
   non-automation of deletions, body rewrites, and secret handling)
2. The fix_action / severity used for routing are **the sensor's declared values**, and Triage
   must not promote them (only demotion — a change toward the safe side — is permitted; the
   gate demotion of §5 is the only such change)
3. A single triage run may enqueue at most `max_enqueue_per_run` (default **5**) findings. The
   excess is demoted to inbox, and the fact that there was an excess must always be reported
   (a silent cap is prohibited)

---

## 5. Self-Modification Gate

This loop's Executor (cycle) can edit the files that define the loop itself (SKILL.md, shared
contracts, validate scripts). Allowing that unconditionally lets "tuned behavior" be rewritten
without verification.

### 5.1 loop-defining files

Files matching the following globs are **loop-defining**:

```
skills/*/SKILL.md
skills/*/references/**
skills/shared/**
commands/**
scripts/validate_repo.py
.agents/config/review-rules.md
```

### 5.2 Gate Rule (demotion at enqueue time)

For a finding whose `affected_paths` include a loop-defining file, before enqueuing, look up
the impacted skills in reverse via the [skill-regression](../../skill-regression/SKILL.md)
dependency graph (`dep_graph.py`), then:

- **All** impacted skills have fixtures (`fixtures.json`) → enqueue is allowed. Add
  `gate: skill-regression` to the issue frontmatter
- Even one impacted skill lacks fixtures → **demote to inbox even for AUTO_FIX**. State the
  demotion reason (the names of the fixture-less skills) explicitly in the inbox entry

> Principle: **automate self-modification only within the range covered by the regression safety
> net**. Where there is no net, a human judges.
> The legitimate way to widen automation is not loosening the gate but increasing fixture
> coverage.

### 5.3 Downstream Mechanical Enforcement

The gate is enforced by existing CI, not by a prose promise:

- If the cycle for an issue carrying `gate: skill-regression` changes the behavioral surface,
  `ledger.py --check` fails in CI (the existing gate of
  [skill-regression](../../skill-regression/SKILL.md)). The cycle cannot land on main unless it
  completes a run → `--update` (or a `--accept` with a stated reason) before finishing
- If the description was changed, re-measuring with trigger-eval is recommended (regressions on
  the triggering surface are not caught by the ledger)

---

## 6. Safety

- Making Triage itself self-driving (scheduled runs) follows the safety brakes of
  [polling-pattern.md](polling-pattern.md) (kill file / max_iter / max_wallclock /
  failed_streak; for cron operation, §6.5 Tick Session). Do not add an autonomous loop without
  brakes to this repository ([orchestration-patterns.md](orchestration-patterns.md) governing
  principle 3)
- All Triage output is append-only or generative (issue generation / inbox append / digest).
  **It does not delete or rewrite existing files** (the sole exception is appending a line to
  issue-status.md)
- Do not write secrets into inbox or digest (do not trust the sensor's redaction; pass the text
  through `secret_detect.py` on the Triage side as well before writing it out)

---

## 7. Sensor Adapter Contract

A sensor can be anything that "can emit an array of §2 Finding JSON to stdout or to a specified
file".

| Sensor kind | Examples | Notes |
|---|---|---|
| Mechanical sensors (deterministic, no LLM) | violations from validate_repo.py, `stale` from `ledger.py --check`, collision pairs from `static_collisions.py` | A conversion adapter (`sensors/*.py`) normalizes the output into Finding JSON |
| LLM sensors | context-audit / doc-check / doc-audit / skill-improve | Map each skill's findings JSON onto the Finding Schema. Use each skill's declared fix_action as-is |

- A sensor only **detects**; it does not fix (the same invariant as Triage)
- Adding a new sensor must require nothing more than adding an adapter script (Open-Closed. The
  Triage core and the admission table stay unchanged)

---

## 8. References

- [polling-pattern.md](polling-pattern.md) — the contract for the Queue / Executor layers
- [fix-action-taxonomy.md](fix-action-taxonomy.md) / [severity-and-verdicts.md](severity-and-verdicts.md) — where the classification axes are defined
- [orchestration-patterns.md](orchestration-patterns.md) — safety-brake principles for autonomous loops
- [verification-gate.md](verification-gate.md) — pre-completion verification on the Executor side
- `skills/skill-regression/` — the dependency graph and CI enforcement of the self-modification gate
