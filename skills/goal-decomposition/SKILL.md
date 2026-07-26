---
name: goal-decomposition
description: Compile a broad goal (for example "go through the whole codebase and finish the refactoring") into a Loop Readiness Dossier (the result of type-checking whether it can run autonomously), and mechanically decide where it wires into the existing closed-loop infrastructure (goal-loop / loop-triage / issue polling). Its main product is mechanically explaining and stopping the fragments that must not run autonomously, and it never performs the wiring itself (type-checking only). Use when the user says "goal-decomposition", "a broad goal", "put this on a loop", "make this able to run itself", "dossier", "decompose the goal and wire it up", "loop readiness", or "can this goal be automated". For this repository only.
---

# Goal Decomposition

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

The entry point that compiles a natural-language high-level goal into a machine-verifiable **Loop Readiness Dossier**.

**Shared contract (required reading, direct link):** [../shared/references/goal-decomposition-pattern.md](../shared/references/goal-decomposition-pattern.md)

- The Dossier Schema, the first-question decision tree, the 5-axis routing proof, the status lifecycle,
  the wire_to×exit_to matrix, the conditions under which a proxy is acceptable, the supply gap playbook, and the mapping tables all live in the contract.
  This SKILL.md is a thin orchestrator and never duplicates the contract
- Where the classification axes are defined: [fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md) (AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY)
- The downstream consumers are [issue polling](../issue/SKILL.md) / [loop-triage](../loop-triage/SKILL.md) / [goal-loop](../goal-loop/SKILL.md)

## Invariants (contract §1 / §6)

1. **compile never performs the wiring.** All it produces is `.agents/artifacts/loop/dossiers/{ts}_{slug}.json` plus `.md`
2. **compile always outputs `status: draft`.** A human moves it to approved by editing the dossier directly
3. **approved grants no execution authority** (v1 is type checking only, and the lint is read-only)
4. For fragments you have not observed, do not inflate confidence — drop them into the inbox with `blocked_by`

## Execution contract

- Call the scripts by absolute path: `python3 {skill_dir}/scripts/dossier_lint.py`. `{skill_dir}` is this SKILL.md's directory and `{repo_root}` is the repository root (usually the cwd)
- Where dossiers live: `.agents/artifacts/loop/dossiers/{timestamp}_{slug}.json` (canonical) plus a `.md` of the same name (the view)
- secret_detect is an import-only module with no CLI (**import and use** `detect_secrets` / `mask_secrets`; never describe it as "running a script")

## Workflow selection

| Input | Workflow |
|------|-------------|
| A natural-language high-level goal ("I want this on a loop", "get it to a self-driving state") | compile |
| Inspecting an existing dossier ("lint the dossier", "validate") | validate |

## compile — goal → dossier draft

### Step 1: Investigation (scope-limited)

Limit the investigation to the paths related to the goal and the oracle_files candidates. **Do not do a full-tree scan.**
Fill in yourself what the codebase can answer (existing sensors, oracle command candidates, the SSOT) and what the contract
lets you infer (the decision tree's exits, the mapping destinations).

### Step 2: Fragment decomposition and wiring (the decision tree)

Split the high-level goal into fragments and, applying contract §3's first question to each (is it a completion condition / a non-attainment detector / a human judgment), decide
its `wire_to` (goal-loop / loop-triage / inbox / plan / reject). After wiring, fill in
`auto_fix_allowed` / `self_modification_risk` / `exit_to` along the 5 axes of §4 and write a one-line `routing_proof` for each fragment
(`why_not_auto_fix` is mandatory for non-AUTO_FIX fragments).

- **Handling proxies** (the decision tree has no explicit leaf for them): for a fragment that is a completion condition whose true oracle cannot be mechanized,
  consider the proxy / intermediate oracle of §5.2 / §10 ③, and it may be wired to goal-loop as blocked with
  `human_limit_approved: false` and pending inbox approval. Even headless, compile may make the **adoption decision** for a proxy
  (the human guarantee is held by the approval gate = GD104)
- **oracle.command need not exist yet** (a dossier is a blueprint and is not executed). For an unimplemented command,
  add a word noting that it is aspirational, either in the routing_proof or on the oracle side
- **oracle_files locks the verifier** — enumerate "the side that defines the meaning of the oracle" (verification scripts, tests,
  and expected values; the same sense as [convergence-pattern §2](../shared/references/convergence-pattern.md)).
  The target documents being fixed are not lock targets (include them only when the target doubles as the verification definition)
- **Choosing between exit_to values** (when the matrix permits both): make `resident_sensor` the default for resident detection, and
  choose `ci_gate` only when the intent to promote it to a permanent block is clear
- **measurement.metrics**: mark a new, not-yet-connected measurement explicitly with the `proposed:` prefix so it is distinguished from existing measurement names
  (events.jsonl, the ledger, and so on)

### Step 3: Three questions for the human (skipped when headless)

Do not bombard them with questions. Ask the human only these three (with fixed wording):

1. **Confirm the non-goals**: "what range is excluded from this goal (the fragments kept off automation)? For example: {the inferred non-goals}"
2. **Approve the proxy's limits**: only when a proxy oracle is used — "{oracle} is not the true completion condition but a lower-bound gate.
   Do you approve it as the lower bound, knowing the gap '{gap}'?"
3. **Approve the routing proof's gaps**: "{fragment} was wired to {wire_to} (grounds: {proof}). Is this wiring acceptable?"

**When headless, skip the confirmation with the user and emit the draft**, recording the unresolved approval items as an inbox entry plus
`blocked_by` (the state gate guarantees human approval, so compile does not block on dialogue).

### Step 4: secret redaction (contract §9, import-based)

The order of the write-out pipeline: **generate the JSON → check for secrets → abort on detection → generate the md only on success**.
In practice: write the JSON first as a temporary file under `.claude/tmp/goal-decomposition/` and inspect it there.
On success, place it into `.agents/artifacts/loop/dossiers/`; on detection, delete the temporary file and abort
(never put an uninspected file into the dossiers directory, and never leave debris behind on a detection).

- **Free-text fields** (`goal.statement` / `inbox[].question` / `routing_proof`, etc.) are masked with `mask_secrets`
- **Structural fields** (`oracle_files` / hash values / `id`) use `detect_secrets`, and **a detection aborts the compile**
  (do not silently destroy them by masking)

### Step 5: Write-out and lint

1. Write `.agents/artifacts/loop/dossiers/{timestamp}_{slug}.json` (`status: "draft"`)
2. Generate the md view conforming to [dossier-template.md](references/dossier-template.md). The md is a **one-way generation**
   from the redacted JSON, plus a sha256 marker of the source JSON at the end (tamper-evident). Hand-editing the md is forbidden
3. Inspect it with `python3 {skill_dir}/scripts/dossier_lint.py .agents/artifacts/loop/dossiers/{timestamp}_{slug}.json`

### Step 6: Report (summary-first)

```
## Goal Decomposition result: {slug}
| wire_to | Count |
|---------|------|
| goal-loop | N |
| loop-triage | N |
| inbox | N |
| plan / reject | N / N |

- inbox / blocked_by: {count}
- Secret check: {pass / aborted (the affected field)}
- lint: {all checks passed / error N, warn N}
- status: draft
- The next move: read the md (.agents/artifacts/loop/dossiers/{slug}.md), and to approve it, edit the JSON directly and raise status to approved
```

## validate — inspecting a dossier

```bash
python3 {skill_dir}/scripts/dossier_lint.py [.agents/artifacts/loop/dossiers/{slug}.json ...]
```

- With no argument, inspect every `*.json` directly under `.agents/artifacts/loop/dossiers/`. When asked to inspect a specific dossier,
  pass only that path as an argument (do not drag unrelated dossiers in)
- Exit codes: `0` = pass (warnings alone are also 0) / `1` = an error-level finding / `2` = a prerequisite does not hold
- If there is an error-level finding, present it and propose a fix by consulting the rule table of contract §11 (the lint itself fixes nothing).
  The inspection result is a text report only — validate never writes a file (compile is the only writer)

## Preventing rationalization

| Excuse | Reality |
|--------|------|
| "This fragment is obviously automatable, so let us emit it as approved" | compile emits nothing but a draft (invariant 2). Approval is a human's job |
| "The oracle is big, but let us make it a proxy and pass it with an LLM judge" | Subjective evaluation by an LLM judge is forbidden by GD201. Add an intermediate oracle instead (contract §10 ③) |
| "Let us take the easy road and put docs/** in oracle_files wholesale" | goal_loop verify centers on the paths recorded in the manifest. Enumerate them explicitly (contract §8, GD301) |
| "It looks like a secret, but it is a structural field, so masking will get it through" | Structural fields are not masked; the compile aborts (contract §9). Do not create silent destruction |
