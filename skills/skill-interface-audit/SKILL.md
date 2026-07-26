---
name: skill-interface-audit
description: 各 SKILL.md を API 仕様として静的に監査し、契約の欠落・構造違反を検出するスキル。skill-authoring.md の執筆原則を正本とし、SI-* ルール体系で機械検証する。純関数 static + LLM 意味判断の混成モデル。パッチ候補を含む finding を出力し、動的検証は既存メタスキルへ橋渡しする。「skill-interface-audit」「インターフェース監査」「スキル契約チェック」「SKILL.md 監査」「API仕様チェック」で起動。
---

# skill-interface-audit

Taking the authoring principles of [skill-authoring.md](../shared/references/skill-authoring.md) as the source of truth, statically audit each SKILL.md as an "API specification".
Where the existing meta-skills own dynamic measurement and the quality of resident instructions, this skill owns **the contractual completeness of skills/\*/SKILL.md** ([positioning in detail](references/positioning.md)).

## Positioning and architecture

Among the meta-skills it owns the "contract layer", and it is cut exclusively against context-audit by the set of target files. It is a hybrid model of pure-function static checks plus LLM semantic judgment. For details see [references/positioning.md](references/positioning.md).

Reference material (progressive disclosure):

- Positioning and architecture: [references/positioning.md](references/positioning.md)
- Rule definitions: [references/rule-catalog.md](references/rule-catalog.md)
- The definition of the three fix-action values: [../shared/references/fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md)
- The definition of severity: [../shared/references/severity-and-verdicts.md](../shared/references/severity-and-verdicts.md)
- The source of truth for the authoring principles: [../shared/references/skill-authoring.md](../shared/references/skill-authoring.md)
- Completion verification: [../shared/references/verification-gate.md](../shared/references/verification-gate.md)

## Arguments

- No argument: audit every skill under skills/.
- One or more skill names: audit only the named skills. For example: `skill-interface-audit refactor commit`
- `--update-baseline`: fix the current findings as the baseline (thereafter only new findings are presented).
- `--bridge`: generate the bridging output toward dynamic verification (scenario candidates for empirical-prompt-tuning plus fixture candidates for skill-regression).

No command is created (the skills-first policy; being single-workflow, it needs no named entry point either).

## Execution contract

- **Resolving script paths**: `{skill_dir}` is the directory this skill is installed in (an absolute path). `{project_root}` is the user's project root (the cwd).
- **Non-interactive fallback**: when running headless or as a subagent, fall to the safe side and change no state. Do not write the baseline; emit the full report.
- `{ts}` is minted with `date +%Y%m%d-%H%M%S` and the same value is reused across the phases.
- **Output location**: `.claude/tmp/skill-interface-audit/` (git-ignored).

## Workflow

### Phase 0: Discovery

1. Collect `skills/*/SKILL.md` and build the target list. Narrow it if skill names were given as arguments
2. Also collect the files under each skill's `references/` as secondary targets
3. Check whether the baseline file (`.claude/skill-interface-audit-baseline.json`) exists
4. How the baseline is handled:
   - **Auditing every skill with no baseline present**: present the first-run flow — (a) fix the current state as the baseline and present only new findings thereafter, or (b) the full report only (the baseline is not written)
   - **A single skill specified**: do not present the baseline first-run flow. Emit the full report. Write the baseline only when `--update-baseline` is explicit

### Phase 1: Static checks (pure functions)

Run the SI-S\* rules in one batch and emit a findings JSON.

Target rules: SI-S001 through SI-S004 (details in [rule-catalog.md](references/rule-catalog.md)).
All of them correspond to machine-verifiable principles of skill-authoring.md and can be decided deterministically.

The finding schema is shared with context-audit:
`id / severity / action / where(skill:file:line) / what / why / how / fix_draft(null | suggested text)`

### Phase 2: Contract assessment (LLM, REPORT\_ONLY)

The LLM evaluates the SI-C\* rules. Keep this clearly separate from Phase 1.

1. Read each skill's SKILL.md and evaluate the contract elements SI-C001 through SI-C006
2. **"Not applicable" is a legitimate state**: a read-only skill (investigate) needs no side-effect declaration, and a single-workflow skill needs no delegation conditions. If you can judge that "given this skill's nature, this contract element is unnecessary", it is a PASS
3. The criterion is not "does the section exist" but "**could an LLM misunderstand this point and cause an accident**"
4. Every finding is REPORT\_ONLY. Include a patch candidate (a draft of the concrete text to add) in `fix_draft`
5. A patch candidate is capped at NEEDS\_JUDGMENT and is **never applied automatically** ([fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md): semantic rewriting of a body must not be AUTO\_FIX)

### Phase 3: Aggregate and bridge

1. Merge the findings of Phase 1 and Phase 2
2. Apply the baseline suppression and present only the new findings (state the suppressed count explicitly; silent truncation is forbidden)
3. Generate a summary-first report:
   ```
   N findings: X NEEDS_JUDGMENT / Y REPORT_ONLY; M suppressed
   ── Phase 1 (structural) ──
   [findings grouped by rule, severity descending]
   ── Phase 2 (contract) ──
   [findings grouped by rule, severity descending]
   ```
4. When `--bridge` is given, generate the bridging output toward dynamic verification:
   - The ambiguous spots of an SI-C\* finding → scenario candidates for empirical-prompt-tuning (mapped onto the friction-taxonomy categories)
   - The diff after applying a patch candidate → fixture candidates for skill-regression
5. Conform to the [verification-gate.md](../shared/references/verification-gate.md) contract and report completion with evidence

### The friction-taxonomy mapping (for the bridge output)

Map SI-C\* findings onto empirical-prompt-tuning's fixed taxonomy to prevent the vocabulary from being duplicated:

| SI-C rule | friction category | Basis |
|---|---|---|
| SI-C001 side effects | rationalization\_hook | Undeclared side effects get rationalized away |
| SI-C002 completion conditions | ambiguous\_term / missing\_premise | An ambiguous completion condition produces multiple readings |
| SI-C003 failure handling | missing\_premise | Implicit premises about failure scenarios |
| SI-C004 input | missing\_premise / ambiguous\_term | Implicit premises about the arguments |
| SI-C005 output | ambiguous\_term | An ambiguous definition of the deliverable |
| SI-C006 delegation | self\_containment\_gap | Implicit dependence on another skill |

## Important rules

- **Never change a SKILL.md**: every output of this skill is REPORT\_ONLY or NEEDS\_JUDGMENT. A patch candidate is a proposal, and the user decides whether to apply it
- **Do not turn it into template enforcement**: do not make it a pressure to "add N sections to every skill". The criterion is "could an LLM misunderstand this point", not uniformity of form
- **Do not overlap with validate\_repo.py**: frontmatter, descriptions, link existence, and the shared-contract vocabulary belong to CI. This skill owns the rest
- **Ground the basis of a severity in experience**: "directly causes accidents" at a given tier is an empirical claim. Anything that cannot be tied to skill-improve's friction data or to an empirical measurement stays at INFO
- **Do not invent new criteria**: the SI-\* rules audit the principles of skill-authoring.md and never create quality criteria of their own ([skill-authoring.md](../shared/references/skill-authoring.md) #5)

## Preventing rationalization

| Excuse | Reality |
|--------|------|
| "This skill is simple, so it needs no side-effect declaration" | The simpler the skill, the more freely an LLM extends it |
| "The completion condition is obvious from context" | Obvious and guessed cannot be told apart. State it, or judge it N/A |
| "Findings come out for every skill, so it is meaningless" | Suppress them with the baseline and look only at the new findings |
| "Just apply the patch candidates as they are" | A patch is NEEDS\_JUDGMENT. Check the context before deciding |

## Side effects

- Generates a report and a findings JSON under `.claude/tmp/skill-interface-audit/`
- Writes `.claude/skill-interface-audit-baseline.json` only when `--update-baseline` is given
- **Never changes** skills/\*/SKILL.md

## Completion conditions

- Phase 1 and Phase 2 are complete for every target skill
- The summary-first report has been generated
- When a baseline update was requested, the baseline file has been written
- The evidence requirements of [verification-gate.md](../shared/references/verification-gate.md) are satisfied

## Handling failures

- The Phase 1 script fails to run: report the error and proceed to Phase 2 (do not discard the partial results)
- The Phase 2 LLM evaluation fails for a particular skill: skip that skill and continue with the rest
- Every phase fails: emit an error report containing whatever information could be collected

## Prerequisites

- Python 3 must be available
- A `skills/` directory must exist (this repository, or a skill-collection repository conforming to skill-authoring.md)

## Delegation conditions

| Situation | Delegate to |
|------|--------|
| You want to measure the triggering accuracy of the descriptions | trigger-eval |
| You want to evaluate the execution quality of a skill body | empirical-prompt-tuning |
| You want to verify regressions after changing a skill | skill-regression |
| You want to detect friction in real operation | skill-improve |
| You want to audit CLAUDE.md / AGENTS.md / rules | context-audit |
| Code⇔documentation consistency inside a skill | doc-check |
