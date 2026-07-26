# Positioning and Architecture

## Positioning

| Layer | Skill | Question |
|---|---|---|
| Selection layer | trigger-eval | Does it fire correctly? (dynamic measurement) |
| **Contract layer** | **skill-interface-audit** | **Is it complete as a specification? (static)** |
| Execution layer | empirical-prompt-tuning | Is the execution quality high? (dynamic) |
| Regression layer | skill-regression | Does the behavior hold after a change? (fixtures) |
| Operations layer | skill-improve | Is there friction in real use? (log measurement) |

**The boundary with context-audit is cut exclusively by the target file set**:
- context-audit → resident instructions (CLAUDE.md / AGENTS.md / rules / memory)
- skill-interface-audit → the skills themselves (skills/\*/SKILL.md + references/)

**Relation to validate\_repo.py**: frontmatter, description trigger words, link existence, and shared contract
vocabulary are already enforced in CI, so they are not duplicated here. Conversely, a rule proven to be stably
machine-decidable in the audit is promoted into validate\_repo.py and put into CI (the exit strategy).

## Architecture: the hybrid model

Following the CA-\* pattern of context-audit, this takes a hybrid model: **deterministic verdicts by pure functions, the LLM for semantic judgment only**.
It is not "purely static" — the LLM handles the contract-completeness judgments of SI-C\*, and they all stay REPORT\_ONLY.

| Phase | Verdict by | Target rules | fix action ceiling |
|---------|---------|-----------|----------------|
| Phase 1 | pure functions (script) | SI-S\* | NEEDS\_JUDGMENT |
| Phase 2 | LLM | SI-C\* | NEEDS\_JUDGMENT (the finding itself is REPORT\_ONLY; only the patch-application decision is NEEDS\_JUDGMENT) |
