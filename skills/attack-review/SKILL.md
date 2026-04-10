---
name: attack-review
description: コードベースを攻撃者視点で6つの専門エージェント（Injection/AuthN・AuthZ/Client Attack/Data・Secrets/Infra・Supply Chain/Business Logic）+ Codex セカンドオピニオンで並行レビューし、リスクマトリクスで脅威を分類する。「attack review」「ペネトレーションレビュー」「攻撃レビュー」「attack-review」「脆弱性レビュー」「セキュリティ攻撃」「pentest review」で起動。server/client 引数でモードを切り替え、引数なしはテックスタック自動検出。言語固有の攻撃ベクターにも対応。
---

# Attack Review

Review the codebase from an **attacker's perspective** with 6 specialized penetration testing agents + Codex second opinion in parallel. Generate a risk-matrix-based threat report with concrete attack scenarios, reproduction steps, and PoC examples.

**Context-saving design**: All agent analysis results are passed via files; only summaries flow into the main context.

**Headless execution**: Do not prompt the user for confirmation. All agents run autonomously. If an agent fails, continue with the remaining agents (graceful degradation).

**Key difference from codebase-review**: This skill thinks like an attacker ("how do I break in?"), not a defender ("is this secure?"). Output is attack scenarios with reproduction steps, not quality scores.

## Progress Checklist

```
attack-review Progress:
- [ ] Determine mode (full/server/client/auto-detect)
- [ ] Detect languages & analyze project structure
- [ ] Prepare work directory & write context.json
- [ ] Preflight check (work directory write permission)
- [ ] Launch specialist agents + Codex in parallel
- [ ] Wait for agents & handle failures
- [ ] Launch integration agent
- [ ] Display summary & place report
```

## Workflow

### Step 1: Determine Mode

Parse `$ARGUMENTS` to determine the review mode:

| First keyword in arguments | Mode | Agents launched |
|---------------------------|------|-----------------|
| `server` | server | 1 (Injection), 2 (AuthN/AuthZ), 4 (Data/Secrets), 5 (Infra/Supply), 6 (Business Logic) + Codex |
| `client` | client | 2 (AuthN/AuthZ), 3 (Client Attack), 4 (Data/Secrets), 5 (Infra/Supply), 6 (Business Logic) + Codex |
| (none) | auto-detect | Determined in Step 2 based on tech stack |
| (anything else) | full | All 6 specialists + Codex |

Remaining arguments after the mode keyword are treated as scope hints:

| Scope argument | Target |
|---------------|--------|
| None | Entire codebase |
| `--diff` | Only files changed in `git diff HEAD` |
| Directory name | Specific directory |

Target files: `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.py`, `*.go`, `*.rs`, `*.java`, `*.php`, `*.dart`, `*.rb`, `*.cs`, `*.html`, `*.css` and other source code.
Exclude: `node_modules/`, `dist/`, `build/`, `.git/`, `vendor/`, `*.test.*`, `*.spec.*`, `*.d.ts`, lock files, generated files.

### Step 2: Language Detection & Project Analysis

Follow the language detection contract in [../shared/references/lang-detect.md](../shared/references/lang-detect.md).

1. Read CLAUDE.md (project root + under `.claude/`) to understand project-specific rules
2. **Language detection** per the shared contract:
   - Glob for marker files (Cargo.toml, package.json, go.mod, pyproject.toml, pubspec.yaml, composer.json, etc.)
   - Read dependency sections to detect frameworks
   - Assign roles (server / client / both) per the contract's role determination rules
3. **Auto-detect mode resolution** (if mode was not explicitly set in Step 1):
   - Server-role languages detected AND client-role detected → `full`
   - Only server-role languages → `server`
   - Only client-role languages → `client`
   - Cannot determine → `full` (safe default)
4. Understand directory structure
5. **Create work directory**:
   ```bash
   mkdir -p .claude/tmp/attack-review-{YYYYMMDD-HHMM}/
   ```
6. **Preflight check** — Verify write permission:
   ```bash
   touch .claude/tmp/attack-review-{YYYYMMDD-HHMM}/.preflight && rm .claude/tmp/attack-review-{YYYYMMDD-HHMM}/.preflight
   ```
   If this fails, abort immediately:
   ```
   ATTACK REVIEW ABORTED: Cannot write to work directory.
   Path: .claude/tmp/attack-review-{YYYYMMDD-HHMM}/
   Ensure the directory exists and is writable.
   ```
7. **Write context.json** (create with Write tool):
   ```json
   {
     "project_name": "Project name from directory or CLAUDE.md",
     "scope": "Target scope description",
     "mode": "full|server|client",
     "detected_languages": [
       {
         "language": "typescript",
         "role": "client",
         "framework": "React",
         "marker_file": "package.json"
       },
       {
         "language": "go",
         "role": "server",
         "framework": "Gin",
         "marker_file": "go.mod"
       }
     ],
     "is_monorepo": false,
     "primary_language": "go",
     "target_files": ["List of target file paths"],
     "file_count": 0,
     "claude_md_rules": "CLAUDE.md contents (if present)",
     "work_dir": ".claude/tmp/attack-review-{YYYYMMDD-HHMM}",
     "datetime": "YYYY-MM-DD HH:MM"
   }
   ```

### Step 3: Launch Agents in Parallel

Based on the determined mode, select and launch agents. Issue all Agent tool calls in a **single message** — do not split across multiple messages.

Prompt templates, attack criteria, and language profiles are in:
- [references/agent-prompts.md](references/agent-prompts.md)
- [references/attack-criteria.md](references/attack-criteria.md)
- [references/lang-profiles.md](references/lang-profiles.md)

#### Agent Selection by Mode

**full mode** — all 7 agents:
```pseudocode
// All calls in ONE message
Agent(
  name: "injection-hunter",
  description: "Injection Attack Review",
  subagent_type: "general-purpose",
  mode: "bypassPermissions",
  prompt: <Template from agent-prompts.md>
          agent_name   = "Injection Hunter"
          criteria     = § Agent 1 from attack-criteria.md
          lang_profile = Server-role sections from lang-profiles.md
          output       = "{work_dir}/agent-1-injection.json"
)
Agent(
  name: "authn-authz-breaker",
  description: "AuthN/AuthZ Attack Review",
  subagent_type: "general-purpose",
  mode: "bypassPermissions",
  prompt: <Template from agent-prompts.md>
          agent_name   = "AuthN/AuthZ Breaker"
          criteria     = § Agent 2 from attack-criteria.md
          lang_profile = All detected language sections from lang-profiles.md
          output       = "{work_dir}/agent-2-authn-authz.json"
)
Agent(
  name: "client-attack-specialist",
  description: "Client-Side Attack Review",
  subagent_type: "general-purpose",
  mode: "bypassPermissions",
  prompt: <Template from agent-prompts.md>
          agent_name   = "Client Attack Specialist"
          criteria     = § Agent 3 from attack-criteria.md
          lang_profile = Client-role sections from lang-profiles.md
          output       = "{work_dir}/agent-3-client-attack.json"
)
Agent(
  name: "data-secrets-exfiltrator",
  description: "Data & Secrets Exposure Review",
  subagent_type: "general-purpose",
  mode: "bypassPermissions",
  prompt: <Template from agent-prompts.md>
          agent_name   = "Data & Secrets Exfiltrator"
          criteria     = § Agent 4 from attack-criteria.md
          lang_profile = All detected language sections from lang-profiles.md
          output       = "{work_dir}/agent-4-data-secrets.json"
)
Agent(
  name: "infra-supply-chain-exploiter",
  description: "Infra & Supply Chain Attack Review",
  subagent_type: "general-purpose",
  mode: "bypassPermissions",
  prompt: <Template from agent-prompts.md>
          agent_name   = "Infra & Supply Chain Exploiter"
          criteria     = § Agent 5 from attack-criteria.md
          lang_profile = All detected language sections from lang-profiles.md
          output       = "{work_dir}/agent-5-infra-supply-chain.json"
)
Agent(
  name: "business-logic-abuser",
  description: "Business Logic Attack Review",
  subagent_type: "general-purpose",
  mode: "bypassPermissions",
  prompt: <Template from agent-prompts.md>
          agent_name   = "Business Logic Abuser"
          criteria     = § Agent 6 from attack-criteria.md
          lang_profile = All detected language sections from lang-profiles.md
          output       = "{work_dir}/agent-6-business-logic.json"
)
Agent(
  name: "codex-review",
  description: "Codex Security Second Opinion",
  subagent_type: "codex:codex-rescue",
  mode: "bypassPermissions",
  prompt: <Codex template from agent-prompts.md>
          output       = "{work_dir}/agent-7-codex.json"
)
```

**server mode** — skip Agent 3 (Client Attack Specialist):
- Launch agents 1, 2, 4, 5, 6, 7 (6 total)

**client mode** — skip Agent 1 (Injection Hunter):
- Launch agents 2, 3, 4, 5, 6, 7 (6 total)

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
| 7 (Codex) | All detected languages (via context.json) |

Codex セキュリティ制約・フォールバックの共通パターン: [../shared/references/codex-integration.md](../shared/references/codex-integration.md)

### Step 3.5: Wait for Agents & Handle Failures

After all agents complete, verify results:

1. Check that each expected JSON file exists in the work directory.

2. **Graceful degradation for core agents (1-6)**:

   Count how many core agent result files exist. The expected count varies by mode:

   | Mode | Total core agents | OK (proceed) | Warn (partial) | Abort |
   |------|-------------------|--------------|----------------|-------|
   | full | 6 | 4+ | 2-3 | 0-1 |
   | server | 5 | 3+ | 2 | 0-1 |
   | client | 5 | 3+ | 2 | 0-1 |

   Warning format:
   ```
   {N}/{total} attack review agents completed. Missing: {list of failed agent names}
   Proceeding with partial results...
   ```

   Abort format:
   ```
   ATTACK REVIEW ABORTED: Only {N}/{total} attack review agents completed.
   Missing: {list of failed agent names}
   Check .claude/tmp/attack-review-{YYYYMMDD-HHMM}/ for any partial results.
   ```

3. **Codex agent (Agent 7) is independent**: If `agent-7-codex.json` is missing, display a warning and proceed without Codex perspective:
   ```
   Codex second opinion unavailable — proceeding with existing review only.
   ```
   Codex failure does NOT affect the core agent success/failure count.

### Step 4: Launch Integration Agent

**After confirming sufficient agents have completed**, launch the integration agent.

Integration agent: `subagent_type: general-purpose`, `mode: bypassPermissions`

Use the integration agent prompt template from [references/agent-prompts.md](references/agent-prompts.md) § Integration Agent Prompt Template.

The integration agent:
1. Reads context.json + all available agent JSON files
2. Follows [references/report-template.md](references/report-template.md)
3. Deduplicates findings across agents
4. Sorts by risk level (Critical → High → Medium → Low)
5. Determines overall risk posture
6. Writes `{work_dir}/summary.txt` (ASCII console display)
7. Writes `{work_dir}/report.md` (full attack report)

If some agents are missing, add to the integration agent prompt:
```
Note: The following agent results are missing: {list}. Generate the report using only the available agent results. Mark missing attack domains as "N/A — agent did not complete" in the report.
```

### Step 5: Display Summary & Archive Report

1. Read `{work_dir}/summary.txt` and display its contents to the user
2. Copy the full report to the reviews archive:
   ```bash
   cp {work_dir}/report.md docs/reviews/attack-review-{YYYYMMDD-HHMM}.md
   ```
   If `docs/reviews/` doesn't exist, create it first.
3. Display completion message:
   ```
   Full report: docs/reviews/attack-review-{YYYYMMDD-HHMM}.md
   ```
