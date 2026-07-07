# Report Template

attack-review 統合エージェントが参照するレポートテンプレート。
`{variable_name}` プレースホルダは統合エージェントが各攻撃エージェントの JSON 出力から取得した値で置換する。

---

## summary.txt テンプレート

コンソールに表示する ASCII アートサマリー。統合エージェントはこのフォーマットに従って `summary.txt` を生成する。

```
╔══════════════════════════════════════════════════════════════════════╗
║                      ATTACK REVIEW REPORT                          ║
╠══════════════════════════════════════════════════════════════════════╣
║  Project:    {project_name}                                        ║
║  Date:       {datetime}                                            ║
║  Mode:       {mode}                                                ║
║  Languages:  {detected_languages}                                  ║
╚══════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────┐
│  RISK DISTRIBUTION                                                   │
├──────────────────────────┬──────────┬──────┬───────┬───────┬────────┤
│  Attack Domain           │ Critical │ High │  Med  │  Low  │ Total  │
├──────────────────────────┼──────────┼──────┼───────┼───────┼────────┤
│  Injection               │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
│  AuthN/AuthZ             │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
│  Client Attack           │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
│  Data & Secrets          │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
│  Infra & Supply Chain    │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
│  Business Logic          │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
├──────────────────────────┼──────────┼──────┼───────┼───────┼────────┤
│  TOTAL                   │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
└──────────────────────────┴──────────┴──────┴───────┴───────┴────────┘

  *** OVERALL RISK POSTURE: {overall_posture} ***

  {critical_count} Critical | {high_count} High | {medium_count} Medium | {low_count} Low

┌──────────────────────────────────────────────────────────────────────┐
│  TOP 5 ATTACK SCENARIOS                                              │
├──────────────────────────────────────────────────────────────────────┤
│  1. [{risk_level}] {title}                                           │
│     {file}:{line}                                                    │
│                                                                      │
│  2. [{risk_level}] {title}                                           │
│     {file}:{line}                                                    │
│                                                                      │
│  3. [{risk_level}] {title}                                           │
│     {file}:{line}                                                    │
│                                                                      │
│  4. [{risk_level}] {title}                                           │
│     {file}:{line}                                                    │
│                                                                      │
│  5. [{risk_level}] {title}                                           │
│     {file}:{line}                                                    │
└──────────────────────────────────────────────────────────────────────┘

  Full report: {report_path}
```

### summary.txt フィールド説明

| フィールド | 説明 |
|-----------|------|
| `project_name` | プロジェクト名（リポジトリ名またはディレクトリ名） |
| `datetime` | レビュー実行日時 `YYYY-MM-DD HH:MM:SS` |
| `mode` | 実行モード: `full` / `server` / `client` のいずれか |
| `detected_languages` | 検出された言語・フレームワーク（カンマ区切り） |
| `overall_posture` | 総合リスク姿勢: `Critical Risk` / `High Risk` / `Moderate Risk` / `Low Risk` / `Minimal Risk` |
| `critical_count` / `high_count` / `medium_count` / `low_count` | 各リスクレベルの検出数 |
| `risk_level` | 個別 finding のリスクレベル: `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` |
| `report_path` | 生成された report.md の絶対パス |

### summary.txt 表示ルール

- **Top 5 Attack Scenarios**: finding が 5 件未満の場合は存在する分だけ表示する
- **Top 5 の並び順**: リスクレベル降順（Critical > High > Medium > Low）、同一レベル内は Likelihood 降順（likelihood higher first）
- **overall_posture の決定**: 検出された finding の最高重大度に基づく。Critical が 1 件以上 → `Critical Risk`、High が 1 件以上 → `High Risk`、Medium のみ → `Moderate Risk`、Low のみ → `Low Risk`、finding ゼロ → `Minimal Risk`
- **Risk distribution テーブル**: 該当 finding がゼロの場合は `0` を表示（行自体は省略しない）

---

## report.md テンプレート

`docs/reviews/` に保存する完全版攻撃レビューレポート。統合エージェントはこのフォーマットに従って `report.md` を生成する。

````markdown
# Attack Review Report

## 1. Executive Summary

| Item | Value |
|------|-------|
| Project | {project_name} |
| Review Date | {datetime} |
| Mode | {mode} |
| Target Scope | {scope} |
| Files Analyzed | {file_count} |
| Detected Languages | {detected_languages} |
| Detected Frameworks | {detected_frameworks} |
| Overall Risk Posture | **{overall_posture}** |

{executive_narrative}

> 3-5 sentences describing the most critical findings, the overall attack surface,
> and the immediate actions required. Write from an attacker's perspective:
> what would an attacker target first, what is the blast radius, and what is
> the recommended priority for remediation.

---

## 2. Risk Distribution

| Attack Domain | Critical | High | Medium | Low | Total |
|---------------|----------|------|--------|-----|-------|
| Injection (Agent 1) | {n} | {n} | {n} | {n} | {n} |
| AuthN/AuthZ (Agent 2) | {n} | {n} | {n} | {n} | {n} |
| Client Attack (Agent 3) | {n} | {n} | {n} | {n} | {n} |
| Data & Secrets (Agent 4) | {n} | {n} | {n} | {n} | {n} |
| Infra & Supply Chain (Agent 5) | {n} | {n} | {n} | {n} | {n} |
| Business Logic (Agent 6) | {n} | {n} | {n} | {n} | {n} |
| **TOTAL** | **{n}** | **{n}** | **{n}** | **{n}** | **{n}** |

> **Mode-specific rows**: `server` mode では Agent 3 (Client Attack) の行を `N/A — skipped in server mode` と表示する。`client` mode では Agent 1 (Injection) を `N/A — skipped in client mode` と表示する。エージェント未完了（graceful degradation）の場合は `N/A — agent did not complete` と表示する。

---

## 3. Risk Matrix Legend

Findings are categorized using a **Likelihood x Impact** risk matrix.
All axes use the 4-value scale `critical | high | medium | low` (matching the JSON output schema).

|                          | Impact: Low | Impact: Medium | Impact: High | Impact: Critical |
|--------------------------|-------------|----------------|--------------|------------------|
| **Likelihood: Critical** | Medium      | High           | Critical     | Critical         |
| **Likelihood: High**     | Low         | Medium         | High         | Critical         |
| **Likelihood: Medium**   | Low         | Medium         | High         | High             |
| **Likelihood: Low**      | Low         | Low            | Medium       | High             |

**Likelihood factors**: Attack complexity, required privileges, user interaction needed, exploit availability.

**Impact factors**: Confidentiality loss, integrity loss, availability loss, scope of affected components.

---

## 4. Critical & High Risk Findings

{If no Critical or High findings: "No Critical or High risk findings detected."}

### Finding {index}: {title}

| Attribute | Value |
|-----------|-------|
| Risk Level | **{risk_level}** |
| Likelihood | {likelihood} |
| Impact | {impact} |
| Attack Domain | {attack_domain} |
| CWE | {cwe_id}: {cwe_name} |
| OWASP | {owasp_category} |
| Effort to Fix | {effort_estimate} |

#### Attack Scenario

{attack_scenario_description}

> Narrative description of how an attacker would discover and exploit this
> vulnerability. Include the attacker's goal, the entry point, and the
> expected outcome of a successful attack.

#### Reproduction Steps

1. {step_1}
2. {step_2}
3. {step_3}
...

#### Proof of Concept

```{language}
{poc_code_snippet}
```

#### Affected Files

- `{file_path}:{line_number}` — {brief_context}
- `{file_path}:{line_number}` — {brief_context}

#### Impact

{impact_description}

> Describe the concrete damage: data exfiltration scope, privilege escalation
> path, service disruption potential, compliance violations, etc.

#### Fix Guidance

{fix_guidance}

> Specific, actionable remediation steps. Include code patterns to adopt
> and anti-patterns to avoid. Reference relevant security standards.

---

{Repeat for each Critical and High finding}

## 5. Medium & Low Risk Findings

{If no Medium or Low findings: "No Medium or Low risk findings detected."}

### Finding {index}: {title}

| Attribute | Value |
|-----------|-------|
| Risk Level | **{risk_level}** |
| Likelihood | {likelihood} |
| Impact | {impact} |
| Attack Domain | {attack_domain} |
| CWE | {cwe_id}: {cwe_name} |
| OWASP | {owasp_category} |
| Effort to Fix | {effort_estimate} |

#### Attack Scenario

{attack_scenario_description}

#### Reproduction Steps

1. {step_1}
2. {step_2}
...

#### Proof of Concept

```{language}
{poc_code_snippet}
```

#### Affected Files

- `{file_path}:{line_number}` — {brief_context}

#### Impact

{impact_description}

#### Fix Guidance

{fix_guidance}

---

{Repeat for each Medium and Low finding}

## 6. Remediation Roadmap

Priority-ordered remediation plan based on risk level and fix effort.

### Immediate — Critical Risk (fix within 24 hours)

| # | Finding | Attack Domain | Effort | Owner |
|---|---------|---------------|--------|-------|
| {n} | {finding_title} | {attack_domain} | {effort} | {owner_placeholder} |

{action_items_for_critical}

### Short-term — High Risk (fix within 1 week)

| # | Finding | Attack Domain | Effort | Owner |
|---|---------|---------------|--------|-------|
| {n} | {finding_title} | {attack_domain} | {effort} | {owner_placeholder} |

{action_items_for_high}

### Medium-term — Medium Risk (fix within 1 month)

| # | Finding | Attack Domain | Effort | Owner |
|---|---------|---------------|--------|-------|
| {n} | {finding_title} | {attack_domain} | {effort} | {owner_placeholder} |

{action_items_for_medium}

### Long-term — Low Risk (address in regular maintenance)

| # | Finding | Attack Domain | Effort | Owner |
|---|---------|---------------|--------|-------|
| {n} | {finding_title} | {attack_domain} | {effort} | {owner_placeholder} |

{action_items_for_low}

---

## 7. Appendix

### A. Risk Matrix Definition

This review uses a Likelihood x Impact matrix to determine risk levels:

- **Critical**: Exploitation is straightforward and causes severe damage (data breach, full system compromise, RCE). Requires immediate remediation.
- **High**: Exploitation is feasible with moderate effort and causes significant damage (privilege escalation, partial data exposure). Requires prompt remediation.
- **Medium**: Exploitation requires specific conditions or yields limited impact. Should be addressed in normal development cycles.
- **Low**: Exploitation is unlikely or impact is minimal. Address as part of ongoing code hygiene.

Likelihood assessment considers:
- Attack complexity (network access, special conditions)
- Required privileges (none, low, high)
- User interaction requirements (none, required)
- Exploit maturity (theoretical, proof-of-concept, weaponized)

Impact assessment considers:
- Confidentiality (none, low, high)
- Integrity (none, low, high)
- Availability (none, low, high)
- Scope (unchanged, changed — affects components beyond the vulnerable one)

### B. Attack Domains

| # | Agent / Domain | Coverage |
|---|----------------|----------|
| 1 | Injection Hunter | SQL injection, command injection, SSRF, path traversal, SSTI, XXE, LDAP injection, header injection (server-side sinks) |
| 2 | AuthN/AuthZ Breaker | Authentication bypass, IDOR, privilege escalation, JWT weaknesses, session management flaws, OAuth misconfiguration, Cookie security |
| 3 | Client Attack Specialist | Reflected / Stored / DOM-based XSS, CSRF, DOM Clobbering, prototype pollution (client), open redirect, clickjacking, postMessage abuse, CSS injection |
| 4 | Data & Secrets Exfiltrator | Hardcoded secrets, error message leakage, PII in logs, excessive API responses, exposed files/dirs, source map leaks |
| 5 | Infra & Supply Chain Exploiter | CORS misconfiguration, missing security headers, dependency CVEs, default credentials, insecure TLS, CI/CD poisoning, container misconfig |
| 6 | Business Logic Abuser | Race conditions / TOCTOU, payment/pricing manipulation, rate limiting gaps, enumeration, mass assignment, workflow bypass, business-logic DoS, replay attacks |

### C. Analyzed Files

{List of analyzed file paths, one per line}

### D. Agent Completion Status

| Agent | Status | Findings | Duration |
|-------|--------|----------|----------|
| {agent_name} | {completed / failed / timeout} | {finding_count} | {duration_seconds}s |
| {agent_name} | {completed / failed / timeout} | {finding_count} | {duration_seconds}s |
| {agent_name} | {completed / failed / timeout} | {finding_count} | {duration_seconds}s |

### E. Detected Languages & Frameworks

| Language | Files | Percentage |
|----------|-------|------------|
| {language} | {file_count} | {percentage}% |

| Framework | Version | Detection Source |
|-----------|---------|-----------------|
| {framework} | {version} | {source: package.json / requirements.txt / etc.} |

---

*Generated by attack-review skill*
````

### report.md フィールド説明

| フィールド | 説明 |
|-----------|------|
| `project_name` | プロジェクト名 |
| `datetime` | レビュー実行日時 `YYYY-MM-DD HH:MM:SS` |
| `mode` | 実行モード |
| `scope` | 対象スコープの説明 |
| `file_count` | 解析対象ファイル数 |
| `detected_languages` | 検出された言語（カンマ区切り） |
| `detected_frameworks` | 検出されたフレームワーク（カンマ区切り） |
| `overall_posture` | 総合リスク姿勢 |
| `executive_narrative` | エグゼクティブサマリーの本文（3-5 文） |
| `risk_level` | `critical` / `high` / `medium` / `low`（JSON スキーマ準拠、表示は先頭大文字でも可） |
| `likelihood` | `critical` / `high` / `medium` / `low`（JSON スキーマ準拠） |
| `impact` | `critical` / `high` / `medium` / `low`（JSON スキーマ準拠） |
| `attack_domain` | Appendix B の 6 ドメインのいずれか（Injection / AuthN/AuthZ / Client Attack / Data & Secrets / Infra & Supply Chain / Business Logic） |
| `cwe_id` | CWE 番号（例: `CWE-89`） |
| `cwe_name` | CWE 名称（例: `SQL Injection`） |
| `owasp_category` | OWASP Top 10 カテゴリ（例: `A03:2021 Injection`） |
| `effort_estimate` | 修正工数見積もり: `trivial` / `small` / `medium` / `large` |
| `owner_placeholder` | 担当者欄（レポート生成時は `TBD`） |

### report.md セクション表示ルール

- **Section 4 (Critical & High)**: 該当 finding がゼロの場合は「No Critical or High risk findings detected.」を表示
- **Section 5 (Medium & Low)**: 該当 finding がゼロの場合は「No Medium or Low risk findings detected.」を表示
- **Section 6 (Roadmap)**: 該当リスクレベルの finding がゼロの場合はそのサブセクション全体を省略
- **Finding の並び順**: 各セクション内でリスクレベル降順、同一レベル内は Impact 降順
- **Finding index**: セクション 4 と 5 で通し番号（セクション 4 が Finding 1-N、セクション 5 が Finding N+1-M）
- **PoC snippet**: 再現可能な最小コード。安全上の理由で weaponized exploit は含めない。概念実証レベルに留める
