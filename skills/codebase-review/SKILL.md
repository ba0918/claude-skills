---
name: codebase-review
description: コードベース全体を4つの専門エージェント（セキュリティ/機密情報、パフォーマンス/メモリ、実装品質/論理整合性、コード衛生/改善点）+ Codex セカンドオピニオンで並行レビューし、100点満点でスコアリングする。「コードベースレビュー」「全体レビュー」「codebase review」「コード品質チェック」「プロジェクト全体を分析」で起動。CLAUDE.mdがあればプロジェクト固有ルールも自動で考慮する。
---

# Codebase Review

Review the entire codebase with 4 specialized agents + Codex second opinion in parallel and generate an integrated score report.

**Context-saving design**: All agent analysis results are passed via files; only summaries flow into the main context.

**Headless execution**: Do not prompt the user for confirmation. All agents run autonomously. If a review agent fails, continue with the remaining agents (graceful degradation).

## Progress Checklist

```
codebase-review Progress:
- [ ] Determine target scope
- [ ] Analyze project structure & prepare work directory
- [ ] Preflight check (work directory write permission)
- [ ] Launch 4 review agents + Codex agent in parallel
- [ ] Wait for all agents & handle failures (Codex failure is non-blocking)
- [ ] Launch integration agent (with Codex perspective if available)
- [ ] Display summary & place report
```

## Workflow

### Step 1: Determine Target Scope

Determine target scope based on arguments:

| Argument | Target |
|----------|--------|
| None | Entire codebase (under src/) |
| `--diff` | Only files changed in `git diff HEAD` |
| Directory name | Specific directory |

Target files: `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.py`, `*.go`, `*.rs`, `*.java`, `*.php` and other source code.
Exclude: `node_modules/`, `dist/`, `build/`, `.git/`, `*.test.*`, `*.spec.*`, `*.d.ts`, lock files.

### Step 2: Analyze Project Structure & Prepare Work Directory

1. Read CLAUDE.md (project root + under `.claude/`) to understand project-specific rules
2. Understand directory structure (`ls` or `find`)
3. Check main config files (`package.json`, `deno.json`, `tsconfig.json`, `Cargo.toml`, etc.)
4. **Create work directory**:
   ```bash
   mkdir -p .claude/tmp/codebase-review-{YYYYMMDD-HHMM}/
   ```
5. **Preflight check** — Verify write permission to the work directory:
   ```bash
   touch .claude/tmp/codebase-review-{YYYYMMDD-HHMM}/.preflight && rm .claude/tmp/codebase-review-{YYYYMMDD-HHMM}/.preflight
   ```
   If this fails, abort immediately:
   ```
   ⛔ CODEBASE REVIEW ABORTED: Cannot write to work directory.
   Path: .claude/tmp/codebase-review-{YYYYMMDD-HHMM}/
   Ensure the directory exists and is writable.
   ```
6. **Write context.json** (create with Write tool):
   ```json
   {
     "project_name": "Project name",
     "scope": "Target scope description",
     "target_files": ["List of target file paths"],
     "file_count": file_count,
     "claude_md_rules": "CLAUDE.md contents (if present)",
     "work_dir": ".claude/tmp/codebase-review-{YYYYMMDD-HHMM}",
     "datetime": "YYYY-MM-DD HH:MM"
   }
   ```

### Step 3: Launch 5 Agents in Parallel

Issue exactly 5 Agent tool calls in a single message. Prompt templates for Agents 1-4 and Agent 5 are in [references/agent-prompts.md](references/agent-prompts.md).

```pseudocode
// All 5 calls in ONE message — do not split across multiple messages
Agent(
  name: "security-review",
  description: "Security & Secrets Review",
  subagent_type: "general-purpose",
  mode: "bypassPermissions",
  prompt: <Agent 1-4 template from references/agent-prompts.md>
          dimension = "Security + Secrets"
          criteria  = Section 1 of references/review-criteria.md
          output    = "{work_dir}/agent-1-security.json"
)
Agent(
  name: "performance-review",
  description: "Performance & Memory Review",
  subagent_type: "general-purpose",
  mode: "bypassPermissions",
  prompt: <Agent 1-4 template>
          dimension = "Performance + Memory Efficiency"
          criteria  = Section 2 of references/review-criteria.md
          output    = "{work_dir}/agent-2-performance.json"
)
Agent(
  name: "quality-review",
  description: "Implementation Quality Review",
  subagent_type: "general-purpose",
  mode: "bypassPermissions",
  prompt: <Agent 1-4 template>
          dimension = "Implementation Quality + Logical Consistency"
          criteria  = Section 3 of references/review-criteria.md
          output    = "{work_dir}/agent-3-quality.json"
)
Agent(
  name: "hygiene-review",
  description: "Code Hygiene Review",
  subagent_type: "general-purpose",
  mode: "bypassPermissions",
  prompt: <Agent 1-4 template>
          dimension = "Code Duplication + Other Improvements"
          criteria  = Section 4 of references/review-criteria.md
          output    = "{work_dir}/agent-4-hygiene.json"
)
Agent(
  name: "codex-review",
  description: "Codex Second Opinion Review",
  subagent_type: "codex:codex-rescue",
  mode: "bypassPermissions",
  prompt: <Agent 5 template from references/agent-prompts.md>
          output    = "{work_dir}/agent-5-codex.json"
)
```

Codex セキュリティ制約・フォールバックの共通パターン: [../shared/references/codex-integration.md](../shared/references/codex-integration.md)

### Step 3.5: Wait for Agents & Handle Failures

After all 5 agents complete, verify results:

1. Check that each expected JSON file exists:
   - `{work_dir}/agent-1-security.json`
   - `{work_dir}/agent-2-performance.json`
   - `{work_dir}/agent-3-quality.json`
   - `{work_dir}/agent-4-hygiene.json`
   - `{work_dir}/agent-5-codex.json` (optional — Codex agent)

2. **Graceful degradation for core agents (1-4)**: Count how many core agent result files exist.

   | Successful core agents | Action |
   |------------------------|--------|
   | 4/4 | Proceed to Step 4 normally |
   | 2-3/4 | Warn about missing agents, proceed with available results |
   | 0-1/4 | Abort with error message listing which agents failed |

   Warning format (2-3 core agents succeeded):
   ```
   ⚠️ {N}/4 review agents completed. Missing: {list of failed agent names}
   Proceeding with partial results...
   ```

   Abort format (0-1 core agents succeeded):
   ```
   ⛔ CODEBASE REVIEW ABORTED: Only {N}/4 review agents completed.
   Missing: {list of failed agent names}
   Check .claude/tmp/codebase-review-{YYYYMMDD-HHMM}/ for any partial results.
   ```

3. **Codex agent (Agent 5) is independent**: If `agent-5-codex.json` is missing, display a warning and proceed without Codex perspective:
   ```
   ⚠️ Codex second opinion unavailable — proceeding with existing review only.
   ```
   Codex failure does NOT affect the core agent success/failure count.

### Step 4: Launch Integration Agent

**After confirming at least 2 review agents have completed**, launch the integration agent via the Agent tool (`mode: bypassPermissions`).

Integration agent: `subagent_type: general-purpose`, `mode: bypassPermissions`

If some agents are missing, add to the integration agent prompt:
```
Note: The following agent results are missing: {list}. Generate the report using only the available agent results. Mark missing categories as "N/A — agent did not complete" in the report.
```

#### Integration Agent Prompt Template

```
You are the integration report analyst for the codebase review.
Integrate the analysis results from 4 review agents and generate the final report.

## Input Files
Work directory: {work_dir}

Read all of the following files:
- {work_dir}/context.json (project information)
- {work_dir}/agent-1-security.json
- {work_dir}/agent-2-performance.json
- {work_dir}/agent-3-quality.json
- {work_dir}/agent-4-hygiene.json
- {work_dir}/agent-5-codex.json (Codex second opinion — may not exist)

## Processing Steps

### 1. Collect Subcategory Scores
Get 8 individual subcategory scores from the subcategories array in each JSON.

### 2. Calculate Weighted Overall Score
Overall score = Σ(subcategory score × weight / 100)

Weights: security=20, secrets=15, performance=12, memory=8,
         quality=15, logic=15, duplication=8, improvements=7

### 3. Integrate and Sort All Issues
Aggregate issues from all agents and sort by severity (critical→major→minor→info).

### 4. Determine Overall Rank
90-100=S, 80-89=A, 70-79=B, 60-69=C, 50-59=D, 0-49=F

### 4.5. Integrate Codex Perspective (if available)
If agent-5-codex.json exists and was read successfully:
- Extract findings and architectural observations
- Merge any critical-severity Codex findings into the Critical Issues section
- Create a dedicated "Codex Perspective" section in the report
- Codex findings do NOT affect the 8-subcategory weighted scores

If agent-5-codex.json does not exist:
- Add a note: "⚠️ Codex second opinion was not available for this review"

### 5. Generate Output Files

**Output 1: {work_dir}/summary.txt**

Output in the following format exactly:

```
════════════════════════════════════════════════════════════════════════
  CODEBASE REVIEW REPORT
  Project: {project_name}
  Date: {datetime}
  Scope: {scope}
════════════════════════════════════════════════════════════════════════

  Overall Score: {total_score}/100  Rank: {rank}

  ┌─────────────────────────┬───────┬────────────┐
  │ Category                │ Score │ Status     │
  ├─────────────────────────┼───────┼────────────┤
  │ Security                │  XX   │ XXXXXXXXXX │
  │ Secrets                 │  XX   │ XXXXXXXXXX │
  │ Performance             │  XX   │ XXXXXXXXXX │
  │ Memory                  │  XX   │ XXXXXXXXXX │
  │ Quality                 │  XX   │ XXXXXXXXXX │
  │ Logic                   │  XX   │ XXXXXXXXXX │
  │ Duplication             │  XX   │ XXXXXXXXXX │
  │ Improvements            │  XX   │ XXXXXXXXXX │
  └─────────────────────────┴───────┴────────────┘

  Critical Issues: {N}
  Major Issues: {N}
  Minor Issues: {N}

  Top 5 Critical/Major Issues:
  1. [{severity}] {message} ({file}:{line})
  2. ...

  Codex Perspective:
  {If available: top 3 Codex findings summary}
  {If unavailable: "⚠️ Codex second opinion was not available"}

  Full report: docs/reviews/review-{YYYYMMDD-HHMM}.md
════════════════════════════════════════════════════════════════════════
```

Status: 90+→EXCELLENT, 70+→GOOD, 50+→NEEDS WORK, <50→CRITICAL

**Output 2: {work_dir}/report.md**

Generate a detailed report following the report template structure (references/report-template.md).
Contents:
- Executive summary (overall score, rank, overview)
- Critical/Major Issues list
- Category details (8 subcategories × score, issues, good points)
- Improvement roadmap (priority order, estimated effort)
- Appendix (score formula, target file list)

## Output Constraint (most important)
Write all analysis results to the 2 files above (summary.txt, report.md).
Your final response must be only the following single line:

DONE: integration

Do not include any other text in your final response.
```

### Step 5: Display Summary & Place Report

After confirming the integration agent has completed:

1. **Read** `{work_dir}/summary.txt` with the Read tool and display it to the console as-is
2. **Copy** with Bash tool: `cp {work_dir}/report.md docs/reviews/review-{YYYYMMDD-HHMM}.md`
3. Display completion message (including report file path)

**Note**: Do not read files other than summary.txt (agent-*.json, report.md) into the main context.

## Error Handling

### Preflight failures (Step 2)
- **Work directory write failure**: Abort immediately with error message. Do not launch any agents.

### Agent failures (Step 3)
- **2+ agents succeed**: Warn and proceed with partial results (graceful degradation)
- **0-1 agents succeed**: Abort with error message
- **Agent timeout**: If an agent does not complete within a reasonable time, treat it as failed

### Integration agent failure (Step 4)
- **Integration agent fails**: Read available agent JSON files directly and generate a minimal summary in the main context (fallback to inline reporting)

## Important Rules

- **Headless execution**: Do not prompt the user for confirmation at any step.
- **All agents must use `mode: bypassPermissions`**: This is critical. Without it, agents will be blocked by permission prompts when reading source files and writing result JSON, causing cascading tool errors.
- **Parallel execution via single message**: Issue all Agent tool calls in a single message to run them in parallel. Do NOT use `run_in_background` (that is a Bash tool parameter, not an Agent tool parameter).
- **Codex agent uses Bash only**: The Codex agent (`subagent_type: "codex:codex-rescue"`) can only use the Bash tool. All file reads/writes must use shell commands (`cat`, `tee`, etc.), not Read/Write/Edit tools.
- **Graceful degradation**: Partial results are better than no results. If some agents fail, generate a report from the successful agents.
- **Do not read agent-*.json or report.md into the main context** (except summary.txt). This preserves context window space.

## Reference

- Review criteria details: [references/review-criteria.md](references/review-criteria.md)
- Report template: [references/report-template.md](references/report-template.md)
