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

**CRITICAL: You MUST launch exactly 5 agents in a single message. Not 4, but 5.** Issue all 5 Agent tool calls in one message to run them in parallel.

All agents use `mode: bypassPermissions` (essential — without it, agents are blocked by permission prompts).

**Launch the following 5 agents simultaneously:**

1. **Agent 1: security-auditor** — `subagent_type: general-purpose` — Security + Secrets (35%)
2. **Agent 2: performance-analyzer** — `subagent_type: general-purpose` — Performance + Memory (20%)
3. **Agent 3: quality-inspector** — `subagent_type: general-purpose` — Quality + Logic (30%)
4. **Agent 4: codebase-hygiene** — `subagent_type: general-purpose` — Duplication + Improvements (15%)
5. **Agent 5: codex-perspective** — `subagent_type: "codex:codex-rescue"` — Codex second opinion (independent section)

Agent 5 (Codex) is NOT optional. Always launch it alongside Agents 1-4. If Codex fails, Step 3.5 handles graceful degradation.

Context to provide Agents 1-4:
- File path of context.json
- Detailed review criteria ([references/review-criteria.md](references/review-criteria.md) relevant section)
- Output JSON file path

Context to provide Agent 5 (Codex):
- File path of context.json (Codex reads it with `cat`)
- Output JSON file path (Codex writes it with `cat > file << 'EOF'`)
- **Codex can only use the Bash tool** — no Read/Write/Edit/Glob

#### Review Agent Prompt Template

```
You are a specialist reviewer for "{dimension name}".
Thoroughly analyze the following codebase.

## Load Context
First, read {work_dir}/context.json to obtain project information and target file list.

## Project-Specific Rules
Refer to claude_md_rules in context.json and follow project-specific rules during review.

## Review Criteria
{Content of the relevant section from references/review-criteria.md}

## Analysis Steps
1. Get target_files from context.json
2. Read each file and analyze based on the checklist above
3. Record individual scores and issues for each subcategory

## Result Output (strict)
Write the analysis results in the following JSON format to **{work_dir}/agent-{N}-{category}.json** using the Write tool:

```json
{
  "agent": "{agent name}",
  "subcategories": [
    {
      "name": "{subcategory name}",
      "key": "{subcategory key}",
      "weight": weight(number),
      "score": 0-100,
      "issues": [
        {
          "severity": "critical|major|minor|info",
          "message": "Detailed description of the issue",
          "file": "file path",
          "line": line_number (0 if unknown),
          "suggestion": "Specific fix suggestion",
          "effort": "low|medium|high"
        }
      ],
      "good_practices": ["Good point 1", "Good point 2"]
    }
  ],
  "summary": "Overall assessment (2-3 sentences)"
}
```

Score criteria:
- 90-100: Excellent. No critical issues
- 70-89: Good. Minor improvements possible
- 50-69: Needs improvement. Issues to address
- 30-49: Many issues. Prompt action recommended
- 0-29: Critical. Immediate action required

## Output Constraint (most important)
Write all your analysis results to the JSON file above.
Your final response (the part returned as the Task result) must be only the following single line:

DONE: {category}

Do not include any other text in your final response. All lengthy analysis and explanations should already be written to the JSON file.
```

#### Codex Agent (Agent 5) Prompt Template

**Important**: Codex (`subagent_type: "codex:codex-rescue"`) can only use the Bash tool. It cannot use Write, Read, Edit, or Glob. All file operations must use shell commands (`cat`, `tee`, `jq`, etc.).

```
You are a Codex-powered second opinion reviewer for the codebase.
Analyze the codebase from a holistic perspective that complements the 4 specialist agents.

## Load Context
First, read {work_dir}/context.json using `cat`:
```bash
cat {work_dir}/context.json
```

## Security Constraint
Skip the following files from target_files (do NOT read them):
- Files matching .gitignore patterns
- .env, credentials.*, *.key, *.pem, and other secret files

## Review Focus
Focus on cross-cutting concerns that individual specialist agents may miss:
1. Overall design patterns and architectural coherence
2. Cross-module dependency issues
3. Consistency of error handling strategies across the codebase
4. Convention violations that span multiple files
5. Alternative architectural approaches

## Analysis Steps
1. Read context.json with `cat` to get target_files (excluding secrets/sensitive files)
2. Read a representative sample of files using `cat` to understand overall patterns
3. Identify cross-cutting concerns and holistic issues

## Result Output (strict)
Write the analysis results in the following JSON format to **{work_dir}/agent-5-codex.json** using `tee` or `cat` with heredoc:

```bash
cat > {work_dir}/agent-5-codex.json << 'CODEX_EOF'
{
  "agent": "codex-perspective",
  "findings": [
    {
      "severity": "critical|major|minor|info",
      "message": "Detailed description of the cross-cutting concern",
      "files": ["affected file paths"],
      "suggestion": "Specific improvement suggestion"
    }
  ],
  "architectural_observations": "Overall architectural assessment (2-3 sentences)",
  "summary": "Overall assessment (2-3 sentences)"
}
CODEX_EOF
```

## Output Constraint (most important)
Write all your analysis results to the JSON file above using Bash commands.
Your final response (the part returned as the Task result) must be only the following single line:

DONE: codex-perspective

Do not include any other text in your final response.
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
