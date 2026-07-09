# Review Dimensions - Plan Reviewer

Detailed checklists and scoring criteria for 7 review dimensions.
Language and framework agnostic. Add project-specific perspectives via `.claude/review-rules.md`.

## Scoring Guide (applies to every dimension)

Each dimension emits a `confidence` score in 0–100. The **score = severity of the most
severe issue found** within that dimension, capped by the number and breadth of issues.
The three verdict ranges (PASS / WARN / BLOCK) map to concrete anchors so reviewers
don't have to guess.

| Score anchor | Inside a range | Meaning |
|---|---|---|
| **90–100** | BLOCK, ceiling | At least one critical issue that makes the plan unsafe to implement as-is (exploit, data loss, clearly unrunnable, missing test plan entirely). |
| **80–89** | BLOCK, floor | One critical issue **or** two important issues stacking. Still must-fix. |
| **65–79** | WARN, ceiling | One important issue **or** multiple minor issues pointing to the same weakness. Recommend fix but not blocking. |
| **50–64** | WARN, floor | Room for improvement visible (one important issue, or a cluster of minors). |
| **25–49** | PASS, ceiling | Only minor / cosmetic issues, plan is sound. |
| **0–24** | PASS, floor | No issues found; this dimension is exemplary. |

Rules:

1. Pick the anchor for the **single most severe issue**, then adjust **within that band only**
   based on how many other issues of similar or lower severity also apply.
2. Never jump anchors based on count alone — 5 minor issues do NOT aggregate into a BLOCK.
   Escalation requires a qualifying single issue at the higher severity.
3. `severity` in individual issues uses: `critical` = BLOCK anchor, `important` = WARN anchor,
   `minor` = PASS anchor. The dimension score must be consistent with its issues' severities.
4. If a dimension has zero issues, its score must be ≤ 24 (PASS floor). Do not assign
   a PASS-ceiling score just to look conservative — that obscures which dimensions were
   actually clean.

## Table of Contents

1. [Feasibility](#1-feasibility)
2. [Security](#2-security)
3. [Performance & Memory](#3-performance--memory)
4. [Architecture & Design](#4-architecture--design)
5. [Completeness](#5-completeness)
6. [Alternatives](#6-alternatives)
7. [UI/UX](#7-uiux)

---

## 1. Feasibility

Whether the plan is technically feasible and can be implemented at a reasonable cost.

### Checklist

- [ ] Affected files exist and specified line numbers are correct (verify against actual code)
- [ ] APIs/libraries used actually exist and have the interfaces described in the plan
- [ ] Implementation environment constraints (runtime limitations, platform compatibility, etc.) are satisfied
- [ ] Effort estimates are reasonable (no significant over/under-estimation)
- [ ] Dependencies can be implemented in the correct order
- [ ] Impact on existing tests has been considered

### Confidence Score Criteria

| Score | Condition |
|-------|-----------|
| 80-100 | Use of non-existent APIs, impossible implementation methods, critical environment constraint oversight |
| 50-79 | Line number discrepancies, significant effort estimate deviation, unclear implementation steps |
| 0-49 | Minor issues only, feasible |

---

## 2. Security

Security risks including input validation, sensitive data protection, and injection attacks.

### Checklist

- [ ] All external inputs (user input, network, files) are validated and sanitized
- [ ] Sensitive data (credentials, tokens, keys, etc.) is handled securely (no logging, no plaintext storage)
- [ ] Defense against injection attacks (SQL, command, path, etc.) is present
- [ ] Redirect/SSRF risks are considered when accessing external resources
- [ ] Error messages do not leak internal system information
- [ ] Data flows crossing trust boundaries are secure

### Confidence Score Criteria

| Score | Condition |
|-------|-----------|
| 80-100 | Unvalidated external input passed to dangerous operations, sensitive data exposure |
| 50-79 | Validation exists but is incomplete, insufficient testing of new input paths |
| 0-49 | Security measures are appropriate |

---

## 3. Performance & Memory

Efficient use of CPU/memory and scalability.

### Checklist

- [ ] No O(n^2)+ algorithms used on large datasets
- [ ] No resource leaks (unclosed file handles, unremoved listeners, uncleared timers, etc.)
- [ ] No unnecessary copies or allocations (string concatenation in loops, unnecessary deep copies, etc.)
- [ ] Memory retention duration for large data is minimized
- [ ] Appropriate use of async processing (no unnecessary serialization, unused parallelization opportunities)
- [ ] No duplicate computation/I/O/processing
- [ ] Runtime-specific resource constraints (thread count, memory limits, etc.) are considered

### Confidence Score Criteria

| Score | Condition |
|-------|-----------|
| 80-100 | Certain resource leak, O(n^2) processing large data, memory exhaustion risk |
| 50-79 | Inefficient but functional, room for improvement |
| 0-49 | Efficient implementation |

---

## 4. Architecture & Design

Conformance with project architecture principles and design guidelines.

### Checklist

**Project-specific (read from CLAUDE.md / .claude/review-rules.md):**
- [ ] No violations of layer structure defined in CLAUDE.md
- [ ] No violations of dependency direction rules defined in CLAUDE.md
- [ ] No violations of project-specific design rules defined in `.claude/review-rules.md`

**General:**
- [ ] DRY principle: No code duplicated 2+ times
- [ ] Single responsibility: No file/function with multiple responsibilities
- [ ] Type safety: Appropriate type definitions, no loose type usage
- [ ] Error handling: Proper propagation and recovery

### Confidence Score Criteria

| Score | Condition |
|-------|-----------|
| 80-100 | Layer violation as defined by project, forbidden dependency direction |
| 50-79 | DRY violation, improper separation of concerns, insufficient type safety |
| 0-49 | Architecture compliant |

---

## 5. Completeness

Whether all necessary items are included in the plan.

### Checklist

- [ ] Error handling: Appropriate fallbacks for all failure paths
- [ ] Edge cases: Empty input, large input, invalid input, Unicode, multibyte characters
- [ ] Backward compatibility: Compatibility with existing config/data/APIs is maintained
- [ ] Test plan: Tests are planned for each change
- [ ] Rollback capability: Can be safely reverted if issues arise
- [ ] Resource cleanup: Release of acquired resources is guaranteed
- [ ] Documentation updates: Config files, APIs, architecture docs, etc. need updating

### Confidence Score Criteria

| Score | Condition |
|-------|-----------|
| 80-100 | No test plan, critical edge case oversight, missing error handling |
| 50-79 | Some edge case gaps, documentation update gaps |
| 0-49 | Sufficiently comprehensive |

---

## 6. Alternatives

Whether better alternative approaches exist compared to the proposed implementation.

### Checklist

- [ ] Is there a simpler way to achieve the same goal?
- [ ] Can standard library alternatives be used (avoid reinventing the wheel)?
- [ ] Can existing libraries/utilities be leveraged?
- [ ] Is the design future-extensible?
- [ ] Is the performance vs. code complexity tradeoff reasonable?

### Confidence Score Criteria

| Score | Condition |
|-------|-----------|
| 80-100 | Planning a complex implementation when standard library can solve it concisely |
| 50-79 | A better approach exists, but the planned approach would also work |
| 0-49 | Optimal approach |

---

## 7. UI/UX

User-facing output quality, interaction flow design, and information architecture.
This dimension is triggered conditionally — only when the plan involves changes to user-facing output or interaction patterns.

### Checklist

- [ ] Error messages are actionable: include what happened, why, and how to fix it
- [ ] Progress feedback is provided for operations taking > 5 seconds
- [ ] User-facing choice prompts follow Hick's Law: ≤ 4 options, clear labels, sensible defaults
- [ ] Output format is consistent with existing skills (terminology, indentation, section headers)
- [ ] Cancel/abort paths are designed and tested (not just happy path)
- [ ] Information hierarchy follows "summary first, details on demand" pattern
- [ ] Long output uses visual grouping (headers, separators, blank lines) for scannability
- [ ] No jargon leak: user-facing text avoids internal implementation terms

### Confidence Score Criteria

| Score | Condition |
|-------|-----------|
| 80-100 | No error recovery guidance, missing progress feedback for long operations, cancel path undesigned |
| 50-79 | Inconsistent output format, excessive cognitive load, suboptimal option design |
| 0-49 | Good user experience design |
