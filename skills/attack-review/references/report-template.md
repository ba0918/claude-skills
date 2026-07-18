# Report Template

Report template referenced by the attack-review integration agent.
`{variable_name}` placeholders are replaced by the integration agent with values obtained from each attack agent's JSON output.

---

## summary.txt Template

ASCII art summary displayed in the console. The integration agent generates `summary.txt` following this format.

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

### summary.txt Field Descriptions

| Field | Description |
|-------|-------------|
| `project_name` | Project name (repository name or directory name) |
| `datetime` | Review execution datetime `YYYY-MM-DD HH:MM:SS` |
| `mode` | Execution mode: one of `full` / `server` / `client` |
| `detected_languages` | Detected languages and frameworks (comma-separated) |
| `overall_posture` | Overall risk posture: `Critical Risk` / `High Risk` / `Moderate Risk` / `Low Risk` / `Minimal Risk` |
| `critical_count` / `high_count` / `medium_count` / `low_count` | Finding count per risk level |
| `risk_level` | Individual finding risk level: `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` |
| `report_path` | Absolute path of the generated report.md |

### summary.txt Display Rules

- **Top 5 Attack Scenarios**: If fewer than 5 findings exist, display only the available ones
- **Top 5 sort order**: Risk level descending (Critical > High > Medium > Low); within the same level, Likelihood descending (higher first)
- **Codex Perspective**: If the Codex agent JSON is available, display the top 3 findings; if unavailable, display a warning message
- **overall_posture determination**: Based on the highest severity among detected findings. 1+ Critical → `Critical Risk`, 1+ High → `High Risk`, Medium only → `Moderate Risk`, Low only → `Low Risk`, zero findings → `Minimal Risk`
- **Risk distribution table**: Display `0` when a domain has zero findings (do not omit the row)

---

## report.md Template

Full attack review report saved to `.agents/artifacts/reviews/` (Git-ignored local store). The integration agent generates `report.md` following this format.

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

> **Mode-specific rows**: In `server` mode, display the Agent 3 (Client Attack) row as `N/A — skipped in server mode`. In `client` mode, display Agent 1 (Injection) as `N/A — skipped in client mode`. For agents that did not complete (graceful degradation), display `N/A — agent did not complete`.

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

### report.md Field Descriptions

| Field | Description |
|-------|-------------|
| `project_name` | Project name |
| `datetime` | Review execution datetime `YYYY-MM-DD HH:MM:SS` |
| `mode` | Execution mode |
| `scope` | Description of the target scope |
| `file_count` | Number of files analyzed |
| `detected_languages` | Detected languages (comma-separated) |
| `detected_frameworks` | Detected frameworks (comma-separated) |
| `overall_posture` | Overall risk posture |
| `executive_narrative` | Executive summary body text (3-5 sentences) |
| `risk_level` | `critical` / `high` / `medium` / `low` (per JSON schema; title-case display is acceptable) |
| `likelihood` | `critical` / `high` / `medium` / `low` (per JSON schema) |
| `impact` | `critical` / `high` / `medium` / `low` (per JSON schema) |
| `attack_domain` | One of the 6 domains from Appendix B (Injection / AuthN/AuthZ / Client Attack / Data & Secrets / Infra & Supply Chain / Business Logic) |
| `cwe_id` | CWE number (e.g., `CWE-89`) |
| `cwe_name` | CWE name (e.g., `SQL Injection`) |
| `owasp_category` | OWASP Top 10 category (e.g., `A03:2021 Injection`) |
| `effort_estimate` | Fix effort estimate: `trivial` / `small` / `medium` / `large` |
| `owner_placeholder` | Owner field (set to `TBD` at report generation time) |

### report.md Section Display Rules

- **Section 4 (Critical & High)**: If zero findings, display "No Critical or High risk findings detected."
- **Section 5 (Medium & Low)**: If zero findings, display "No Medium or Low risk findings detected."
- **Section 6 (Codex)**: If Codex agent JSON is unavailable, display the warning block
- **Section 7 (Roadmap)**: If zero findings exist at a given risk level, omit that subsection entirely
- **Finding sort order**: Within each section, sort by risk level descending; within the same level, sort by Impact descending
- **Finding index**: Sequential numbering across Sections 4 and 5 (Section 4: Finding 1-N, Section 5: Finding N+1-M)
- **PoC snippet**: Minimal reproducible code. Do not include weaponized exploits for safety reasons. Keep at proof-of-concept level
