# Verification Gate Shared Contract

The pre-completion verification contract shared by cycle / iterate / commit / test-driven-development.
It mechanically enforces "never claim completion without evidence".

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

Unless a verification command was run within the most recent message, completion must not be claimed.

## Gate Function

```
Before claiming completion or success:

1. IDENTIFY — which command proves this claim?
2. RUN     — run the command in full (new, fresh)
3. READ    — read the whole output; check the exit code and the failure count
4. VERIFY  — does the output back the claim?
   - NO  → report the actual state, with evidence
   - YES → make the claim, with evidence
5. CLAIM   — only now may the claim be made

Skipping any step = guessing, not verifying
```

## Forbidden expressions

The following must not be used before a verification command has been run:

- "should work" / "should pass" / 「通るはず」
- "probably" / "seems to" / 「おそらく」
- "Done!" / "Perfect!" / "Great!" / 「完了！」（before verification）
- "I'm confident" / 「自信がある」
- "looks correct" / 「正しそう」

## Verification pattern table

| Subject | Required evidence | Insufficient evidence |
|------|---------------|----------------|
| Tests | Test command output: 0 failures | A previous run's result, "it should pass" |
| Build | Build command: exit 0 | The linter passed |
| Linter | Linter output: 0 errors | A partial check, a guess |
| Bug fix | Retest of the original symptom: pass | The code changed, so it must be fixed |
| Requirement satisfaction | Line-by-line collation against the requirement list | The tests passed |
| Agent delegation | Confirm the actual changes in the VCS diff | Trusting the agent's success report |

## Preventing rationalization

| Excuse | Reality |
|--------|------|
| "It should pass by now" | Run the verification command |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "The linter passed" | Linter ≠ compiler ≠ tests |
| "The agent said it succeeded" | Verify independently |
| "I'm tired" | Fatigue is not a reason to skip |
| "A partial check is enough" | A partial check proves nothing |

## Integration guidance per skill

### Integration into cycle

- Inject it into the agent prompt of Phase 2 (Implement)
- Require a verification command run at the completion of each step
- Include the test-run output as evidence in the result file

### Integration into iterate

- Instruct the review agent of Phase 4 (Review) to apply the Gate Function
- Do not issue a PASS without evidence of a test run

### Integration into commit (best effort)

- **Attempt** to run the test suite before committing
- Run it only when a test framework could be detected
- On test failure: append a warning to the commit message body and continue committing
  - `⚠️ Tests failing: {failure_summary}`
- When the test framework is unknown: skip (commit immediately, as before)
- Honor commit's Core Principle "No confirmation" — do not block on test failure

### Integration into test-driven-development

- Apply the Gate Function in each of the RED / GREEN / REFACTOR phases
- The Bash output of the test run is the transition condition of each phase
