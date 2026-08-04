# Measurement Identity — Shared Contract (unifying the join key for measurement)

> **⚠️ Warning:** This contract defines the measurement join key needed to answer "is the loop getting better?".
> Changing the schema, the enums, or the mapping table affects every writer (both polling adapters / skill-regression / trigger-eval)
> and every reader (skill-improve and others). When changing it, update the referencing skills in the same PR.

---

## 1. The problem — siloed measurement systems

This repository has five measurement systems, and none of them share a join key:

| System | What it measures | Existing store | Limitation |
|---|---|---|---|
| polling TickResult | Success/failure counters of a tick | None (volatile) | Disappears when the tick ends |
| skill-regression | Behavioral verification events | `ledger.json` | Only the latest entry (no history) |
| trigger-eval | Trigger-accuracy metrics | None (report only) | Cannot compare across runs |
| skill-improve | Session friction | session JSONL (read) | Anecdote-level, not joined to the instruction version |
| cycle results | The outcome of a plan run | `.agents/artifacts/plans/results` | Free-form text, not machine-aggregatable |

As things stand, "did this revision of SKILL.md raise the success rate?" cannot be answered even in principle.
**Adding another silo is not the solution** — unifying the join key is.

---

## 2. Identity Triple

Every measurement event is identified by these three keys:

| Key | Definition | SSOT |
|---|---|---|
| `skill` | The name (directory name) of the skill that governed the behavior of that run | `skills/<name>/` |
| `surface_sha256` | The behavior-surface fingerprint at the time of the run | The behavior-surface definition in `skills/skill-regression/scripts/dep_graph.py` + `ledger.py fingerprint()` (**re-implementation is forbidden**; always call the same implementation) |
| `run_id` | The UUID of the run event | The same family as `run_id` in [polling-pattern.md §7](polling-pattern.md#7-tick-result-schema) (it can also be correlated with the frontmatter of a failed issue) |

`surface_sha256` functions as **the version number of the instruction**. Comparing before and after a revision means
comparing "the results during the period of hash A vs the results during the period of hash B".

---

## 3. Event Record Schema

Append one event per line to `.agents/runtime/loop/events.jsonl` (the runtime area =
gitignored, outside commits, outside migration. The single-host premise is the same as polling. The runtime area is defined in
[artifact-store.md "Runtime area"](artifact-store.md#runtime-area)). **Structured fields only; no free-form text; no secrets** (inheriting the philosophy of TickResult §7).

```
Event {
  ts:             ISO8601
  system:         "polling-fs" | "polling-label" | "skill-regression" | "trigger-eval"
  event:          "tick" | "verification" | "eval"
  skill:          str
  surface_sha256: hex64
  run_id:         UUID | null
  outcome:        object   # per system (§4). Numbers and enums only
}
```

- `system` / `event` are closed enums. Additions are made as a revision of this contract (**No new silos rule**:
  when adding a new measurement, extend this schema rather than creating a new store)
- The append does not need to be an atomic write (one appended line, single host, single process)

---

## 4. Mapping table for the existing systems

| system | event | outcome fields | When to append |
|---|---|---|---|
| `polling-fs` / `polling-label` | `tick` | `{claimed, done, failed_transient, failed_permanent, halt_reason?}` (identical to TickResult §7) | Immediately after the tick emits its TickResult (the final Step of each SKILL.md). `skill` = issue / github-issue, and `surface_sha256` is computed at the start of the tick |
| `skill-regression` | `verification` | `{result: "pass" \| "accepted-addition" \| "accepted-prose" \| "accepted-without-run", scenarios?: int}` (`accepted-addition` = accepted without a run, but hash comparison mechanically confirmed the surface only gained files; `accepted-prose` = accepted without a run, but structural fingerprints mechanically confirmed only the prose of existing md files changed) | Immediately after running `ledger.py --update` (ledger.json holds only the latest; events hold the history) |
| `trigger-eval` | `eval` | `{recall, precision, stability}` (one line per target skill) | On completing the Tier 1/2 measurement |
| `empirical` | `tuning` | `{iterations, scenario_count, converged, final_precision, precision_delta, prompt_bytes_delta}` | On convergence (`exit_verdict == "converged"`). **Wired only when the target is a repo skill** (when the target is an arbitrary prompt, a CLAUDE.md section, and so on, `surface_sha256` cannot be computed, so the wiring is skipped. Record `instruction_fingerprint` in the iteration JSON instead) |

Read-only systems:

- **skill-improve**: a reader, not a writer. It correlates the friction in the session JSONL with the events by `run_id` /
  `skill` × `surface_sha256`, so it can analyze "under which instruction version did friction increase"
- **cycle (run manually)**: out of scope for v1. The success or failure of a cycle run through polling is captured by the `tick` event.
  Measuring a manual cycle is a future extension (to be made as a revision of this contract)

---

## 5. The join query (one command)

```bash
python3 skills/shared/scripts/measurement_identity.py report --skill issue \
  [--events .agents/runtime/loop/events.jsonl]
```

- Aggregates `{ticks, done, failed, success_rate, first_ts, last_ts}` per surface_sha256 and
  displays it as a table in chronological order
- States the success-rate difference between the two most recent surfaces (= the effect of the last revision)
- The aggregation is done by pure functions (`aggregate_by_surface` / `surface_delta`) and verified by unittests

---

## 6. Operations

- When `.agents/runtime/loop/events.jsonl` grows large, it may be moved monthly to `.agents/runtime/loop/archives/YYYY-MM.jsonl`
  (the same archive pattern as polling; report can span them by passing `--events` several times)
- If events remain at the old default path `.agents/artifacts/loop/events.jsonl` (before the runtime split),
  running `report` / `emit` with the default path emits an actionable warning (presenting the `mv` command to the new path).
  Passing `--events` explicitly gives that path top priority (backward compatibility)
- **Deleting or rewriting an event is forbidden** (append-only. A mis-recorded event stays as it is; do not overwrite it with the next correct event and do not amend it — this structurally eliminates the possibility of tampering with the measurements)
- Adding or changing a writer is done together with an update of this contract's mapping table (§4)

## 7. References

- [polling-pattern.md](polling-pattern.md) — where run_id / TickResult are defined
- [loop-engineering.md](loop-engineering.md) — the supply-side loop (finding_id is an identity on a different axis. Do not conflate them: finding_id is the identity of a "problem", this contract is the identity of a "run")
- `skills/skill-regression/` — the SSOT for the behavior surface and the fingerprint
