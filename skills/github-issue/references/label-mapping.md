## Label Mapping

**This section is the canonical SSOT.** The plan, `label-spec.md`, and the other references hold only direct links to this section and must never duplicate the body of the mapping table.

### State Mapping Table

| Shared contract State (§2) | The GitHub label set | Notes |
|---|---|---|
| `ready` | `{claude-auto}` only | `claude-running` / `claude-review` / `claude-failed-*` / `claude-failed` not attached |
| `running` | `{claude-auto, claude-running}` | The initial running |
| `running` (substate: review) | `{claude-auto, claude-running, claude-review}` OR `{claude-auto, claude-review}` | **A GitHub-specific intermediate state.** Subsumed into `running` of shared contract §2 |
| `done` | (already closed)| Every `claude-*` is removed at the moment of close |
| `failed/transient` | `{claude-auto, claude-failed-transient}` (+ the alias `claude-failed` dual-write) | Retryable on the next tick |
| `failed/permanent` | `{claude-auto, claude-failed-permanent}` (+ the alias `claude-failed` dual-write) | Awaiting human judgment |
| `archives` | — | On GitHub, close is equivalent to archives; no label is needed |

### is_running predicate (substate unification)

```
is_running(labels) := "claude-running" ∈ labels OR "claude-review" ∈ labels
```

`claude-review` does not appear in the state set of shared contract §2. It is isolated as a running substate inside the Label adapter, and the client-side filter of `list_ready()` excludes both.

### state_of_failure Precedence Rule

```
# Precedence: when a new label is present, ignore the old alias (guarding against a stale leftover)
state_of_failure(labels):
  if "claude-failed-transient" ∈ labels and "claude-failed-permanent" ∈ labels:
    warn("invalid state: both failure labels present")
    return PERMANENT                               # an invalid state is fail-closed (see below)
  if "claude-failed-transient" ∈ labels:  return TRANSIENT
  if "claude-failed-permanent" ∈ labels:  return PERMANENT
  if "claude-failed" ∈ labels:             return PERMANENT  # legacy alias
  return None

is_failed_transient(labels) := state_of_failure(labels) == TRANSIENT
is_failed_permanent(labels) := state_of_failure(labels) == PERMANENT
is_any_failed(labels)       := state_of_failure(labels) is not None
```

**Invalid-state detection**: when both `claude-failed-transient` and `claude-failed-permanent` are attached at once, treat it as an invalid state: a warning log plus handling as `failed/permanent` (fail-closed).

---

