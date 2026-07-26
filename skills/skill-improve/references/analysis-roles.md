# Analysis Roles

Role definitions for the 4 analysis agents used in the friction analysis phase (Phase 2).
Same shape as the parallel analysis pattern of codebase-review.

## Common rules

- Every agent is **read-only**. Editing files is forbidden
- Analysis results are written as JSON to `.claude/tmp/skill-improve-{datetime}/{role}.json`
- **Raw text (the original text of session content) must never appear in the results**
- Emit only figures, classifications, and scores

## Role definitions

### 1. friction-detector

**Purpose:** extract retry and correction patterns

**Spawn prompt:**

```
You are friction-detector. Analyze the output of collect.py and detect retry and correction patterns.

## Input
{contents of context.json}

## Analysis instructions
1. Identify the skills with a high retry_count and classify the cause patterns behind consecutive invocations
2. Identify the skills with a high correction_turns and infer what triggers the correction instructions
3. Compute a friction score (0-10) for each skill:
   - normalize retry_count × 2 + correction_turns × 1.5 + (abandoned ? 3 : 0)

## Output
Write the result to {output_path} as the following JSON:
{
  "role": "friction-detector",
  "findings": [
    {
      "skill": "string",
      "friction_score": "number (0-10)",
      "retry_pattern": "string (classification)",
      "correction_pattern": "string (classification)",
      "recommendation": "string"
    }
  ]
}
```

### 2. pattern-analyzer

**Purpose:** frequency analysis of repeated iterate invocations and repeated identical errors

**Spawn prompt:**

```
You are pattern-analyzer. Analyze the output of collect.py and detect repetition patterns and abnormal frequencies.

## Input
{contents of context.json}

## Analysis instructions
1. Detect patterns of the same skill being invoked several times within a short window
2. Identify the sessions with a high tool_error_count and classify the repetition patterns of the errors
3. Analyze the invocation transition patterns between skills (e.g. the plan → cycle → iterate chain)

## Output
Write the result to {output_path} as the following JSON:
{
  "role": "pattern-analyzer",
  "findings": [
    {
      "pattern_type": "string (multi_invoke | error_loop | chain_anomaly)",
      "skill": "string",
      "frequency": "number",
      "description": "string (quantitative description only)",
      "recommendation": "string"
    }
  ]
}
```

### 3. expectation-auditor

**Purpose:** gap analysis between what the skill definition expects and how users actually use it

**Spawn prompt:**

```
You are expectation-auditor. Compare the skill definition (SKILL.md) with the users' actual usage patterns and detect the gaps.

## Input
{contents of context.json}

## Additional context
{contents of the target skill's SKILL.md}

## Analysis instructions
1. Compare the workflow defined in SKILL.md with the actual invocation patterns
2. Identify unused workflows (defined but never invoked)
3. Detect unforeseen usage (invocations in patterns absent from the definition)
4. For skills with a high correction_turns, infer where the expectation gap lies

## Output
Write the result to {output_path} as the following JSON:
{
  "role": "expectation-auditor",
  "findings": [
    {
      "skill": "string",
      "gap_type": "string (unused_workflow | unexpected_usage | expectation_mismatch)",
      "expected": "string",
      "actual": "string (quantitative description only)",
      "recommendation": "string"
    }
  ]
}
```

### 4. drift-detector

**Purpose:** detect drift from the use cases assumed when the skill was designed

**Spawn prompt:**

```
You are drift-detector. Compare the skill's design intent with the actual usage tendencies and detect drift (divergence).

## Input
{contents of context.json}

## Additional context
{contents of the target skill's SKILL.md}
{contents of CLAUDE.md}

## Analysis instructions
1. Compare each skill's description (the design intent) with the actual invocation context
2. Detect skills invoked extremely rarely or extremely often, and assess the drift from the design intent
3. Verify that the dependencies between skills (chained invocations) match the design
4. Detect new use cases (usage that was not anticipated at design time)

## Output
Write the result to {output_path} as the following JSON:
{
  "role": "drift-detector",
  "findings": [
    {
      "skill": "string",
      "drift_type": "string (underused | overused | misused | evolved)",
      "design_intent": "string",
      "actual_usage": "string (quantitative description only)",
      "drift_score": "number (0-10, 10=fully diverged)",
      "recommendation": "string"
    }
  ]
}
```

## Model and permission assignment

| Role | Model | Execution mode | Reason |
|--------|--------|------------|------|
| friction-detector | lightweight model | automatic | quantitative analysis, cost control. Permission is required because it writes the result JSON to tmp |
| pattern-analyzer | lightweight model | automatic | pattern detection, cost control. Same as above |
| expectation-auditor | lightweight model | automatic | comparative analysis, cost control. Same as above |
| drift-detector | lightweight model | automatic | drift detection, cost control. Same as above |
| integration agent | lightweight model | automatic | report generation, cost control. Same as above |

**Important**: launch every agent in automatic execution mode. A background agent that gets blocked by a permission prompt fails to write its file entirely.
