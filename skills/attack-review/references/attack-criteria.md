# Attack Criteria

Index of the attack checklists referenced by attack-review agents. Each agent loads only its own criteria file (table below) and investigates the corresponding attack vectors.
All checks are performed from an **attacker's perspective**. The question is not "Is this defense sufficient?" but rather "How do I break through?"

## Risk Matrix

All findings are assessed using Likelihood x Impact.
**Vocabulary standardization**: Likelihood / Impact / Risk Level all use the 4-value scale `critical | high | medium | low` (aligned with the JSON output schema).

| | Impact: Low | Impact: Medium | Impact: High | Impact: Critical |
|---|---|---|---|---|
| **Likelihood: Critical** | Medium | High | Critical | Critical |
| **Likelihood: High**     | Low    | Medium | High     | Critical |
| **Likelihood: Medium**   | Low    | Medium | High     | High |
| **Likelihood: Low**      | Low    | Low    | Medium   | High |

- **Likelihood**: Discoverability + exploitability of the attack (can it be automated with tools, does it require authentication, can it be inferred from public information)
  - `critical`: trivially exploitable, automated tools detect it, no authentication needed
  - `high`: exploitable with moderate effort, publicly known technique
  - `medium`: requires specific conditions or insider knowledge
  - `low`: theoretical, requires significant effort or unusual conditions
- **Impact**: Severity of damage (RCE, data breach, privilege escalation, service disruption, financial loss)
  - `critical`: full system compromise, mass data breach, RCE
  - `high`: significant data leak, privilege escalation, account takeover
  - `medium`: limited data exposure, service disruption, single-user impact
  - `low`: information disclosure with minimal sensitivity, minor inconvenience

## Per-Agent Criteria Files

The check items live in one file per agent. Each agent loads only its own file — never this
whole set. This index carries the shared Risk Matrix and vocabulary above; do not duplicate
them into the per-agent files.

| Agent | Criteria file |
|---|---|
| 1. Injection Hunter (server) | [criteria-agent-1-injection.md](criteria-agent-1-injection.md) |
| 2. AuthN/AuthZ Breaker (both) | [criteria-agent-2-authn-authz.md](criteria-agent-2-authn-authz.md) |
| 3. Client Attack Specialist (client) | [criteria-agent-3-client-attack.md](criteria-agent-3-client-attack.md) |
| 4. Data & Secrets Exfiltrator (both) | [criteria-agent-4-data-secrets.md](criteria-agent-4-data-secrets.md) |
| 5. Infra & Supply Chain Exploiter (both) | [criteria-agent-5-infra-supply-chain.md](criteria-agent-5-infra-supply-chain.md) |
| 6. Business Logic Abuser (both) | [criteria-agent-6-business-logic.md](criteria-agent-6-business-logic.md) |
