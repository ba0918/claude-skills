---
name: systematic-debugging
description: 4フェーズ構造化デバッグスキル。根本原因を特定してから修正する。investigate（調査のみ）の補完として修正まで実行する。「debug」「デバッグ」「バグ修正」「なぜ壊れる」で起動。
---

# Systematic Debugging

A four-phase structured debugging skill. It blocks random fixes and makes identifying the root cause mandatory.

### Differentiation from Other Skills

- **vs investigate**: investigate is a read-only investigation. This skill performs the investigation *and* the fix. It accepts investigate's output as input
- **vs cycle / iterate**: cycle and iterate are plan-based implementation. This skill specializes in the structured resolution of bugs and problems

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

You may not propose a fix until Phase 1 is complete.

## Phase 1: Root Cause Investigation

**Propose no fix whatsoever. Investigation only.**

### Accepting investigate's Output as Input

When `$ARGUMENTS` contains the path to an investigate skill output file, read that report and use it as context. It lets you skip part of Phase 1.

### Step 1.1: Read the Error Message Closely

1. Read the error message and the stack trace **in full** (do not skip any of it)
2. Record the line numbers, file paths, and error codes
3. Do not ignore warning messages either

### Step 1.2: Reproduce

1. Confirm that you can reliably reproduce the bug
   - Run the test or the failing command in the shell
2. Record the reproduction steps
3. Cannot reproduce it → collect more data (do not guess)

### Step 1.3: Check Recent Changes

```bash
git log --oneline -10
git diff HEAD~5 --stat
```

- What changed?
- Any new dependencies? Any configuration changes?
- Any differences in the environment?

### Step 1.4: Trace the Data Flow

Apply the technique in [references/root-cause-tracing.md](references/root-cause-tracing.md).

- Trace backwards from the symptom of the bug
- Verify the input and output data at each layer
- In multi-layer systems, add diagnostic instrumentation

Display:
```
── Phase 1: Root Cause Investigation ──
Error: {error_summary}
Reproducible: {yes/no}
Recent changes: {relevant_changes}
Data flow trace: {trace_summary}
Suspected root cause: {hypothesis}
```

## Phase 2: Pattern Analysis

### Step 2.1: Find Similar Code That Works

- Look for similar patterns by searching the codebase and reading files
- Compare the part that works against the part that is broken

### Step 2.2: Identify the Differences

- List **every difference** between the working code and the broken code
- Do not assume "this one can't be related" — record every difference

### Step 2.3: Understand the Dependencies

- What other components does this code require?
- What configuration, environment variables, or preconditions are in play?

Display:
```
── Phase 2: Pattern Analysis ──
Working reference: {file_path}
Differences found: {count}
Key difference: {description}
```

## Phase 3: Hypothesis & Testing

### Step 3.1: Form Exactly One Hypothesis

- "I believe {X} is the root cause, because {Y}"
- Write it concretely (do not leave it vague)

### Step 3.2: Test It With a Minimal Change

- Make exactly one **minimal change** that verifies the hypothesis
- Do not apply several fixes at once
- Run the test in the shell and check the result

### Step 3.3: Verify

- The hypothesis held → advance to Phase 4
- The hypothesis was wrong → form a **new hypothesis** (do not pile on further fixes)
- You do not know → admit that you do not know. Do not guess

Display:
```
── Phase 3: Hypothesis ──
Hypothesis: {description}
Test: {minimal_change}
Result: {confirmed/rejected}
```

## Phase 4: Implementation

### Step 4.1: Write a Failing Test Case

- Write the minimal test that reproduces this bug
- Follow the TDD contract: [../shared/references/tdd-contract.md](../shared/references/tdd-contract.md)
- Run the test in the shell and **confirm that it fails**

### Step 4.2: Implement the Fix

- Fix the root cause (not the symptom)
- **One change only**. No "while I'm here" improvements
- Bundled refactoring is forbidden

### Step 4.3: Verify

- Run the tests in the shell and **confirm they all pass**:
  - The new regression test passes
  - No existing test has been broken
- Apply verification-gate: [../shared/references/verification-gate.md](../shared/references/verification-gate.md)

Display:
```
── Phase 4: Implementation ──
Fix: {description}
Regression test: {test_name}
Tests: {pass_count}/{total_count} passed
Result: ALL PASS ✅
```

## Three-Failed-Attempts Rule

Once you have attempted a fix three or more times and failed, **do not continue fixing automatically**.

Present the choices to the user and consult them:

```
⚠️ 3回の修正試行が失敗しました。根本的な設計の問題の可能性があります。

これまでの試行:
1. {試行1の概要} → {失敗理由}
2. {試行2の概要} → {失敗理由}
3. {試行3の概要} → {失敗理由}

選択肢:
1. アーキテクチャの問題を一緒に検討する（推奨）
2. 別のアプローチで修正を試す
3. 調査結果をレポートとして出力し中断する
```

- 「1」 selected → move on to the architecture discussion
- 「2」 selected → return to Phase 1 and re-analyze (with a different approach)
- 「3」 selected → show the investigation report and finish:
  ```
  ══════════════════════════════════════
  DEBUG SESSION REPORT (INCOMPLETE)
  Error: {error_summary}
  Root cause hypothesis: {best_hypothesis}
  Attempts: 3 (all failed)
  Recommendation: {architecture_review_suggestion}
  ══════════════════════════════════════
  ```

## Handoff from investigate

The path through which investigate's output arrives:

```
/claude-skills:investigate {problem}
  → 調査レポートを確認
  → /claude-skills:debug {investigate_report_summary}
```

In Phase 1, put the contents of the investigate report to work as context and drop the duplicated investigation.

## Completion Display

```
══════════════════════════════════════
DEBUG SESSION COMPLETE
Error: {error_summary}
Root cause: {root_cause}
Fix: {fix_description}
Regression test: {test_name}
Tests: ALL PASS ✅
══════════════════════════════════════
```

## Key Rules

- **Propose no fix before Phase 1 is complete** — the root cause comes first
- **One change at a time** — never apply several fixes simultaneously
- **No "while I'm here" improvements** — do not mix fixing with improving
- **Stop after three failures** — suspect a design problem
- **Admit when you do not know** — more investigation beats guessing
