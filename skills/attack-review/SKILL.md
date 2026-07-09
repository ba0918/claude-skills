---
name: attack-review
description: コードベースを攻撃者視点で6つの専門エージェント（Injection/AuthN・AuthZ/Client Attack/Data・Secrets/Infra・Supply Chain/Business Logic）+ Codex セカンドオピニオンで並行レビューし、リスクマトリクスで脅威を分類する。「attack review」「ペネトレーションレビュー」「攻撃レビュー」「attack-review」「脆弱性レビュー」「セキュリティ攻撃」「pentest review」で起動。モードは `full` / `server` / `client` の 3 種（引数 `server`/`client` で明示、`full` または任意キーワードで 6 エージェント全起動、引数なしはテックスタックから自動検出）。言語固有の攻撃ベクターにも対応。
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

**Target files** (two categories, both included in `target_files`):

1. **Source code**: `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.py`, `*.go`, `*.rs`, `*.java`, `*.php`, `*.dart`, `*.rb`, `*.cs`, `*.html`, `*.css` and other source code.
2. **Manifest / dependency files** (required for Agent 5 Supply Chain): `package.json`, `composer.json`, `go.mod`, `Cargo.toml`, `requirements.txt`, `Pipfile`, `pubspec.yaml`, `Gemfile`, `pom.xml`, `build.gradle`, `*.csproj`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile`.

**Exclude**: `node_modules/`, `dist/`, `build/`, `.git/`, `vendor/`, `*.test.*`, `*.spec.*`, `*.d.ts`, lock files (`package-lock.json`, `yarn.lock`, `Pipfile.lock`, `go.sum`, `Cargo.lock`, `composer.lock`, `Gemfile.lock`), generated files, minified bundles (`*.min.js`, `*.min.css`).

> **Note**: Lock files are excluded from `target_files` for noise reduction, but Agent 5 may consult them directly if needed to confirm a specific CVE. Manifest files are the primary supply-chain surface.

### Step 2: Language Detection & Project Analysis

Follow the language detection contract in [../shared/references/lang-detect.md](../shared/references/lang-detect.md).

1. Read CLAUDE.md (project root + under `.claude/`) to understand project-specific rules
2. **Language detection** per the shared contract:
   - ファイル一覧取得でマーカーファイルを検索 (Cargo.toml, package.json, go.mod, pyproject.toml, pubspec.yaml, composer.json, etc.)
   - Read dependency sections to detect frameworks
   - Assign roles (server / client / both) per the contract's role determination rules
3. **Auto-detect mode resolution** (if mode was not explicitly set in Step 1):
   - Server-role languages detected AND client-role detected → `full`
   - Only server-role languages → `server`
   - Only client-role languages → `client`
   - Cannot determine → `full` (safe default)
4. Understand directory structure
5. **日時をシェルで取得**（以下の正確なコマンドを使用 — コンテキストから推測しない）:
   ```bash
   date +'%Y%m%d-%H%M'   # → e.g. 20260421-1840, used for {YYYYMMDD-HHMM} in work_dir
   date +'%Y-%m-%d %H:%M' # → e.g. 2026-04-21 18:40, used for the datetime field
   ```
   Store both values and reuse them throughout Steps 5-7.
6. **Create work directory** (using the datetime captured above):
   ```bash
   mkdir -p .claude/tmp/attack-review-{YYYYMMDD-HHMM}/
   ```
7. **Preflight check** — Verify write permission:
   ```bash
   touch .claude/tmp/attack-review-{YYYYMMDD-HHMM}/.preflight && rm .claude/tmp/attack-review-{YYYYMMDD-HHMM}/.preflight
   ```
   If this fails, abort immediately:
   ```
   ATTACK REVIEW ABORTED: Cannot write to work directory.
   Path: .claude/tmp/attack-review-{YYYYMMDD-HHMM}/
   Ensure the directory exists and is writable.
   ```
8. **context.json を作成する**。

   **Schema** — every field is required unless marked optional. Use the exact types/values shown:

   | Field | Type | Example / Values | Notes |
   |-------|------|------------------|-------|
   | `project_name` | string | `"fullstack-monorepo"` | Derived from (in this priority order): repo root manifest `name` field (`package.json` / `Cargo.toml` / `composer.json` / `pyproject.toml` `[project].name` / `pubspec.yaml` `name`), CLAUDE.md top-level heading, or the directory basename. |
   | `scope` | string | `"Entire codebase"` / `"git diff HEAD"` / `"src/auth/"` | Exact values: `"Entire codebase"` when no scope argument, `"git diff HEAD"` when `--diff`, or the directory path string when a directory is specified. |
   | `mode` | string enum | `"full"` / `"server"` / `"client"` | Must be one of these 3 exact values. |
   | `detected_languages` | array<object> | (see below) | Never empty. |
   | `detected_languages[].language` | string | `"typescript"`, `"javascript"`, `"python"`, `"go"`, `"rust"`, `"php"`, `"dart"`, `"ruby"`, `"java"`, `"csharp"` | Lowercase. |
   | `detected_languages[].role` | string enum | `"server"` / `"client"` / `"both"` | Per lang-detect.md role determination. |
   | `detected_languages[].framework` | string \| null | `"Express"`, `"React"`, `"none"` | Use `"none"` (literal string) when no framework detected. Never `null`. |
   | `detected_languages[].marker_file` | string \| null | `"package.json"` / `null` | `null` is legal (e.g., legacy PHP without composer.json — detection by `.php` file globbing). |
   | `detected_languages[].variant` | string \| null (optional) | `"legacy"`, `"modern"`, `"python2"`, `null` | **Optional field.** Include for PHP (`"legacy"` when no composer.json + `.php` files detected, else `"modern"`) or Python 2.x. Omit for languages without variant distinction. Downstream agents use this to select Legacy vs Modern language profile sections. |
   | `is_monorepo` | boolean | `true` / `false` | `true` when marker files exist in 2+ sibling subdirectories under the repo root (per lang-detect.md). A root-level marker alone does not count. |
   | `primary_language` | string | `"go"` | Server-role language wins over client-role. If multiple server-role languages exist, use the first one detected (file-glob order). |
   | `target_files` | array<string> | `["client/package.json", "client/src/App.tsx", "package.json", "server/package.json", "server/src/app.js"]` | See **Target files** definition in Step 1. Include manifest files (`package.json`, `composer.json`, `go.mod`, `Cargo.toml`, `requirements.txt`, `Pipfile`, `pubspec.yaml`, `Gemfile`, `pom.xml`) **in addition to** the source-code extensions — they are required for Agent 5 (Supply Chain) analysis. **Sort order: alphabetical by path string** (stable across runs, deterministic). |
   | `file_count` | number | `42` | Must equal `target_files.length`. |
   | `claude_md_rules` | string | `"..."` / `""` | The full contents of the CLAUDE.md file(s) joined with `\n\n---\n\n` separators, or the empty string `""` when no CLAUDE.md exists. Never `null`. |
   | `work_dir` | string | `".claude/tmp/attack-review-20260421-1840"` | Concrete path — substitute `{YYYYMMDD-HHMM}` with the actual datetime. |
   | `datetime` | string | `"2026-04-21 18:40"` | Format: `YYYY-MM-DD HH:MM`. |

   **Canonical example**:

   ```json
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
     "claude_md_rules": "",
     "work_dir": ".claude/tmp/attack-review-20260421-1840",
     "datetime": "2026-04-21 18:40"
   }
   ```

   **Legacy PHP example** (no marker file, variant field in use):

   ```json
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
     "claude_md_rules": "",
     "work_dir": ".claude/tmp/attack-review-20260421-1840",
     "datetime": "2026-04-21 18:40"
   }
   ```

### Step 3: Launch Agents in Parallel

決定されたモードに基づいてエージェントを選択し起動する。すべてのサブエージェント起動を**単一メッセージで**行う — 複数メッセージに分割しない。

**モデル階層**: コアエージェントと統合エージェントは高性能モデルで実行する — 攻撃発見には機械的検証ゲートがないため、見落とした脆弱性はそのまま通過する。セキュリティ分類器がリフューザルを返す可能性のあるモデルは使用しない。

プロンプトテンプレート・攻撃基準・言語プロファイル:
- [references/agent-prompts.md](references/agent-prompts.md)
- [references/attack-criteria.md](references/attack-criteria.md)
- [references/lang-profiles.md](references/lang-profiles.md)

#### Agent Selection by Mode

**full mode** — 7 エージェント全起動（すべて自動実行モード・高性能モデル）:
```
起動するサブエージェント:

1. injection-hunter        — Injection Attack → {work_dir}/agent-1-injection.json
                             criteria: § Agent 1 from attack-criteria.md
                             lang_profile: Server-role sections from lang-profiles.md

2. authn-authz-breaker     — AuthN/AuthZ Attack → {work_dir}/agent-2-authn-authz.json
                             criteria: § Agent 2 from attack-criteria.md
                             lang_profile: All detected language sections

3. client-attack-specialist — Client-Side Attack → {work_dir}/agent-3-client-attack.json
                             criteria: § Agent 3 from attack-criteria.md
                             lang_profile: Client-role sections from lang-profiles.md

4. data-secrets-exfiltrator — Data & Secrets → {work_dir}/agent-4-data-secrets.json
                             criteria: § Agent 4 from attack-criteria.md
                             lang_profile: All detected language sections

5. infra-supply-chain-exploiter — Infra & Supply Chain → {work_dir}/agent-5-infra-supply-chain.json
                             criteria: § Agent 5 from attack-criteria.md
                             lang_profile: All detected language sections

6. business-logic-abuser   — Business Logic → {work_dir}/agent-6-business-logic.json
                             criteria: § Agent 6 from attack-criteria.md
                             lang_profile: All detected language sections

7. codex-review            — Codex セカンドオピニオン → {work_dir}/agent-7-codex.json
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

統合エージェント: 汎用サブエージェント、高性能モデル、自動実行モード

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
