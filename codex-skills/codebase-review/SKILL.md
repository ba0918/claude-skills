---
name: codebase-review
description: コードベース全体を4つの専門エージェント（セキュリティ/機密情報、パフォーマンス/メモリ、実装品質/論理整合性、コード衛生/改善点）で並行レビューし、100点満点でスコアリングする。「コードベースレビュー」「全体レビュー」「codebase review」「コード品質チェック」「プロジェクト全体を分析」で起動。AGENTS.mdがあればプロジェクト固有ルールも自動で考慮する。
---

# Codebase Review (Codex Edition)

## Codex CLI ツールの使い分け

- レビューエージェント起動: `spawn_agent` / `wait_agent`（4体並行）
- ファイル読み取り・結果 JSON 受け渡し: `shell`（`cat` / `rg`、`.codex/tmp/`）
- レポート出力: `shell` heredoc

Review the entire codebase with 4 specialized agents in parallel and generate an integrated score report.

**Context-saving design**: All agent analysis results are passed via files; only summaries flow into the main context.

**Headless execution**: Do not prompt the user for confirmation. All agents run autonomously. If a review agent fails, continue with the remaining agents (graceful degradation).

## Progress Checklist

```
codebase-review Progress:
- [ ] Determine target scope
- [ ] Analyze project structure & prepare work directory
- [ ] Preflight check (work directory write permission)
- [ ] Launch 4 review agents in parallel
- [ ] Wait for all agents & handle failures
- [ ] Launch integration agent
- [ ] Display summary & place report
```

## Workflow

### Step 1: Determine Target Scope

Determine target scope based on arguments:

| Argument | `scope` string | target_files source |
|----------|----------------|---------------------|
| None | `"entire codebase under src/"` | `git ls-files src/` (or `find src/ -type f` if not a git repo) |
| `--diff` | `"diff (git diff HEAD)"` | `git diff HEAD --name-only --diff-filter=AM` (Added/Modified only; Deleted is skipped since the file no longer exists) |
| Directory name `<dir>` | `"directory: <dir>"` | `git ls-files <dir>/` (fallback: `find <dir> -type f`) |

After collecting the raw list, apply both filters in order. Patterns are interpreted as **glob patterns (`fnmatch` semantics)**: `*` matches any characters except `/` within a path component, and path-prefix patterns like `dist/` match any file under that directory.

1. **Extension allowlist**: `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.py`, `*.go`, `*.rs`, `*.java`, `*.php`
2. **Path/suffix blocklist**: `node_modules/`, `dist/`, `build/`, `.git/`, `*.test.*`, `*.spec.*`, `*.d.ts`, lock files (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `Cargo.lock`, `go.sum`, etc.)

Config files like `package.json` / `Cargo.toml` / `tsconfig.json` are **not** in the allowlist and are therefore excluded as review targets. They may still be read in Step 2 for project structure context.

**Empty target abort (evaluate BEFORE Step 2 — do not create the work directory if the list is empty)**: If the filtered target_files list is empty (e.g., clean working tree on `--diff`, or project with no matching source files), do NOT create the work directory and do NOT launch any agents. Print and exit cleanly:

```
⚠️ CODEBASE REVIEW SKIPPED: No reviewable source files found.
   Scope: {scope}
   If you expected files, re-check the argument or verify the allowlist/blocklist.
```

### Step 2: Analyze Project Structure & Prepare Work Directory

1. Read AGENTS.md (project root) to understand project-specific rules
2. Understand directory structure (`shell` commands: `ls`, `find`)
3. Check main config files (`package.json`, `deno.json`, `tsconfig.json`, `Cargo.toml`, etc.)
4. **Create work directory**:
   ```bash
   mkdir -p .codex/tmp/codebase-review-{YYYYMMDD-HHMM}/
   ```
5. **Preflight check** — Verify write permission to the work directory:
   ```bash
   touch .codex/tmp/codebase-review-{YYYYMMDD-HHMM}/.preflight && rm .codex/tmp/codebase-review-{YYYYMMDD-HHMM}/.preflight
   ```
   If this fails, abort immediately:
   ```
   ⛔ CODEBASE REVIEW ABORTED: Cannot write to work directory.
   Path: .codex/tmp/codebase-review-{YYYYMMDD-HHMM}/
   Ensure the directory exists and is writable.
   ```
6. **Write context.json** (create via `shell`):
   ```bash
   cat > {work_dir}/context.json << 'EOF'
   {
     "project_name": "Project name",
     "scope": "Step 1 scope string (e.g., \"entire codebase under src/\" / \"diff (git diff HEAD)\" / \"directory: crates/core\")",
     "target_files": ["List of filtered target file paths from Step 1"],
     "file_count": "len(target_files) — the review-target count after filtering, NOT total repo size",
     "agents_md_rules": "AGENTS.md contents (empty string \"\" if absent)",
     "work_dir": ".codex/tmp/codebase-review-{YYYYMMDD-HHMM}",
     "datetime": "YYYY-MM-DD HH:MM"
   }
   EOF
   ```

### Step 3: Launch 4 Agents in Parallel

Issue exactly 4 `spawn_agent` calls in a single turn. Prompt templates are in [references/agent-prompts.md](references/agent-prompts.md).

**Placeholder expansion**: When building each agent's prompt, replace every placeholder (`{variable}`, `<Agent template>`, "Content of the relevant section from references/review-criteria.md", `{work_dir}`, etc.) with the **actual content** inlined — do not forward unresolved placeholders to the sub-agent. The sub-agent does not have SKILL.md context and cannot resolve them.

```
spawn_agent: "security-review"
  → dimension: "Security + Secrets"
  → criteria: Section 1 of references/review-criteria.md
  → output: "{work_dir}/agent-1-security.json"

spawn_agent: "performance-review"
  → dimension: "Performance + Memory Efficiency"
  → criteria: Section 2 of references/review-criteria.md
  → output: "{work_dir}/agent-2-performance.json"

spawn_agent: "quality-review"
  → dimension: "Implementation Quality + Logical Consistency"
  → criteria: Section 3 of references/review-criteria.md
  → output: "{work_dir}/agent-3-quality.json"

spawn_agent: "hygiene-review"
  → dimension: "Code Duplication + Other Improvements"
  → criteria: Section 4 of references/review-criteria.md
  → output: "{work_dir}/agent-4-hygiene.json"
```

### Step 3.5: Wait for Agents & Handle Failures

After all 4 agents complete (`wait_agent`), verify results:

1. Check that each expected JSON file exists:
   - `{work_dir}/agent-1-security.json`
   - `{work_dir}/agent-2-performance.json`
   - `{work_dir}/agent-3-quality.json`
   - `{work_dir}/agent-4-hygiene.json`

2. **Graceful degradation**: Count how many agent result files exist.

   | Successful agents | Action |
   |-------------------|--------|
   | 4/4 | Proceed to Step 4 normally |
   | 2-3/4 | Warn about missing agents, proceed with available results |
   | 0-1/4 | Abort with error message listing which agents failed |

   Warning format (2-3 agents succeeded):
   ```
   ⚠️ {N}/4 review agents completed. Missing: {list of failed agent names}
   Proceeding with partial results...
   ```

   Abort format (0-1 agents succeeded):
   ```
   ⛔ CODEBASE REVIEW ABORTED: Only {N}/4 review agents completed.
   Missing: {list of failed agent names}
   Check .codex/tmp/codebase-review-{YYYYMMDD-HHMM}/ for any partial results.
   ```

3. **Partial score normalization (only when 2-3/4 agents succeeded)**: When one or more subcategories are missing, the integration agent must compute:

   ```
   partial_overall = Σ(available subcategory score × weight) / Σ(available weights)
   ```

   **Relation to the full-review formula (§Step 4 #2)**: The canonical formula `Overall = Σ(score × weight / 100)` assumes the 8 weights sum to 100, so dividing by 100 normalizes to 0-100. When some subcategories are absent, `Σ(available weights)` replaces the fixed 100 in the denominator. The two formulas are mathematically equivalent when all 8 subcategories are present; the partial form is a pure generalization.
   - Weights are the percentage values defined in §Step 4 (security=20, secrets=15, ...). Because scores are 0-100 and `Σ(available weights)` is on the same scale, the division directly yields a 0-100 normalized value — **do not multiply by 100 again** (that would overflow).
   - Example: available={security(20)=78, secrets(15)=85, quality(15)=72, logic(15)=80} → (78·20 + 85·15 + 72·15 + 80·15) / (20+15+15+15) = 5115 / 65 ≈ 79.
   - Round to the nearest integer.
   - Missing rows in the scoreboard show `"N/A"` (score) and `"N/A — agent did not complete"` (status).
   - Label the overall score as `"Partial Score (N/8 subcategories)"` so users cannot mistake it for a full review.
   - Do NOT substitute 0 for missing subcategories — that penalizes areas that weren't measured and misrepresents the review.
   - Rank thresholds (90-100=S, 80-89=A, ..., 0-49=F) apply to `partial_overall` as well; append `(partial)` after the rank letter to signal data incompleteness (e.g., `B (partial)`).

### Step 4: Launch Integration Agent

**After confirming at least 2 review agents have completed**, launch the integration agent via `spawn_agent`.

**Only when ≥1 agent failed** (i.e., 2-3/4 succeeded; skip this line entirely when 4/4 succeed), add to the integration agent prompt:
```
Note: The following agent results are missing: {list}. Generate the report using only the available agent results. Mark missing categories as "N/A — agent did not complete" in the report. Apply the partial score normalization rule from §Step 3.5: partial_overall = Σ(available score × weight) / Σ(available weights), rounded to the nearest integer (do NOT multiply by 100 — scores are already 0-100 and the denominator is in the same scale). Label the result as "Partial Score (N/8 subcategories)" and append "(partial)" to the rank letter.
```

`{list}` uses filename form — comma-separated JSON filenames (e.g., `agent-2-performance.json, agent-4-hygiene.json`), **not** agent display names or category names.

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

  Critical Issues: {N}     # N = sum across available agents only; missing agents contribute 0
  Major Issues: {N}
  Minor Issues: {N}

  Top 5 Critical/Major Issues:
  1. [{severity}] {message} ({file}:{line})
  2. ...

  Full report: docs/reviews/review-{YYYYMMDD-HHMM}.md
════════════════════════════════════════════════════════════════════════
```

Status: 90+→EXCELLENT, 70+→GOOD, 50+→NEEDS WORK, <50→CRITICAL, N/A→"N/A — agent did not complete".

**Column width**: The Status column is not fixed-width — expand it as needed so `"N/A — agent did not complete"` fits on a single line. Keep the box-drawing characters consistent.

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

1. **Read** `{work_dir}/summary.txt` with `shell` (cat) and display it to the console as-is
2. **Copy** report (ensure target directory exists first):
   ```bash
   mkdir -p docs/reviews && cp {work_dir}/report.md docs/reviews/review-{YYYYMMDD-HHMM}.md
   ```
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
- **Integration agent fails** (no `summary.txt` was produced): Read available agent JSON files directly and generate a minimal summary in the main context (inline fallback).
  - **Skip the Step 5 `cp` step** — there is no `report.md` to place.
  - Tell the user explicitly: `⚠️ Integration agent failed. No docs/reviews/review-*.md was generated. Raw JSON is in {work_dir}/ for manual inspection.`
  - **Inline fallback summary template** (keep it compact — top 3 critical + top 3 major is sufficient; do not expand full issue lists to preserve main context):
    ```
    ⚠️ Integration agent failed — inline fallback summary.
    Scope: {scope}
    Available agents: {comma-separated list}
    Missing agents:   {comma-separated list, or "none"}

    Partial Score (N/8 subcategories): {score}/100   Rank: {rank} (partial if applicable)

    Top 3 critical issues:
      1. [critical] {message} ({file}:{line})
      2. ...
    Top 3 major issues:
      1. [major] {message} ({file}:{line})
      2. ...

    Raw JSON: {work_dir}/
    ```
  - Apply the §Step 3.5 #3 partial normalization even in fallback mode when fewer than 8 subcategories are available.

## Important Rules

- **Headless execution**: Do not prompt the user for confirmation at any step.
- **Parallel execution via single turn**: Issue all `spawn_agent` calls in a single turn to run them in parallel.
- **Graceful degradation**: Partial results are better than no results. If some agents fail, generate a report from the successful agents.
- **Do not read agent-*.json or report.md into the main context** (except summary.txt). This preserves context window space.

## Reference

- Review criteria details: [references/review-criteria.md](references/review-criteria.md)
- Report template: [references/report-template.md](references/report-template.md)
- Agent prompt templates: [references/agent-prompts.md](references/agent-prompts.md)
