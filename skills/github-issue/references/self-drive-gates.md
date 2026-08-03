## Self-Drive Gates

`claude-auto` declares that an issue may be driven **with no human present**. Until these gates existed,
that declaration was honoured by nothing but an agent reading the body and choosing to respect it —
the label spec called the body the source of truth, yet no step ever read, required, or interpreted the
body's verdict. This section is where that becomes machine-enforced.

Three of the four gates below live in the adapter; Gate 2 and Gate 3 live in the cycle workflow
([SKILL.md](../SKILL.md)) because they need the plan and the working tree.

| Gate | Where it runs | On rejection |
|---|---|---|
| Gate 0a — the claim gate (declared scope, blast radius) | `list_ready()` client-side filter | quiet skip |
| Gate 1 — the self-drive verdict | `list_ready()` client-side filter | quiet skip |
| Gate 0b — the halt gate (the plan's actual scope) | cycle, after the plan is built | permanent failed |
| Gate 2 — REOPENED context reconciliation | cycle, after the plan is built | permanent failed |
| Gate 3 — the zero-diff safety net | cycle, after the implementation phase | permanent failed |

**Quiet skip versus permanent failed** splits on who is at fault. Gate 0a / Gate 1 reject an issue whose
body does not meet the contract — a defect in how the issue was written, not a failed run. They write no
label and do not touch `failed_streak`, exactly like the `authorAssociation` filter. Gate 0b / 2 / 3 fire
after the issue was already claimed, so leaving them silent would leave `claude-running` stranded; they
stop through the normal permanent-failed path.

### Terminology: what self-driving means

**Self-driving means running to completion in an execution environment where no human is present.**

| Mode | Execution environment | Human | What a judgment call costs |
|---|---|---|---|
| **Self-driving** | polling loop, scheduled cloud run | absent | the moment one is needed the run is stuck; the only move is to stop |
| **Semi-automatic** | interactive session | present | it is settled on the spot and work continues |

These are not two ends of a continuum — they are **different execution environments**. Whether a human is
present is 0 or 1, so the self-drive verdict cannot be anything but two-valued.

`部分的に自走可` does not name a middle degree of self-driving. What it actually names is
**"this is semi-automatic work, not self-driving work"** — that is, `自走不可`. It is the name of the
other mode wearing the costume of a degree.

### `parse_self_drive_verdict(body)`

A pure function. Input is the issue body; output is one of `ALLOWED` / `FORBIDDEN` / `MISSING` / `AMBIGUOUS`.
The executable source of truth is `polling_adapter.py verdict --body-file F` — never re-derive
the parsing in prose or shell. Its contract: lines inside fenced code blocks are never scanned
(a quoted verdict line is not a verdict); the `## 自走可否` section runs up to the next `#` /
`##` heading; no section or no `判定:` line → `MISSING`; contradictory or non-single-token
values → `AMBIGUOUS`; only `自走可` → `ALLOWED`, only `自走不可` → `FORBIDDEN`, every other
value → `AMBIGUOUS`.

**The value must be matched whole, never as a substring.** `部分的に自走可` ends in the characters
`自走可`, so a substring test would read the one forbidden value as permission — the exact inversion of
what this gate is for. The anchored `^判定:\s*(\S+)\s*$` capture is what prevents it.

| Body | Verdict | list_ready |
|---|---|---|
| `## 自走可否` + `判定: 自走可` | `ALLOWED` | claimed |
| `## 自走可否` + `判定: 自走不可` | `FORBIDDEN` | quiet skip |
| `## 自走可否` + `判定: 部分的に自走可` | `AMBIGUOUS` | quiet skip |
| `## 自走可否` present, no `判定:` line | `MISSING` | quiet skip |
| no `## 自走可否` section | `MISSING` | quiet skip |

**Fail-closed**: only `ALLOWED` claims. `FORBIDDEN` / `MISSING` / `AMBIGUOUS` all quiet-skip.

#### Why `部分的に自走可` is a forbidden value rather than a third state

1. **No gate can enforce it.** The self-drive verdict is not a property of the issue's contents but of
   **the unit the loop claims**. The loop claims one whole issue; "claim half of it" is not an operation
   that exists. `自走可` / `自走不可` are enforceable as claim decisions; `部分的に自走可` can only be
   enforced by an agent reading the body and restraining itself. It demotes a machine gate to an honour system.
2. **The body turns into a lie the moment the work lands.** Once the self-drivable part is done, the body
   keeps advertising completed work as self-drivable, and what remains is exactly the part nobody may touch.
   The more faithfully an agent follows the body, the more surely it reaches into the forbidden half.
3. **Writing it means the decomposition is already finished.** "A is self-drivable, B needs a human" is a
   completed triage; the issue simply was not split. The value is not a verdict — it is an unfinished
   issue-splitting task wearing a verdict's clothes.

An issue that is only partly self-drivable gets the self-drivable part split into its own issue.

### `parse_change_targets(body)`

A pure function. Input is the issue body; output is an ordered, de-duplicated `list[Path]`, or `MISSING`.
The executable source of truth is `polling_adapter.py change-targets --body-file F`. Its
contract: fenced blocks ignored as above; only `- X` / `* X` list items whose whole text
(after stripping wrapping backticks) matches `^[A-Za-z0-9._\-/]+$` count; an item failing the
character set drops that item only; an item containing `..` or starting with `/` rejects the
whole declaration as `MISSING`; the result is order-preserving and de-duplicated, and an
empty result is `MISSING`.

- **Only a list item that is exactly a path counts.** Real bodies carry a second list under the same
  heading annotating each file, in the form `- a/b.md:170 — what to fix here`, and those must not be read
  as declarations. Requiring the whole item to match the path character set drops them: a line reference
  contains `:`, an annotation contains spaces.
- **The two checks reject at different scopes, and the difference is deliberate.** Failing the path
  character set skips **that item only** (`continue`) — that is exactly what lets the annotated list
  above be ignored — and it runs first, so an annotated item that also contains `..` is still just
  dropped. Failing the traversal / absolute-path check rejects **the whole declaration** (`MISSING`),
  because an item of that shape is evidence the body is malformed or hostile. Dropping it silently and
  carrying on with the rest would hand Gate 0a a shortened path list, so both of its checks loosen:
  `forbidden_path_globs` can no longer see the dropped entry, and `impact_units` measures less than
  the change actually reaches — **underestimating the blast radius**, the one error this gate must
  not make. (Gate 0b moves the other way: a shorter declared set makes `plan_paths ⊆ declared_paths`
  harder to satisfy, not easier.)
- `MISSING` is a Gate 0a quiet skip.

### `impact_units(paths, config)`

Executed inside `polling_adapter.py gate0` (and available standalone). Contract: unset
`config.impact_command` → `NO_ORACLE` (Gate 0's impact check is a no-op — see
config-defaults.md); `{files}` expands to the shell-quoted paths; a non-zero exit is
`Err("impact_oracle_failed")` — fail-closed, NEVER read a non-zero exit as 0 impacted units;
otherwise the non-empty output lines are the impacted units.

Every path handed to the oracle has already passed `parse_change_targets`'s character-set validation, so
the expansion cannot inject shell metacharacters.

### `gate_0_decision(paths, config)`

The executable source of truth is `polling_adapter.py gate0 --paths-json F --config-json F`.
Contract, in order: ① the forbidden-path glob check (needs no oracle, so it holds in every
repository) → `REJECT("forbidden_path")`; ② the blast-radius check via `impact_units` —
`NO_ORACLE` → `ALLOW`, oracle error → `REJECT` (fail-closed), more units than
`config.max_impacted_units` → `REJECT("impact_too_wide")`, else `ALLOW`.

The three rejection reasons are distinguishable in the log, but all three behave identically at the gate
they run in — quiet skip in Gate 0a, permanent failed in Gate 0b.

### Gate 0b — the halt gate

The issue author's declaration cannot be trusted on its own, so once the plan is fixed the **actual**
target set is re-examined. Run both checks in [SKILL.md](../SKILL.md) Cycle Step 3, after the plan is built:

1. **Scope containment**: `plan_paths ⊆ declared_paths`. The declaration is the source of truth for scope,
   and a plan may not widen it on its own. Any path outside it → permanent failed
2. **Blast radius**: `gate_0_decision(plan_paths, config)` → on `REJECT`, permanent failed

Do not start implementing on either. Both record `error_kind = "abort"` (see [§error_kind Enum](error-kinds.md#error_kind-enum)); the
distinguishing detail goes in the halt reason (`gate0b_scope_violation` / `gate0b_{reason}`), so no new
`error_kind` value is introduced.

---

