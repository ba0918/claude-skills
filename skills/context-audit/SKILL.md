---
name: context-audit
description: An inventory skill that audits LLM instruction files (CLAUDE.md / AGENTS.md / .claude/rules / project memory) for decay, contradiction, harmful instructions, and cross-tool divergence. It verifies mechanically with a pure-function rule engine (the CA-* rule system), handles findings with the 3 values AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY, and never automates deletion. It owns "quality as instructions", which neither doc-check (code vs docs) nor doc-audit (docs vs docs) looks at. Use when the user says "context-audit", "audit the instruction files", "take inventory of CLAUDE.md", "audit AGENTS.md", "review the memory files", "the instructions have rotted", or "check whether the instructions are stale".
---

# context-audit

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

The behavioral quality of an LLM depends on the health of the instruction layer (CLAUDE.md / AGENTS.md / rules / memory).
When that layer decays over long-term operation (obsolete references, contradictions, destructive permissions, cross-tool divergence), the LLM's behavior degrades — yet the existing doc-check (docs⇔code) and doc-audit (docs⇔docs) do not look at this "**quality as instructions**",
and project memory falls within the reach of no skill at all. context-audit takes on this stocktaking.

**Positioning**: whereas doc-check owns code accuracy and doc-audit owns consistency among documents,
context-audit owns instruction-bearing files as "instruction quality".

## Architecture: centered on pure-function rules

The same structure as trigger-eval / skill-improve: "**pure functions are verified by unittest; the agent only produces and passes JSON**".
The audit logic is consolidated into Python scripts, and SKILL.md handles only workflow control, LLM judgment (the REPORT_ONLY classification of CA-C001 contradictions and the presentation of NEEDS_JUDGMENT), and the application of AUTO_FIX. Determinism never leaks into the glue (the body of SKILL.md).

| Script | Role |
|-----------|------|
| `scripts/collect_targets.py` | Collects and classifies the audit targets with a path allowlist (deterministic). Resolves cwd→the memory slug + reverse-verify |
| `scripts/static_checks.py` | The pure-function rule engine (the `RULES` registry and dispatcher). Emits the findings JSON |
| `scripts/apply_fixes.py` | The pure function applying AUTO_FIX (findings + content → new content. Body bytes unchanged, idempotent) |
| `scripts/aggregate_report.py` | findings + baseline → a summary-first report (applying suppression, aggregating severity) |
| The entity behind `scripts/secret_detect.py` | `skills/shared/scripts/secret_detect.py` (shared with skill-improve, reused) |

Reference material (progressive disclosure):

- The rule definitions: [references/rule-catalog.md](references/rule-catalog.md)
- The details of memory auditing and the privacy constraints: [references/memory-audit.md](references/memory-audit.md)
- The schema and operation of baseline suppression: [references/baseline-format.md](references/baseline-format.md)
- The definition of the 3 fix-action values: [../shared/references/fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md)
- The definition of severity: [../shared/references/severity-and-verdicts.md](../shared/references/severity-and-verdicts.md)
- Completion verification: [../shared/references/verification-gate.md](../shared/references/verification-gate.md)

## Arguments

- No argument: audit the instruction files of the current repository plus the project memory corresponding to cwd.
- `--include-global`: additionally target `~/.claude/CLAUDE.md` and `~/.claude/rules/*.md` (a privacy opt-in).
- `--update-baseline`: fix the current findings into the baseline (thereafter only new findings are presented). The implementation is `aggregate_report.py --update-baseline PATH` (the LLM never gathers IDs by hand).
- `--interactive`: resume the NEEDS_JUDGMENT interactive prompts (continuing past the cap of a single run).

No command is created (the skills-first policy; being single-workflow, it needs no named entry point either).

## The execution contract (path resolution, the non-interactive fallback)

- **Resolving script paths**: `{skill_dir}` in the command examples below is **the directory where this skill itself lives** (the base directory presented when the skill is loaded; under a plugin installation it sits inside the cache). Start scripts with an **absolute path**. `{project_root}` is **the user's project root (cwd)** and is passed as the root argument for the audit targets (keep root equal to cwd, because root is also used for memory slug resolution).
- **The non-interactive fallback**: when the [execution context](../shared/references/execution-context.md) is headless, **the user's prior explicit instruction takes highest priority** (if an instruction equivalent to one of the options exists, follow it. For example "fix it as the baseline" = the equivalent of (a)). Absent an explicit instruction, fall to the safe side that changes no state — the first run behaves as **the equivalent of (c), the full report** (the baseline is not written), and the AUTO_FIX / NEEDS_JUDGMENT of Phase 4 are **not applied but sent to the report** (in the report, present NEEDS_JUDGMENT in its own independent frame so it is not confused with REPORT_ONLY).
- `{ts}` is numbered with `date +%Y%m%d-%H%M%S` and the same value is reused across phases (existing artifacts are never overwritten).

## Workflow

Every output goes to `.agents/tmp/context-audit/` (under the audited project, git-ignored).

### Phase 0: Discovery

```bash
python3 {skill_dir}/scripts/collect_targets.py {project_root} \
  --output .agents/tmp/context-audit/targets-{ts}.json
```

(`{skill_dir}` is the directory where this skill lives, `{project_root}` is the user's project root = cwd. See the execution contract)

- Collect the targets with a **path allowlist (deterministic, a pure function)**. The targets: the root's `CLAUDE.md` / `AGENTS.md`,
  `.claude/rules/*.md` / `rules/*.md`, `.agents/config/review-rules.md`, plus the project memory corresponding to cwd.
- A nonexistent target (for example, no `.claude/rules/`) is graceful-skipped (recorded in `skipped`, never an error).
- CLAUDE.md/AGENTS.md in nested subdirectories, and archival/temporary areas such as `.agents/artifacts/plans/`, `.agents/artifacts/ideas/`, and `.agents/tmp/`, are
  not included in the allowlist (that is, they are excluded).
- A single non-UTF-8 or unreadable file never interrupts the whole audit (`errors='replace'` / skip-and-report).
- Global settings are added only when `--include-global` is given.
- **On detecting that the baseline is absent, present the first-run flow** to the user and ask them to choose: "(a) fix the current state as the baseline and present only new findings thereafter / (b) triage only the top severities / (c) the full report". This avoids overwhelming them on the first run.
- State `memory_dir` (the resolved absolute path) in the report, making visible which project was read.
  (Because the per-finding `where` has its home path masked by redaction, the authoritative disclosure of what was audited is
  this Phase 0 `memory_dir` field.)

### Phase 1: Static Checks

```bash
python3 {skill_dir}/scripts/static_checks.py \
  .agents/tmp/context-audit/targets-{ts}.json --root {project_root} \
  --output .agents/tmp/context-audit/findings-{ts}.json
```

- Run the `RULES` registry in one pass and emit the findings JSON.
- The finding schema is common to every rule and requires `id / severity / action / where(file:line) / what / why / how /
  fix_action(old→new|null)`.
- **Apply secret redaction to the line-context of every finding before serializing** (`finalize_findings`).
  Neither detected values nor raw secret lines survive into the JSON.

### Phase 2: LLM Checks (REPORT_ONLY)

- The LLM classifies the CA-C001 contradiction candidates extracted by `static_checks.py` (an over-generation favoring recall) into "a contradiction / an intentional difference / already resolved by precedence / unclear". **It performs no fixes.**
- When there are 0 candidates, Phase 2 may be skipped entirely.
- What is handed to the LLM is **only the redacted, normalized minimal claim text** (raw memory lines and PII are never handed over).

### Phase 3: Aggregate

```bash
python3 {skill_dir}/scripts/aggregate_report.py \
  .agents/tmp/context-audit/findings-{ts}.json \
  --baseline .agents/config/context-audit-baseline.json \
  --output .agents/tmp/context-audit/report-{ts}.json
```

- Apply baseline suppression and generate the **summary-first report skeleton** deterministically
  (the top line `N findings: X AUTO_FIX / Y NEEDS_JUDGMENT / Z REPORT_ONLY; M suppressed`,
  grouped by rule → sorted by descending severity).
- **Respect the action emitted by static_checks.py and never recompute it.**
- A suppressed finding is shown as a count only (silent truncation is forbidden).

### Phase 4: Apply & Report

- **AUTO_FIX**: apply the differences computed by `apply_fixes.py` after **presenting them as a unified diff → a batch confirmation**
  ("apply N auto-fixes?").
  ```bash
  python3 {skill_dir}/scripts/apply_fixes.py \
    .agents/tmp/context-audit/findings-{ts}.json --write
  ```
- **NEEDS_JUDGMENT**: present in batches grouped by fix-type / rule ID ("apply 12 path typo fixes
  in bulk / confirm individually / skip"). Cap the interactive prompts at N per run, and send the rest to the report
  (resumable with `--interactive`).
- **REPORT_ONLY**: present as an actionable structured report containing what / why / how
  (for a contradiction, record both locations side by side).
- Conform to the `verification-gate.md` contract and report completion **accompanied by evidence of test execution**.

## Critical Rules

- **Never automate deletion or semantic rewriting of the body.** AUTO_FIX is limited to path fixes (only when the edit distance is ≤1 and
  the candidate is unique) and frontmatter formatting normalization (body bytes unchanged). When in doubt, fall to REPORT_ONLY / NEEDS_JUDGMENT.
- **Memory auditing covers only the project corresponding to cwd by default.** Global and cross-project coverage is an `--include-global` opt-in.
  Slug resolution matches the real Claude Code + reverse-verify, and is fail-safe skipped when ambiguous.
- **For secrets, never transcribe the value — only the pattern name + file:line.** Redaction is an invariant over every line-context.
- **The baseline is committed but stores only opaque finding IDs** (never carry detected values or body text).
  In a non-git project it is enough to keep it as a file. `--update-baseline` re-fixes it from the current findings even when a baseline already
  exists (idempotent).
- **CA-D002 is automatically skipped when `validate_repo.py` is detected** (a mechanical deconflict, not relying on a prose judgment).

## Tests

The pure functions are verified by the unittests in `scripts/test_*.py`:

```bash
for t in skills/context-audit/scripts/test_*.py; do python3 "$t"; done
```

- `test_collect_targets.py` / `test_static_checks.py` / `test_apply_fixes.py` /
  `test_aggregate_report.py` / `test_catalog_sync.py` (preventing catalog⇔registry drift) /
  `test_secret_detect.py` (the regression of the shared secret detection).
