---
name: skill-improve
description: A meta skill that detects and analyzes friction in skill usage from session data and drives skill improvements from that data. Use when the user says "skill-improve", "improve the skills", or "analyze the friction".
---

# Skill Improve

A meta-skill that collects and analyzes friction signals from session data and carries out self-improvement of the skills.

**Headless execution**: launch every agent in Phase 2 in automatic-execution mode. Do not raise confirmation prompts to the user.

## Flow Overview

```
skill-improve command
  │
  ├─ Phase 1: Data collection (collect.py → context.json)
  │
  ├─ Phase 2: Friction analysis (4 agents in parallel)
  │    ├─ friction-detector / pattern-analyzer
  │    ├─ expectation-auditor / drift-detector
  │    └─ → friction-report.md
  │
  ├─ Phase 3: Improvement hypotheses (the investigate pattern)
  │    └─ → hypotheses A/B/C + autonomy verdict
  │
  └─ Phase 4: Improvement implementation (improve mode only)
       ├─ Small → iterate
       └─ Large → create a plan → delegate to cycle
```

## Parameters

- The first argument of `$ARGUMENTS`: workflow selection
  - `analyze` (default): run Phases 1-3 and generate friction-report.md
  - `report`: run Phase 1 only and emit the collected data as JSON
  - `improve`: run Phases 1-4 and carry the improvement through automatically (a dry-run is mandatory)
- `--days N`: the analysis period (default: 30 days)
- `--project NAME`: the project filter (default: inferred from the cwd)
- `--all-projects`: scan across every project. Use it for analyzing user-scoped skills or for grasping usage trends across all skills
- `--capture-prompts`: opt-in. Emits masked user prompt bodies as JSONL (for collecting real examples of missed triggering; the `trigger-eval` skill is the second consumer). Because it writes out bodies, `--output` is mechanically restricted to a path under `cwd/.claude/tmp` that is also `git check-ignore`d (fail-closed). It uses a different path from the default body-free output and does not affect existing behavior. Secret values are fully masked as `[REDACTED:kind]` (detecting AWS / PEM / JWT / email / home paths / known-prefix tokens such as ghp_, github_pat_, xoxb-, sk-, sk-ant-, and AIza, whether or not they are quoted)

## Phase 1: Data collection

### Step 1.1: Run collect.py

When `--all-projects` is given:

```bash
python3 skills/skill-improve/scripts/collect.py \
  --days {days} \
  --all-projects \
  --output .claude/tmp/skill-improve-{datetime}/context.json
```

In the default case (a project is specified):

```bash
python3 skills/skill-improve/scripts/collect.py \
  --days {days} \
  --project {project} \
  --output .claude/tmp/skill-improve-{datetime}/context.json
```

### Step 1.2: Check the result

Read context.json and display the summary:

```
── Phase 1: Data Collection ──
Project: {project_filter} (all-projects: {true/false})
Projects scanned: {projects_scanned_count}
Period: {days} days
Sessions: {sessions_found}
Skill invocations: {total_skill_invocations}
Unique skills: {unique_skills_used}
Secret warnings: {count}
```

In `report` mode, stop here. Display the JSON contents and finish.

When there are zero skill invocations:

```
⚠️ No skill invocations found in the last {days} days.
Try increasing the period with --days or checking the project filter.
```

Do not proceed to Phase 2; finish.

## Phase 2: Friction analysis (4 agents in parallel)

### Step 2.1: Spawn the agents

Launch the four analysis agents **in parallel** as subagents (a lightweight model, automatic-execution mode).
For each agent's prompt, see [references/analysis-roles.md](references/analysis-roles.md).

**Important**: automatic-execution mode is mandatory. Without it, the background agents are blocked by a permission prompt when writing to `.claude/tmp/`, and every agent fails to write.

The context handed to each agent:
1. The contents of context.json
2. The SKILL.md of the target skill (identified by listing the files)
3. The role-specific analysis instructions
4. **The pressure-test viewpoint**: include "could this skill's constraints be rationalized away under pressure?" as an analysis item
   - Pressure types: time pressure / sunk cost / authority / economics / fatigue / social / pragmatic
   - For each constraint, evaluate "the likelihood that the user or the LLM rationalizes bypassing this constraint under {pressure type}"
   - Recommend strengthening the guardrails for high-risk constraints

Each agent writes its analysis result as JSON to `.claude/tmp/skill-improve-{datetime}/{role}.json`.

### Step 2.2: Integrate the results

Launch an integrating subagent (a lightweight model, automatic-execution mode), and have it integrate the four analysis results to
generate `.claude/tmp/skill-improve-{datetime}/friction-report.md`.

The integrating agent's prompt:
```
Read the 4 JSON files under .claude/tmp/skill-improve-{datetime}/ and
write out the friction report as friction-report.md.

Format:
# Friction Report: {project}

## Executive Summary
{a 1-3 line summary}

## Skill Rankings (by friction score)
| Skill | Score | Top Issue | Recommendation |

## Detailed Findings
### {skill_name}
- Friction Score: {score}
- Issues: ...
- Recommendations: ...

## Improvement Hypotheses
### Hypothesis A: {title}
- Target: {skill}
- Change: {description}
- Expected Impact: {impact}
- Size: Small / Large
```

Display:

```
── Phase 2: Friction Analysis ──
Agents: 4/4
Skills analyzed: {N}
Top friction skill: {name} (score: {score})
Report: .claude/tmp/skill-improve-{datetime}/friction-report.md
```

## Phase 3: Improvement hypotheses and the autonomy verdict

### Step 3.1: Read friction-report.md

### Step 3.2: Autonomy verdict

Following the criteria of [references/scoring-guide.md](references/scoring-guide.md), judge the size of the improvement:

| Friction score | Verdict | Action |
|-----------|------|-----------|
| 0-2 | Report only | Display friction-report.md and finish |
| 3-5 | Small | Fix SKILL.md directly with iterate |
| 6+ | Large | Create a plan → delegate to cycle |

### Step 3.3: Categorize the improvement hypotheses

Classify the improvement hypotheses into the following categories:

| Category | Description | Examples |
|---------|------|-----|
| UX improvement | Reduce friction in the user experience | Better error messages, a simplified flow |
| Logic fix | Fix bugs and logical inconsistencies | A wrong branch condition, an unhandled edge case |
| **Guardrail hardening** | Prevent constraints from being bypassed under pressure | Adding a rationalization-prevention table, strengthening an Iron Law, introducing a Gate Function |
| Performance | Improve execution efficiency | Cutting unnecessary subagent invocations |
| Documentation | Improve explanations and references | Clarifying an unclear instruction |

In `analyze` mode, stop here. Display the contents of friction-report.md and the improvement hypotheses.

Display:

```
── Phase 3: Improvement Hypotheses ──
Hypotheses: {N} (UX: {n}, Logic: {n}, Guardrail: {n}, Perf: {n}, Docs: {n})
Recommended action: {Report only / iterate / cycle}
Top hypothesis: {title} (target: {skill}, size: {size})
```

## Phase 4: Improvement implementation (improve mode only)

**Important: always run the dry-run, at every level.**

### Step 4.1: Display the dry-run

Display the skill files to be improved and an outline of the changes:

```
══════════════════════════════════════
SKILL-IMPROVE DRY-RUN
Target skill: {skill_name}
Files to modify: {file_list}
Change summary: {summary}

Proceeding with implementation...
══════════════════════════════════════
```

### Step 4.2: Delegate the implementation

| Size | Delegate to | How |
|--------|--------|------|
| Small | iterate | Run the `claude-skills:iterate` skill. Pass the friction report's improvement hypothesis as the argument |
| Large | cycle | Create a plan from the improvement hypothesis and delegate to `claude-skills:cycle` |

### Step 4.3: Display completion

```
══════════════════════════════════════
SKILL-IMPROVE COMPLETE
Mode: {improve}
Skills analyzed: {N}
Improvements applied: {N}
Report: {friction_report_path}
══════════════════════════════════════
```

## Cleaning up temporary files

On phase completion (whether it ends normally or with an error), delete `.claude/tmp/skill-improve-{datetime}/`.
Keep `friction-report.md`, however (so the user can refer to it later).

## Error handling

### Errors in Phase 1

- **Python not installed**: display an error message and abort
- **collect.py failed**: display stderr and abort
- **No session data**: display a warning and abort

### Errors in Phase 2

- **Agent spawn failed (two or more succeeded)**: continue with the results of the agents that succeeded only
- **Agent spawn failed (one or fewer)**: abort

### Errors in Phase 4

- **iterate/cycle failed**: display the error. friction-report.md is kept

## References

- Friction analysis agent roles: [references/analysis-roles.md](references/analysis-roles.md)
- Friction schema definition: [references/friction-schema.md](references/friction-schema.md)
- Scoring criteria: [references/scoring-guide.md](references/scoring-guide.md)
