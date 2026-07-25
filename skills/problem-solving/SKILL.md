---
name: problem-solving
description: 行き詰まった時の思考ツール集。5つのサブワークフロー（simplify/collide/invert/scale/pattern）で多角的にアプローチする。brainstorm セッションからも呼び出し可能。「problem-solving」「行き詰まった」「思考ツール」で起動。
---

# Problem Solving

A toolkit of thinking techniques for when you are stuck. Five sub-workflows, chosen by the
kind of impasse, guide reasoning at the conceptual level.

### How this differs from neighbouring skills

- **vs. brainstorm**: brainstorm diverges freely. This skill applies a specific thinking
  technique in a structured way
- **vs. investigate**: investigate establishes facts about a codebase. This skill supports
  conceptual thinking (no code generation)

## Hard constraints

### Forbidden operations (never perform, under any circumstances)

- Editing files
- Creating or overwriting files
- Editing notebooks

### Forbidden behaviour

- No code generation, no implementation proposals (pseudo-code for explaining a concept is
  fine)
- Never say "let's implement it" or "I'll write the code"
- Stay on conceptual discussion

### Permitted operations

- Reading files (to investigate the codebase)
- Pattern search (to investigate the codebase)
- Listing files (to investigate the codebase)
- Shell commands (**read-only only**: `git log`, `ls`, `cat`, ...)
- Dialogue with the user (offering choices, confirming)

## Workflow selection

The leading keyword of `$ARGUMENTS` selects the workflow:

- `simplify` → **Simplification Cascades**
- `collide` → **Collision-Zone Thinking**
- `invert` → **Inversion Exercise**
- `scale` → **Scale Game**
- `pattern` → **Meta-Pattern Recognition**
- (none) → **Dispatch** (identify the kind of impasse and route to the right technique)

---

## Dispatch workflow (no keyword)

Ask the user to identify the kind of impasse:

```
どのような行き詰まりですか？
1. 問題が複雑すぎて分解できない → simplify を提案
2. 新しいアイデアが出ない → collide を提案
3. 前提や制約が正しいか疑問 → invert を提案
4. スケールしたときの問題が見えない → scale を提案
5. 似たパターンを他で見た気がする → pattern を提案
```

Run the sub-workflow matching the user's choice.

---

## Shared structure of every sub-workflow

All sub-workflows run in the same four steps:

1. **Define the problem** — ask the user to make the problem concrete
2. **Apply the technique** — run the steps specific to that technique
3. **Organise the findings** — present a summary
4. **Propose next actions** — back to brainstorm / create a plan / try another technique

---

## Simplification Cascades

Find the "everything is a special case of X" and cut complexity drastically.

### When to use

- The same thing is implemented in five or more ways
- Special cases keep multiplying
- if/else chains are getting complicated
- Too many configuration options

### Process

1. **Define the problem**: ask the user "what feels too complex?"
2. **Identify similar patterns**: list the similar implementations, special cases, and
   branches
3. **Look for the common essence**: "what operation do all of these share?"
4. **Propose a unifying model**: present the frame "everything is a special case of {X}"
5. **Evaluate the cascade**: list what becomes unnecessary once unified

### Quick reference

| Symptom | Possible cascade |
|------|--------------|
| 5+ implementations of the same concept | Abstract the shared pattern |
| A growing list of special cases | Find the general case |
| Complex rules riddled with exceptions | Find the rule with no exceptions |
| Too many configuration options | Find the default that works for 95% |

---

## Collision-Zone Thinking

Force unrelated concepts to collide and let discoveries emerge.

### When to use

- Conventional approaches are not enough
- A breakthrough idea is needed
- You want to shift perspective

### Process

1. **Define the problem**: ask the user "what are you working on?"
2. **Pick unrelated domains**: offer three fields with no connection to the problem
3. **Force the collision**: "what if we treated {problem} like {domain}?"
4. **Explore emergent properties**: list the new ideas the collision produces
5. **Discuss feasibility**: weigh the ideas together with the user

### Quick reference

| Impasse | Domain to collide with | Possible discovery |
|-----------|-------------|-----------|
| Code organisation | DNA / genetics | Mutation testing, evolutionary algorithms |
| Service structure | Lego bricks | Composable microservices |
| Data management | Water flow | Streaming, data lakes |
| Request handling | Postal delivery | Message queues, async processing |

---

## Inversion Exercise

Invert the assumptions to uncover hidden constraints and alternative approaches.

### When to use

- It feels like "there is no other way"
- There are assumptions you never question
- You want to check whether a constraint is real

### Process

1. **Define the problem**: ask the user "what feels like 'there is no other way'?"
2. **List the assumptions**: list five or more current assumptions
3. **Invert each one**: work through "what if the opposite were true?" systematically
4. **Explore the implications**: how would you design in the inverted world?
5. **Find the hidden constraints**: an assumption that cannot be inverted is a real
   constraint; one that can be inverted was a belief

### Quick reference

| Usual assumption | Inversion | Discovery |
|-----------|------|------|
| Cache to cut latency | Add latency to make things cacheable | Debounce pattern |
| Pull data when needed | Push data before it is needed | Prefetching, eager loading |
| Handle errors when they occur | Make errors structurally impossible | Type systems, contracts |
| Add the features users want | Remove the features users don't need | Simplicity > addition |

---

## Scale Game

Test at extreme scale (1000× bigger / smaller) to expose the essence.

### When to use

- You are unsure about scalability
- The edge cases are unclear
- You want to know the limits of the architecture

### Process

1. **Define the problem**: ask the user "what do you want to scale-test?"
2. **Choose the scale dimension**: Volume / Speed / Users / Duration / Failure rate
3. **Consider the minimum extreme**: what if it were 1000× smaller / fewer / faster?
4. **Consider the maximum extreme**: what if it were 1000× bigger / more / slower?
5. **Identify the breaking point**: at what point does the design fall apart?

### Quick reference

| Scale dimension | Extreme test | Discovery |
|------------|-----------|------|
| Data volume | 1 row vs 1 billion rows | Algorithmic complexity limits |
| Speed | Instant vs one year | Need for async, caching |
| Users | 1 vs 1 billion | Concurrency, resource limits |
| Duration | Milliseconds vs years | Memory leaks, state bloat |
| Failure rate | 0% vs 100% | Soundness of error handling |

---

## Meta-Pattern Recognition

Extract a universal principle from a pattern that appears in three or more domains.

### When to use

- You feel you have seen the same pattern elsewhere
- You are getting déjà vu
- You suspect you are reinventing the wheel

### Process

1. **Define the problem**: ask the user "what pattern have you noticed?"
2. **Confirm it appears in 3+ domains**: list where the pattern shows up
3. **Extract the abstract form**: describe it in a domain-independent way
4. **Identify the variations**: how each domain adapts it
5. **Explore new applications**: where this pattern could be used but has not been

### Quick reference

| Where the pattern appears | Abstract form | Other applications |
|--------------|---------|----------|
| CPU / DB / HTTP / DNS caches | Keep frequently accessed data close | LLM prompt caching, CDN |
| Layering (network / storage / compute) | Separate concerns by abstraction level | Architecture, org design |
| Queueing (message / task / request) | Buffer to decouple producer and consumer | Event systems, async processing |
| Pooling (connection / thread / object) | Reuse expensive resources | Memory management, resource governance |

---

## Proposing next actions (all sub-workflows)

At the end of every sub-workflow, ask the user which next action to take:

```
💡 発見を次にどう活かしますか？
1. brainstorm でさらにアイデアを発散する → /claude-skills:brainstorm
2. plan を作成して実装に進む → /claude-skills:plan-create
3. 別の思考ツールを試す → /claude-skills:problem-solving
4. ここで終了する
```
