---
name: attack-review
description: コードベースを攻撃者視点で6つの専門エージェント（Injection/AuthN・AuthZ/Client Attack/Data・Secrets/Infra・Supply Chain/Business Logic）で並行レビューし、リスクマトリクスで脅威を分類する。「attack review」「ペネトレーションレビュー」「攻撃レビュー」「attack-review」「脆弱性レビュー」「セキュリティ攻撃」「pentest review」で起動。モードは `full` / `server` / `client` の 3 種（引数 `server`/`client` で明示、`full` または任意キーワードで 6 エージェント全起動、引数なしはテックスタックから自動検出）。言語固有の攻撃ベクターにも対応。
---

# Attack Review (Codex Edition)

## Codex CLI ツールの使い分け

- 攻撃観点エージェント起動: `spawn_agent` / `wait_agent`（6体並行）
- テックスタック検出・結果 JSON 受け渡し: `shell`（`cat` / `rg`、`.codex/tmp/`）
- レポート出力: `shell` heredoc

Review the codebase from an **attacker's perspective** with 6 specialized penetration testing agents in parallel. Generate a risk-matrix-based threat report with concrete attack scenarios, reproduction steps, and PoC examples.

**Context-saving design**: All agent analysis results are passed via files; only summaries flow into the main context.

**Headless execution**: Do not prompt the user for confirmation. All agents run autonomously via `spawn_agent`. If an agent fails, continue with the remaining agents (graceful degradation).

**Key difference from codebase-review**: This skill thinks like an attacker ("how do I break in?"), not a defender ("is this secure?"). Output is attack scenarios with reproduction steps, not quality scores.

## Progress Checklist

```
attack-review Progress:
- [ ] Determine mode (full/server/client/auto-detect)
- [ ] Detect languages & analyze project structure
- [ ] Obtain datetime & prepare work directory
- [ ] Preflight check (work directory write permission)
- [ ] Write context.json
- [ ] Launch 6 specialist agents in parallel via spawn_agent
- [ ] Wait for agents & handle failures
- [ ] Launch integration agent
- [ ] Display summary & place report
```

## Workflow

### Step 1: Determine Mode

Parse the invocation arguments (`$ARGUMENTS`) to determine the review mode:

| First keyword in arguments | Mode | Agents launched |
|---------------------------|------|-----------------|
| `server` | server | 1 (Injection), 2 (AuthN/AuthZ), 4 (Data/Secrets), 5 (Infra/Supply), 6 (Business Logic) |
| `client` | client | 2 (AuthN/AuthZ), 3 (Client Attack), 4 (Data/Secrets), 5 (Infra/Supply), 6 (Business Logic) |
| (none) | auto-detect | Determined in Step 2 based on tech stack |
| (anything else) | full | All 6 specialists |

Remaining arguments after the mode keyword are treated as scope hints:

| Scope argument | Target |
|---------------|--------|
| None | Entire codebase |
| `--diff` | Only files changed in `git diff HEAD` |
| Directory name | Specific directory |

**Target files** (two categories, both included in `target_files`):

1. **Source code**: `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.py`, `*.go`, `*.rs`, `*.java`, `*.php`, `*.dart`, `*.rb`, `*.cs`, `*.html`, `*.css` and other source code.
2. **Manifest / dependency files** (required for Agent 5 Supply Chain): `package.json`, `composer.json`, `go.mod`, `Cargo.toml`, `requirements.txt`, `Pipfile`, `pubspec.yaml`, `Gemfile`, `pom.xml`, `build.gradle`, `*.csproj`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile`.

**Exclude**: `node_modules/`, `dist/`, `build/`, `.git/`, `vendor/`, `*.test.*`, `*.spec.*`, `*.d.ts`, lock files (`package-lock.json`, `yarn.lock`, `Pipfile.lock`, `go.sum`, `Cargo.lock`, `composer.lock`, `Gemfile.lock`), generated files, minified bundles (`*.min.js`, `*.min.css`).

> **Note**: Lock files are excluded from `target_files` for noise reduction, but Agent 5 may consult them directly via `cat` if needed to confirm a specific CVE. Manifest files are the primary supply-chain surface.

**Empty target abort (evaluate BEFORE Step 2 — do not create the work directory if the list is empty)**: If the filtered `target_files` list is empty (e.g., clean working tree on `--diff`, or project with no matching source files), do NOT create the work directory and do NOT launch any agents. Print and exit cleanly:

```
⚠️ ATTACK REVIEW SKIPPED: No reviewable source files found.
   Scope: {scope}
   If you expected files, re-check the argument or verify the allowlist/blocklist.
```

### Step 2: Language Detection & Project Analysis

Follow the language detection contract in [../shared/references/lang-detect.md](../shared/references/lang-detect.md).

1. Read AGENTS.md (project root + under `.codex/` if present) via `shell` (`cat`) to understand project-specific rules
2. **Language detection** per the shared contract:
   - Use `shell` (`ls`, `find`) to glob for marker files (Cargo.toml, package.json, go.mod, pyproject.toml, pubspec.yaml, composer.json, etc.)
   - `cat` dependency sections to detect frameworks
   - Assign roles (server / client / both) per the contract's role determination rules
3. **Auto-detect mode resolution** (if mode was not explicitly set in Step 1):
   - Server-role languages detected AND client-role detected → `full`
   - Only server-role languages → `server`
   - Only client-role languages → `client`
   - Cannot determine → `full` (safe default)
4. Understand directory structure
5. **Obtain datetime via shell** (use these exact commands — do not guess from context):
   ```bash
   date +'%Y%m%d-%H%M'   # → e.g. 20260421-1840, used for {YYYYMMDD-HHMM} in work_dir
   date +'%Y-%m-%d %H:%M' # → e.g. 2026-04-21 18:40, used for the datetime field
   ```
   Store both values and reuse them throughout Steps 5-8.
6. **Create work directory** (using the datetime captured above):
   ```bash
   mkdir -p .codex/tmp/attack-review-{YYYYMMDD-HHMM}/
   ```
7. **Preflight check** — Verify write permission:
   ```bash
   touch .codex/tmp/attack-review-{YYYYMMDD-HHMM}/.preflight && rm .codex/tmp/attack-review-{YYYYMMDD-HHMM}/.preflight
   ```
   If this fails, abort immediately:
   ```
   ⛔ ATTACK REVIEW ABORTED: Cannot write to work directory.
   Path: .codex/tmp/attack-review-{YYYYMMDD-HHMM}/
   Ensure the directory exists and is writable.
   ```
8. **Write context.json** via `shell` heredoc.

   **Schema** — every field is required unless marked optional. Use the exact types/values shown:

   | Field | Type | Example / Values | Notes |
   |-------|------|------------------|-------|
   | `project_name` | string | `"fullstack-monorepo"` | Derived from (in this priority order): repo root manifest `name` field (`package.json` / `Cargo.toml` / `composer.json` / `pyproject.toml` `[project].name` / `pubspec.yaml` `name`), AGENTS.md top-level heading, or the directory basename. |
   | `scope` | string | `"Entire codebase"` / `"git diff HEAD"` / `"src/auth/"` | Exact values: `"Entire codebase"` when no scope argument, `"git diff HEAD"` when `--diff`, or the directory path string when a directory is specified. |
   | `mode` | string enum | `"full"` / `"server"` / `"client"` | Must be one of these 3 exact values. |
   | `detected_languages` | array<object> | (see below) | Never empty. |
   | `detected_languages[].language` | string | `"typescript"`, `"javascript"`, `"python"`, `"go"`, `"rust"`, `"php"`, `"dart"`, `"ruby"`, `"java"`, `"csharp"` | Lowercase. |
   | `detected_languages[].role` | string enum | `"server"` / `"client"` / `"both"` | Per lang-detect.md role determination. |
   | `detected_languages[].framework` | string | `"Express"`, `"React"`, `"none"` | Use `"none"` (literal string) when no framework detected. Never `null`. |
   | `detected_languages[].marker_file` | string \| null | `"package.json"` / `null` | `null` is legal (e.g., legacy PHP without composer.json — detection by `.php` file globbing). |
   | `detected_languages[].variant` | string \| null (optional) | `"legacy"`, `"modern"`, `"python2"`, `null` | **Optional field.** Include for PHP (`"legacy"` when no composer.json + `.php` files detected, else `"modern"`) or Python 2.x. Omit for languages without variant distinction. Downstream agents use this to select Legacy vs Modern language profile sections. |
   | `is_monorepo` | boolean | `true` / `false` | `true` when marker files exist in 2+ sibling subdirectories under the repo root (per lang-detect.md). A root-level marker alone does not count. |
   | `primary_language` | string | `"go"` | Server-role language wins over client-role. If multiple server-role languages exist, use the first one detected (file-glob order). |
   | `target_files` | array<string> | `["client/package.json", "client/src/App.tsx", "package.json", "server/package.json", "server/src/app.js"]` | See **Target files** definition in Step 1. Include manifest files in addition to the source-code extensions — they are required for Agent 5 (Supply Chain). **Sort order: alphabetical by path string** (stable across runs, deterministic). |
   | `file_count` | number | `42` | Must equal `target_files.length`. |
   | `agents_md_rules` | string | `"..."` / `""` | The full contents of the AGENTS.md file(s) joined with `\n\n---\n\n` separators, or the empty string `""` when no AGENTS.md exists. Never `null`. |
   | `work_dir` | string | `".codex/tmp/attack-review-20260421-1840"` | Concrete path — substitute `{YYYYMMDD-HHMM}` with the actual datetime. |
   | `datetime` | string | `"2026-04-21 18:40"` | Format: `YYYY-MM-DD HH:MM`. |

   **Canonical example**:

   ```bash
   cat > {work_dir}/context.json << 'EOF'
   {
     "project_name": "fullstack-monorepo",
     "scope": "Entire codebase",
     "mode": "full",
     "detected_languages": [
       {
         "language": "typescript",
         "role": "client",
         "framework": "React",
         "marker_file": "client/package.json"
       },
       {
         "language": "go",
         "role": "server",
         "framework": "Gin",
         "marker_file": "go.mod"
       }
     ],
     "is_monorepo": true,
     "primary_language": "go",
     "target_files": [
       "client/package.json",
       "client/src/App.tsx",
       "go.mod",
       "server/main.go"
     ],
     "file_count": 4,
     "agents_md_rules": "",
     "work_dir": ".codex/tmp/attack-review-20260421-1840",
     "datetime": "2026-04-21 18:40"
   }
   EOF
   ```

   **Legacy PHP example** (no marker file, variant field in use):

   ```bash
   cat > {work_dir}/context.json << 'EOF'
   {
     "project_name": "legacy-app",
     "scope": "Entire codebase",
     "mode": "server",
     "detected_languages": [
       {
         "language": "php",
         "role": "server",
         "framework": "none",
         "marker_file": null,
         "variant": "legacy"
       }
     ],
     "is_monorepo": false,
     "primary_language": "php",
     "target_files": ["admin.php", "db.php", "index.php"],
     "file_count": 3,
     "agents_md_rules": "",
     "work_dir": ".codex/tmp/attack-review-20260421-1840",
     "datetime": "2026-04-21 18:40"
   }
   EOF
   ```

### Step 3: Launch Agents in Parallel

Based on the determined mode, select and launch agents. Issue all `spawn_agent` calls in a **single turn** — do not split across multiple turns.

**Placeholder expansion**: When building each agent's prompt, replace every placeholder (`{variable}`, `{attack_criteria_section}`, `{lang_profile_sections}`, `{work_dir}`, etc.) with the **actual content** inlined — do not forward unresolved placeholders to the sub-agent. The sub-agent does not have SKILL.md context and cannot resolve them.

Prompt templates, attack criteria, and language profiles are in:
- [references/agent-prompts.md](references/agent-prompts.md)
- [references/attack-criteria.md](references/attack-criteria.md)
- [references/lang-profiles.md](references/lang-profiles.md)

#### Agent Selection by Mode

**full mode** — all 6 agents:

```
spawn_agent: "injection-hunter"
  → agent_name: "Injection Hunter"
  → criteria: § Agent 1 of references/attack-criteria.md
  → lang_profile: Server-role sections from references/lang-profiles.md
  → output: "{work_dir}/agent-1-injection.json"

spawn_agent: "authn-authz-breaker"
  → agent_name: "AuthN/AuthZ Breaker"
  → criteria: § Agent 2 of references/attack-criteria.md
  → lang_profile: All detected language sections from references/lang-profiles.md
  → output: "{work_dir}/agent-2-authn-authz.json"

spawn_agent: "client-attack-specialist"
  → agent_name: "Client Attack Specialist"
  → criteria: § Agent 3 of references/attack-criteria.md
  → lang_profile: Client-role sections from references/lang-profiles.md
  → output: "{work_dir}/agent-3-client-attack.json"

spawn_agent: "data-secrets-exfiltrator"
  → agent_name: "Data & Secrets Exfiltrator"
  → criteria: § Agent 4 of references/attack-criteria.md
  → lang_profile: All detected language sections from references/lang-profiles.md
  → output: "{work_dir}/agent-4-data-secrets.json"

spawn_agent: "infra-supply-chain-exploiter"
  → agent_name: "Infra & Supply Chain Exploiter"
  → criteria: § Agent 5 of references/attack-criteria.md
  → lang_profile: All detected language sections from references/lang-profiles.md
  → output: "{work_dir}/agent-5-infra-supply-chain.json"

spawn_agent: "business-logic-abuser"
  → agent_name: "Business Logic Abuser"
  → criteria: § Agent 6 of references/attack-criteria.md
  → lang_profile: All detected language sections from references/lang-profiles.md
  → output: "{work_dir}/agent-6-business-logic.json"
```

**server mode** — skip Agent 3 (Client Attack Specialist):
- Launch agents 1, 2, 4, 5, 6 (5 total)

**client mode** — skip Agent 1 (Injection Hunter):
- Launch agents 2, 3, 4, 5, 6 (5 total)

#### Language Profile Injection Rules

Each agent receives language-specific attack profiles based on the detected tech stack:

| Agent | Receives profiles for |
|-------|----------------------|
| 1 (Injection Hunter) | `role: "server"` or `"both"` languages only |
| 2 (AuthN/AuthZ Breaker) | All detected languages |
| 3 (Client Attack Specialist) | `role: "client"` or `"both"` languages only |
| 4 (Data & Secrets Exfiltrator) | All detected languages |
| 5 (Infra & Supply Chain Exploiter) | All detected languages |
| 6 (Business Logic Abuser) | All detected languages |

See references/agent-prompts.md § "Section Extraction Rules" for the precise byte-range rules (including Legacy PHP ordering).

### Step 3.5: Wait for Agents & Handle Failures

After all agents complete (`wait_agent`), verify results:

1. Check that each expected JSON file exists in the work directory via `shell` (`ls`).

2. **Graceful degradation**:

   Count how many agent result files exist. The expected count varies by mode:

   | Mode | Total agents | OK (proceed) | Warn (partial) | Abort |
   |------|-------------|--------------|----------------|-------|
   | full | 6 | 4+ | 2-3 | 0-1 |
   | server | 5 | 3+ | 2 | 0-1 |
   | client | 5 | 3+ | 2 | 0-1 |

   Warning format:
   ```
   ⚠️ {N}/{total} attack review agents completed. Missing: {list of failed agent names}
   Proceeding with partial results...
   ```

   Abort format:
   ```
   ⛔ ATTACK REVIEW ABORTED: Only {N}/{total} attack review agents completed.
   Missing: {list of failed agent names}
   Check .codex/tmp/attack-review-{YYYYMMDD-HHMM}/ for any partial results.
   ```

### Step 4: Launch Integration Agent

**After confirming sufficient agents have completed**, launch the integration agent via `spawn_agent`.

Use the integration agent prompt template from [references/agent-prompts.md](references/agent-prompts.md) § Integration Agent Prompt Template.

The integration agent:
1. Reads context.json + all available agent JSON files via `cat`
2. Follows [references/report-template.md](references/report-template.md)
3. Deduplicates findings across agents
4. Sorts by risk level (Critical → High → Medium → Low), with likelihood higher first within the same level
5. Determines overall risk posture
6. Writes `{work_dir}/summary.txt` (ASCII console display) via heredoc
7. Writes `{work_dir}/report.md` (full attack report) via heredoc

If some agents are missing, add to the integration agent prompt:
```
Note: The following agent results are missing: {list}. Generate the report using only the available agent results. Mark missing attack domains as "N/A — agent did not complete" in the report.
```

`{list}` uses filename form — comma-separated JSON filenames (e.g., `agent-3-client-attack.json, agent-5-infra-supply-chain.json`).

### Step 5: Display Summary & Archive Report

After confirming the integration agent has completed:

1. **Read** `{work_dir}/summary.txt` via `shell` (`cat`) and display it to the console as-is
2. **Copy** the full report to the reviews archive (ensure target directory exists first):
   ```bash
   mkdir -p docs/reviews && cp {work_dir}/report.md docs/reviews/attack-review-{YYYYMMDD-HHMM}.md
   ```
3. Display completion message:
   ```
   Full report: docs/reviews/attack-review-{YYYYMMDD-HHMM}.md
   ```

**Note**: Do not read files other than `summary.txt` (agent-*.json, report.md) into the main context.

## Error Handling

### Preflight failures (Step 2)
- **Work directory write failure**: Abort immediately with error message. Do not launch any agents.

### Agent failures (Step 3)
- Graceful degradation per the table in Step 3.5. Partial results proceed to Step 4.
- **Agent timeout**: If an agent does not complete within a reasonable time, treat it as failed.

### Integration agent failure (Step 4)
- **Integration agent fails** (no `summary.txt` was produced): Read available agent JSON files directly via `cat` and generate a minimal summary in the main context (inline fallback).
  - **Skip the Step 5 `cp` step** — there is no `report.md` to place.
  - Tell the user explicitly: `⚠️ Integration agent failed. No docs/reviews/attack-review-*.md was generated. Raw JSON is in {work_dir}/ for manual inspection.`
  - **Inline fallback summary template** (keep it compact — top 3 Critical + top 3 High is sufficient):
    ```
    ⚠️ Integration agent failed — inline fallback summary.
    Scope: {scope}
    Mode: {mode}
    Available agents: {comma-separated list}
    Missing agents:   {comma-separated list, or "none"}

    Overall Posture: {derived from highest severity}

    Top 3 Critical findings:
      1. [critical] {title} ({file}:{line})
      2. ...
    Top 3 High findings:
      1. [high] {title} ({file}:{line})
      2. ...

    Raw JSON: {work_dir}/
    ```

## Important Rules

- **Headless execution**: Do not prompt the user for confirmation at any step.
- **Parallel execution via single turn**: Issue all `spawn_agent` calls in a single turn to run them in parallel.
- **Graceful degradation**: Partial results are better than no results. If some agents fail, generate a report from the successful agents.
- **Do not read agent-*.json or report.md into the main context** (except summary.txt). This preserves context window space.
- **Attacker's perspective only**: Agents must think "how do I break in?", not "is this secure?". Output is attack scenarios with reproduction steps, not defensive recommendations.

## Reference

- Attack criteria details: [references/attack-criteria.md](references/attack-criteria.md)
- Language-specific attack profiles: [references/lang-profiles.md](references/lang-profiles.md)
- Report template: [references/report-template.md](references/report-template.md)
- Agent prompt templates: [references/agent-prompts.md](references/agent-prompts.md)
- Language detection contract: [../shared/references/lang-detect.md](../shared/references/lang-detect.md)
