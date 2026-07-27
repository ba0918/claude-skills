# Friction Schema

The output JSON schema of collect.py, and the schema definition of friction-report.md.

## collect.py output JSON schema

```json
{
  "summary": {
    "project_filter": "string",
    "days": "integer",
    "sessions_found": "integer",
    "total_skill_invocations": "integer",
    "unique_skills_used": ["string"],
    "collection_timestamp": "ISO 8601 string"
  },
  "sessions": [
    {
      "file": "string (filepath)",
      "session_start": "ISO 8601 string | null",
      "session_end": "ISO 8601 string | null",
      "total_turns": "integer",
      "skill_count": "integer"
    }
  ],
  "skill_invocations": [
    {
      "skill": "string",
      "turn": "integer",
      "timestamp": "ISO 8601 string (optional)"
    }
  ],
  "friction_signals": {
    "{skill_name}": {
      "retry_count": "integer — consecutive invocations of the same skill",
      "correction_turns": "integer — correction-instruction turns after the skill ran",
      "session_abandoned_count": "integer — session abandonments",
      "tool_error_count": "integer — tool execution errors",
      "total_turns_to_completion": "integer — total turns until the skill completed",
      "invocation_count": "integer — invocations"
    }
  },
  "secret_warnings": [
    {
      "type": "string (aws_key | private_key | jwt | prefix_token | email | home_path | generic_secret | generic_long_key)",
      "masked": "string — always the full mask [REDACTED:kind] (no partial disclosure)"
    }
  ]
}
```

**masked format**: the full mask `[REDACTED:{type}]` (the old partial disclosure of first4+last4 is gone). Because masked is an opaque string, the friction-schema contract still holds. secret_warnings of the same type are collapsed into one entry by the dedup key `{type}:{masked}`. `prefix_token` detects the known prefix tokens (ghp_ / github_pat_ / xoxb- / sk- / sk-ant- / AIza) whether or not they are quoted.

## --capture-prompts output schema (opt-in / for trigger-eval)

A JSONL generated only when `--capture-prompts` is given. 1 line = 1 record. Because it contains message bodies, `--output` is mechanically restricted (fail-closed) to a path under `cwd/.agents/tmp` that is also git-ignored.

```json
{"ts": "ISO 8601 string | null", "project": "string", "user_text_masked": "string — mask_secrets applied", "fired_skill": "string (bare skill name) | null", "signals": ["string — slash_fired / correction_after_skill, etc."]}
```

## friction-report.md schema

friction-report.md is a Markdown document containing the following sections.

**Important: it must never contain raw text (the original text of session content). Only figures, classifications, and scores are allowed.**

```markdown
# Friction Report: {project}

**Generated:** {ISO 8601 timestamp}
**Period:** {days} days
**Sessions:** {count}

## Executive Summary
{a 1-3 line quantitative summary. No raw text}

## Skill Rankings (by friction score)
| Rank | Skill | Friction Score | Invocations | Top Issue | Recommendation |
|------|-------|---------------|-------------|-----------|---------------|

## Detailed Findings

### {skill_name}
- **Friction Score:** {a number from 0 to 10}
- **Invocations:** {count}
- **Retry Rate:** {retry_count / invocation_count}
- **Correction Rate:** {correction_turns / invocation_count}
- **Abandonment Rate:** {session_abandoned_count / invocation_count}
- **Error Rate:** {tool_error_count / total_turns}
- **Issues:**
  - {issue_description — quantitative statements only}
- **Recommendations:**
  - {recommendation}

## Improvement Hypotheses

### Hypothesis {A/B/C}: {title}
- **Target:** {skill_name}
- **Change:** {description of the change}
- **Expected Impact:** {the expected effect, quantified}
- **Size:** Small / Large
- **Confidence:** High / Medium / Low
```

## Forbidden fields

The following **must never** be included in friction-report.md:

- the original text of user messages
- the original text of assistant responses
- session IDs
- personal information other than the username contained in file paths
- secrets (never include them in friction-report even when masked)
