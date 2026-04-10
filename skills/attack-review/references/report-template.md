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
│  Injection & Input       │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
│  Auth & Session          │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
│  Data Exposure           │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
│  Access Control          │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
│  Crypto & Secrets        │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
│  Config & Deployment     │    {n}   │  {n} │  {n}  │  {n}  │  {n}   │
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

┌──────────────────────────────────────────────────────────────────────┐
│  CODEX PERSPECTIVE                                                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  {If codex available:}                                               │
│  1. [{risk_level}] {finding_title}                                   │
│     {description_one_liner}                                          │
│                                                                      │
│  2. [{risk_level}] {finding_title}                                   │
│     {description_one_liner}                                          │
│                                                                      │
│  3. [{risk_level}] {finding_title}                                   │
│     {description_one_liner}                                          │
│                                                                      │
│  {If codex NOT available:}                                           │
│  [!] Codex second opinion was not available for this review.         │
│      Results are based on the core attack agents only.               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

  Full report: {report_path}
```

### summary.txt フィールド説明

| フィールド | 説明 |
|-----------|------|
| `project_name` | プロジェクト名（リポジトリ名またはディレクトリ名） |
| `datetime` | レビュー実行日時 `YYYY-MM-DD HH:MM:SS` |
| `mode` | 実行モード（`full` / `quick` / `targeted:{path}` 等） |
| `detected_languages` | 検出された言語・フレームワーク（カンマ区切り） |
| `overall_posture` | 総合リスク姿勢: `Critical Risk` / `High Risk` / `Moderate Risk` / `Low Risk` / `Minimal Risk` |
| `critical_count` / `high_count` / `medium_count` / `low_count` | 各リスクレベルの検出数 |
| `risk_level` | 個別 finding のリスクレベル: `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` |
| `report_path` | 生成された report.md の絶対パス |

### summary.txt 表示ルール

- **Top 5 Attack Scenarios**: finding が 5 件未満の場合は存在する分だけ表示する
- **Top 5 の並び順**: リスクレベル降順（Critical > High > Medium > Low）、同一レベル内は Impact 降順
- **Codex Perspective**: Codex エージェントの JSON が利用可能な場合は上位 3 件を表示、利用不可の場合は警告メッセージを表示
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
| Injection & Input Validation | {n} | {n} | {n} | {n} | {n} |
| Authentication & Session Management | {n} | {n} | {n} | {n} | {n} |
| Sensitive Data Exposure | {n} | {n} | {n} | {n} | {n} |
| Access Control & Authorization | {n} | {n} | {n} | {n} | {n} |
| Cryptography & Secrets Management | {n} | {n} | {n} | {n} | {n} |
| Configuration & Deployment | {n} | {n} | {n} | {n} | {n} |
| **TOTAL** | **{n}** | **{n}** | **{n}** | **{n}** | **{n}** |

---

## 3. Risk Matrix Legend

Findings are categorized using a **Likelihood x Impact** risk matrix:

|                  | Impact: Low | Impact: Medium | Impact: High | Impact: Critical |
|------------------|-------------|----------------|--------------|------------------|
| **Likelihood: High**   | Medium | High     | Critical | Critical |
| **Likelihood: Medium** | Low    | Medium   | High     | Critical |
| **Likelihood: Low**    | Low    | Low      | Medium   | High     |

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

## 6. Codex Perspective

{If codex agent JSON was available:}

### Cross-cutting Observations

{codex_narrative}

> Codex agent's independent assessment of systemic security patterns,
> architectural weaknesses, and cross-cutting concerns that individual
> attack domain agents may miss.

### Codex Findings

#### {index}. [{risk_level}] {finding_title}

- **Attack Domain**: {attack_domain}
- **Affected Files**: {file_list}
- **Observation**: {observation}
- **Recommendation**: {recommendation}

{Repeat for each Codex finding}

{If codex agent JSON was NOT available:}

> **Warning**: Codex second opinion was not available for this review. The report is based on the core attack agents only. Re-run with Codex enabled for additional cross-cutting analysis.

---

## 7. Remediation Roadmap

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

## 8. Appendix

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

| Domain | Coverage |
|--------|----------|
| Injection & Input Validation | SQL injection, XSS, command injection, path traversal, template injection, SSRF, deserialization, prototype pollution |
| Authentication & Session Management | Broken authentication, session fixation, credential stuffing, JWT weaknesses, OAuth misconfigurations, MFA bypass |
| Sensitive Data Exposure | Hardcoded secrets, PII leakage, insufficient encryption at rest/transit, verbose error messages, log injection of secrets |
| Access Control & Authorization | IDOR, privilege escalation, missing function-level access control, CORS misconfiguration, forced browsing |
| Cryptography & Secrets Management | Weak algorithms, insufficient key length, improper random generation, missing integrity checks, insecure key storage |
| Configuration & Deployment | Debug mode in production, default credentials, missing security headers, insecure dependency versions, open admin interfaces |

### C. Analyzed Files

{List of analyzed file paths, one per line}

### D. Agent Completion Status

| Agent | Status | Findings | Duration |
|-------|--------|----------|----------|
| {agent_name} | {completed / failed / timeout} | {finding_count} | {duration_seconds}s |
| {agent_name} | {completed / failed / timeout} | {finding_count} | {duration_seconds}s |
| {agent_name} | {completed / failed / timeout} | {finding_count} | {duration_seconds}s |
| Codex | {completed / skipped / failed} | {finding_count} | {duration_seconds}s |

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
| `risk_level` | `Critical` / `High` / `Medium` / `Low` |
| `likelihood` | `High` / `Medium` / `Low` |
| `impact` | `Critical` / `High` / `Medium` / `Low` |
| `attack_domain` | 6 ドメインのいずれか |
| `cwe_id` | CWE 番号（例: `CWE-89`） |
| `cwe_name` | CWE 名称（例: `SQL Injection`） |
| `owasp_category` | OWASP Top 10 カテゴリ（例: `A03:2021 Injection`） |
| `effort_estimate` | 修正工数見積もり: `trivial` / `small` / `medium` / `large` |
| `owner_placeholder` | 担当者欄（レポート生成時は `TBD`） |

### report.md セクション表示ルール

- **Section 4 (Critical & High)**: 該当 finding がゼロの場合は「No Critical or High risk findings detected.」を表示
- **Section 5 (Medium & Low)**: 該当 finding がゼロの場合は「No Medium or Low risk findings detected.」を表示
- **Section 6 (Codex)**: Codex エージェント JSON が利用不可の場合は警告ブロックを表示
- **Section 7 (Roadmap)**: 該当リスクレベルの finding がゼロの場合はそのサブセクション全体を省略
- **Finding の並び順**: 各セクション内でリスクレベル降順、同一レベル内は Impact 降順
- **Finding index**: セクション 4 と 5 で通し番号（セクション 4 が Finding 1-N、セクション 5 が Finding N+1-M）
- **PoC snippet**: 再現可能な最小コード。安全上の理由で weaponized exploit は含めない。概念実証レベルに留める
