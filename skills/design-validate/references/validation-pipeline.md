# Validation Pipeline

The specification of the multi-stage validation pipeline the design-validate skill runs.

## Pipeline overview

```
Stage 1: Baseline Check
  └── confirm approval.json exists + verify the hashes

Stage 2: Static Lint (mechanical)
  └── run design-lint → compute the scores for R001, R002, R003

Stage 3: Visual Regression (visual)
  └── Playwright screenshot comparison → compute the scores for R004, R007

Stage 4: Rubric Judge (llm-judge)
  └── launch an independent judge subagent → compute the scores for R005, R006

Stage 5: Aggregation
  └── weighted average → verdict + evidence output
```

## Stage 1: Baseline Check

### Checking the preconditions

1. Does `.design/baseline/approval.json` exist?
   - If not, warn with 「Baseline が確定していません。先に Base Design の承認が必要です」
   - Show the path to design-scaffold's approval flow
2. Verifying `tokensHash` / `catalogHash`
   - Compute the SHA-256 hash of tokens.json and compare it with `tokensHash` in approval.json
   - Compute the SHA-256 hash of component-catalog.json and compare it with `catalogHash`
   - On a mismatch:
     ```
     ⚠️ Baseline と現在の定義ファイルが不一致です。
     tokens.json: {match/mismatch}
     catalog.json: {match/mismatch}
     
     再承認が必要です。`/claude-skills:design-scaffold` で Base Design を更新してください。
     ```

### Behavior when the baseline is not established

Even without a baseline, Stage 2 (lint) can run.
Stage 3 (visual) and Stage 4 (rubric) require the baseline and are skipped.

## Stage 2: Static Lint

### How it runs

Run the same logic as the design-lint skill internally.

1. Read `.design/tokens.json`
2. Read `.design/lint-config.json`
3. Read `.design/component-catalog.json` (when it exists)
4. Scan every target file and apply DL001-204
5. Map the results onto the rubric items:

| Rubric ID | Lint rules | Computation |
|-----------|-----------|---------|
| R001 (Token Compliance) | DL001-006 | violations=0 → 100, >0 → 0 (binary) |
| R002 (Component Compliance) | DL101-103 | violations=0 → 100, >0 → 0 (binary) |
| R003 (Layout Compliance) | DL201-204 | violations=0 → 100, >0 → 0 (binary) |

### Short-circuit evaluation

If any of R001, R002, R003 FAILs:
- Do not run Stages 3 and 4 (a visual test of code that fails lint is meaningless)
- Emit the FAIL report immediately
- Present the list of violations to fix

## Stage 3: Visual Regression

### Preconditions

- Baseline screenshots exist under `.design/baseline/screenshots/`
- Playwright is installed (check with `npx playwright --version`)
- Storybook can be built (`npx storybook build` succeeds)

### How it runs

1. Build Storybook: `npx storybook build --output-dir storybook-static`
2. Take screenshots with Playwright and compare them against the baseline
3. Decide whether the difference is at or below `maxDiffPixelRatio`

### Result mapping

| Rubric ID | Target | Computation |
|-----------|------|---------|
| R004 (Visual Consistency) | components | the mean diff over all components ≤ the threshold → pass |
| R007 (Responsive Behavior) | each breakpoint | diff ≤ the threshold at every breakpoint → pass |

### When Storybook / Playwright are not installed

Skip when the framework-dependent setup is incomplete:
- Explain 「Visual test をスキップしました。Storybook + Playwright をセットアップすると visual regression test が有効になります」
- Treat R004 and R007 as N/A and redistribute their weight

## Stage 4: Rubric Judge (LLM)

### The independence principle

Evaluate with **a different instance** from the LLM that generated the code (to prevent self-scoring).
Inside design-validate, launch a dedicated judge agent as a **subagent**.

### Launching the judge

```
Agent({
  description: "Design Rubric Judge",
  prompt: `
    You are an independent examiner of design system compliance.
    Evaluate the screenshots below against the design system in DESIGN.md.
    
    ## Evaluation criteria
    
    ### R005: Visual Harmony (overall harmony)
    - pass: color, font, and spacing are consistent, with no visual noise
    - partial: broadly consistent, but with 1-2 inconsistent spots
    - fail: there is obvious inconsistency or visual discomfort
    
    ### R006: Interaction Coherence
    - pass: hover/focus/active states are consistent across every component
    - partial: broadly consistent, but inconsistent on some components
    - fail: the interaction patterns are inconsistent between components
    
    ## Input
    - screenshots: {screenshots}
    - the Do's/Don'ts of DESIGN.md: {dos_donts}
    
    ## Output format
    Answer for each item in the following JSON:
    {
      "R005": { "score": "pass|partial|fail", "reason": "state the grounds in one sentence" },
      "R006": { "score": "pass|partial|fail", "reason": "state the grounds in one sentence" }
    }
  `
})
```

### Score conversion

| Judge verdict | Numeric score |
|-----------|----------|
| pass | 100 |
| partial | 50 |
| fail | 0 |

## Stage 5: Aggregation

### Computing the weighted average

```
totalScore = Σ (criterion.weight × criterion.score) / Σ (active_weights)

* N/A items are excluded from the weights and the rest renormalized
```

### Default rubric items

| ID | Name | Verification | Weight | Scoring |
|----|------|---------|--------|---------|
| R001 | Token Compliance | mechanical | 0.25 | binary |
| R002 | Component Compliance | mechanical | 0.20 | binary |
| R003 | Layout Compliance | mechanical | 0.15 | binary |
| R004 | Visual Consistency | visual | 0.15 | scale-5 |
| R005 | Visual Harmony | llm-judge | 0.10 | scale-5 |
| R006 | Interaction Coherence | llm-judge | 0.08 | scale-5 |
| R007 | Responsive Behavior | visual | 0.07 | binary |

**Weight ratio:** mechanical (60%) > visual (22%) > llm-judge (18%)

### The verdict

```
if totalScore >= rubric.passingScore:
  verdict = "PASS"
else:
  verdict = "FAIL"
```

Default `passingScore`: 80

### Evidence output

```json
{
  "timestamp": "2026-04-14T20:00:00Z",
  "pipeline": "design-validate",
  "tokensVersion": "1.0.0",
  "baselineApproved": "2026-04-14T19:30:00Z",
  "scores": {
    "R001": { "score": 100, "verification": "mechanical", "details": "0 violations" },
    "R002": { "score": 100, "verification": "mechanical", "details": "0 violations" },
    "R003": { "score": 100, "verification": "mechanical", "details": "0 violations" },
    "R004": { "score": 95, "verification": "visual", "details": "avg diff: 0.3%" },
    "R005": { "score": 100, "verification": "llm-judge", "details": "pass: color and spacing are consistent" },
    "R006": { "score": 50, "verification": "llm-judge", "details": "partial: the ghost button hover is inconsistent" },
    "R007": { "score": 100, "verification": "visual", "details": "pass at every breakpoint" }
  },
  "totalScore": 93.5,
  "passingScore": 80,
  "verdict": "PASS"
}
```

### Saving the evidence

Save it to `.design/validate-report.json`. Conforms to the verification-gate contract.
