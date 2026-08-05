# Skill Authoring — Common Specification

The format specification and authoring principles for creating or substantially revising a
skill in this repository. Meta-skills such as skill-improve also reference it as their
judgement criteria. The machine-verifiable rules written here are enforced in CI by
`scripts/validate_repo.py`.

## The Trunk Workflow and the Funnel

This repository has one canonical flow — the **trunk** — for building or changing
anything. This section is the canonical home of the trunk diagram (do not copy it into
always-loaded files such as AGENTS.md). The behavioral spec of the entry phase is
[docs/spec/brainstorm.md](../../../docs/spec/brainstorm.md).

```
utterance / GitHub issue
        │   issues take no separate route — a well-groomed issue simply
        │   converges in one round of dialogue
        ▼
   brainstorm    idea → requirements → specification, hammered out in dialogue
        │        (heavy phase; agreed specs land in docs/spec)
        ▼
      plan       implementation plan seeded by the agreements
        ▼
   implement
        ▼
     review
        ▼
   alignment     write implementation-induced changes back into docs/spec and docs
        │        (station owner: doc-check's diff-driven checks; its dedicated
        ▼         branch-diff mode is being added)
       PR        feature branch; human-approved merge

 side lines (deliberately not wired into the trunk):
   ledger       — adjudication record; board only when decision history is wanted
   spec-verify  — spec → property-based tests; board only when automated contract
                  checks are wanted
```

### The Funnel Principle

Routing into the trunk is one rule plus an exception list — never a vocabulary-to-skill
mapping table (N phrases × M skills cannot be memorized and always leaks):

- **Default entry = brainstorm.** Any request to build or change something is first
  weighed against brainstorm.
- **Exceptions are enumerated work categories**, not judgment calls: terminal or
  read-only work such as committing, session handoff, or pure investigation. The
  runtime exception list is owned by the `using-workflow` skill; this section owns the
  diagram only. The split keeps the always-resident token cost low.

### Declare Where a New Skill Plugs In

Every new skill — and every substantial revision — states its position relative to the
trunk: which station it serves, which side line it is, or which funnel exception
category covers it. Not being able to state the position is a responsibility smell of
the same kind the Anti-bloat Clause tracks: a skill serving no station and no exception
is either duplicating a station owner or bundling several responsibilities.

## Directory Layout

```
skills/<skill-name>/
  SKILL.md          # required: the main logic
  references/       # optional: templates, checklists, etc. (relative links from SKILL.md)
  scripts/          # optional: execution helpers (skill-improve's collect.py, etc.)
commands/<command>.md  # optional: a thin wrapper that invokes the skill (not needed by default for new skills under the skills-first policy)
```

- Skill names are kebab-case. Do not use the single-file `.skill` format
- Put only files you actually use in `references/`. Do not create empty directories imitating
  another skill's layout
- Contracts and definitions shared by several skills go in `skills/shared/references/`, linked
  from each skill

## The Place of Commands (skills-first)

Always concentrate the logic in skills, and treat commands as optional sugar local to Claude
Code. Skills are the cross-tool common denominator (ecosystems such as Codex CLI / APM do not
support the equivalent of commands), and even on Claude Code a skill can be invoked directly
as `/skill-name`, so discoverability is secured by the description even without a command.

- **Default new skills to having no command**. Guarantee the invocation path by writing trigger
  words and argument usage into the SKILL.md description
- A command may be added only when a **named entry point for a multi-workflow skill** is needed
  (e.g. issue-create / issue-list / issue-plan for the `issue` skill — when you want each entry
  of a one-skill-many-workflows setup listed separately with its own explanation in `/`
  completion)
- Even when you do create a command, write no logic in it. Keep it a thin wrapper that only
  invokes the Skill tool and passes `$ARGUMENTS` through
- **Keep existing commands for compatibility**. A one-line wrapper costs almost nothing to
  maintain, and removing it breaks existing users' `/claude-skills:*` invocations. Do not
  actively add more; let them decline naturally
- **When a command name does not correspond to its skill name, name the target skill in the
  description** (enforced by check 16 of `validate_repo.py`). When the names diverge, as with
  `/debug` → `systematic-debugging`, commands and skills look like separate namespaces to the
  user, and the `/` completion blurb alone cannot identify the entry point. Since the policy is
  neither to rename nor to delete, solve it on the explanatory-text side. The
  `<skill-name>-<workflow>` form (`issue-list`, etc.) is exempt because the correspondence is
  self-evident

## Frontmatter Contract (enforced by validate_repo.py)

```yaml
---
name: skill-name        # matches the directory name
description: <what it does>. <when to use it (trigger words)>.
---
```

- **name / description are required** (check 3)
- **description is at most 1024 characters** (check 10)
- **description contains trigger words** (check 10): Japanese skills use
  「『◯◯』『◯◯』で起動」, English skills use "Use when …". Skill firing is decided by the model
  reading the description, so missing trigger words translate directly into missed firings
- **Do not write a workflow summary in the description**. Putting the procedure in the
  description causes the accident where the model acts on the summary alone without reading the
  body
- When an exemption is needed, register it with a reason in `DESCRIPTION_TRIGGER_EXEMPT` of
  `validate_repo.py` rather than in the frontmatter (do not let editing a skill file alone
  bypass verification)

## Authoring Principles

1. **Process over prose** — a skill is a workflow, not a reference document. Write it as
   phases, steps, and transition conditions. If it is turning into a pile of knowledge, move it
   out to `references/`
2. **Specific over general** — not "check the tests" but "run `npm test` and confirm 0 failures"
3. **Evidence over assumption** — always pair a completion condition with an evidence
   requirement (conforms to [verification-gate.md](verification-gate.md))
4. **Progressive disclosure** — SKILL.md is strictly an entry point. Put detailed material in
   `references/`, read at the point the workflow reaches it. References go one level deep from
   SKILL.md (do not chain references of references)
5. **Do not reinvent shared contracts** — TDD / verification gates / Codex integration /
   polling / language detection / orchestration design reference the existing shared
   references. Duplicated descriptions are a breeding ground for drift

## Anti-bloat Clause — Responsibility Placement (binding)

Measured on PR #190 (2026-08-02): cycle's SKILL.md grew 353 → 721 lines across 18
review rounds. Each round patched a mechanism defect with more prose, each patch opened
new interpretation branches, and those branches became the next round's findings — a
self-amplifying loop. It was broken only by moving the state transitions out of prose
into an executable primitive (`publication_advance.py`) verified by fault-injection
tests. Precision-through-prose also degrades execution: the longer the instructions,
the more context goes to procedure-following instead of the task, and low-salience
instructions drop out (Opus 5 prompting guidance).

Before adding any sentence to a SKILL.md or a runtime-loaded reference, apply this
test:

> Does this text improve the model's judgment — or does it describe a state transition
> that code should guarantee?

If the latter, do not write the sentence. Move the behavior to a script plus tests.

| Belongs in natural language (judgment) | Belongs in code (guarantee) |
|---|---|
| What may be auto-fixed, and what may not | Command sequences and their ordering |
| Where human confirmation is required | Atomicity, CAS, locking, crash recovery |
| What verdicts (BLOCK / WARN / …) mean | File layouts, retries, idempotency |
| Never-discard-on-failure safety principles | Anything a fault-injection test can pin |
| Priorities the model should weigh | Input validation and exit-code contracts |

Budgets — treat crossing them as a design smell demanding re-placement, never as a cue
for "tighter wording":

- A single run loading more than ~500 lines of instructions in total (SKILL.md plus every
  reference that run actually reads, measured per execution path). This is a diagnostic
  threshold, not a gate: crossing it makes the skill a re-placement candidate to declare,
  never a BLOCK. There is no separate per-file budget — a lean SKILL.md in front of heavy
  mandatory references is the same load. Below the threshold, fewer lines are still
  better: every low-value line dilutes the salience of the lines that must win at
  execution time.
- A review finding against a mechanism (race, crash window, ordering, cleanup) is
  resolved in code + tests. Answering it with prose is the loop restarting.
- Rationale, rejected alternatives, and rare-exception walkthroughs go to commit
  messages or to `references/` files the runtime path does not load.

### Load-reduction patterns (2026-08-03 corpus inventory, issue #201)

Apply these before rewording anything; they are ordered by measured leverage. Do not cut
disambiguation, defaults, or the one worked example to hit the budget — see "When Prompt
Compression Works" below for what must stay.

1. **Contract split — consumer view vs orchestrator view.** When one shared contract
   serves two audiences, extract what consumers need into a small sub-contract and keep
   the full machinery for its real users. First instance:
   [artifact-paths.md](artifact-paths.md) (~70 lines) replaces the full store contract
   (~450 lines) for every skill that only reads and writes artifact paths.
2. **Quote, don't load.** When a skill needs one sentence from a contract, quote that
   sentence inline and keep the link as provenance only, stating that the file is not
   read at runtime. Loading a 100-400 line contract to justify one sentence was the most
   common waste in the inventory.
3. **Conditional load at phase boundaries.** Attach every heavy reference to the branch
   that needs it so early-exit and common paths stay light. Worked examples: sweep-fix
   (early exit pays 395 of a 926-line worst path), ledger (a 42-line router whose
   497-line contract loads only at the moment of writing).
4. **Split section-addressed monoliths.** A file cited for one of its sections (one
   agent's criteria, one definition) but loaded whole should be split along its
   consumption seams; an anchor link does not reduce the load.
5. **Guard against under-loading.** The inverse failure exists: a rule the skill's
   guarantees depend on needs an explicit read instruction on the path that uses it, not
   a listing under "References". Explicitness may add lines; that is the correct trade.

## Rationalization-prevention Tables and Red Flags

State in a table the "excuses" an agent makes when skipping a step, and the rebuttals.
Recommended for skills that have easily-skipped steps (verification, tests, confirmation).

```markdown
## Preventing rationalization

| Excuse | Reality |
|--------|------|
| "Just this once" | No exceptions. That is rationalization |
| "I already know it's right" | Confidence is not evidence |
```

- Worked examples: the rationalization prevention in
  [verification-gate.md](verification-gate.md), the rationalization table in
  [tdd-contract.md](tdd-contract.md)
- **Red Flags** is an observable list of "signs the skill is not being followed". Use it during
  review and for self-monitoring. Write it in a decidable form ("declaring GREEN without
  running the tests")

## When Prompt Compression Works (based on empirical-prompt-tuning measurements)

Even for Fable 5 generation models, "shorter is better" does not hold. Measuring the plan /
cycle skills over 6 iterations with `empirical-prompt-tuning` produced the following
observations.

### Patterns that work

- **Consolidating inline duplicate explanations into contract references**: replace a shared
  contract inlined into SKILL.md (checkpoint restore procedure, delegation relay, etc.) with a
  short reference to the canonical contract. It is markedly effective when these 3 conditions
  hold (measured friction -37%):
  1. The inline section is long (tens of lines or more)
  2. The inline section is not relevant to every scenario (e.g. the checkpoint section is
     unnecessary when creating a new plan)
  3. It is fully covered on the contract side
- **Cutting examples and enums**: a capable model does not need general definitions such as "how
  to build a URL slug". Keep one example or cut it entirely
- **Reducing prohibition words ("never" / "must not", `絶対に` / `してはならない`)**: they are the main cause of
  `over_specified` and `rationalization_hook`. Compliance does not drop with softer phrasing
  (measured: both categories vanished completely within 4 iterations)

### Patterns that do not work / must not be cut

- **Deleting the contract side's rationale / rejection records / v2 roadmap**: it reduces
  maintenance debt but the runtime signal is weak (friction barely changed)
- **Loosening "conventions" such as path constraints or auto-mode discrimination**: compliance
  collapses
- **Consolidating always-relevant information**: when the inline section is needed in every
  scenario, consolidating it leaves the executor reading the same amount of information, so the
  effect is thin (demonstrated by compressing cycle's delegation relay)

### Structural friction cannot be solved by cutting prose

`ambiguous_term` / `missing_premise` / `self_containment_gap` are solved by **making things
explicit and adding examples**, not by reduction. Because the causes are ambiguity in template
formats, missing project information, and the template-chase structure itself, the approach
required runs opposite to the Fable line of argument.

### Additional findings from rollout batch 1 (commit / plan-reviewer, 2026-07-22)

- **For skills that are already lean (~150-200 lines), the main effect is friction reduction
  rather than size reduction**: commit came to -9% in lines against -83% in friction (6→1,
  precision maintained at 100%). Adding explicitness can even increase the byte count, and that
  is fine ("selecting high-signal tokens" is the correct framing)
- **Run compression themes and explicitness themes in separate iterations**: it lets you observe
  separately the friction that disappears through compression (originating in duplicate
  explanation) and the friction that only disappears through explicitness (missing defaults,
  undefined branches)
- **`is_diverged` is a coarse, category-level judgement**: even when the details differ every
  time and the total is gradually decreasing, 3 consecutive occurrences of ambiguous_term make
  it diverged. If the residue is (a) an inherently judgement-bound area, (b) the
  contract-reference design itself, or (c) caused by the evaluation harness, adding prose tips
  over into over-specification, so stopping is the right call

### Separating the 3 kinds of "conservative" (measured 2026-07-25 / null result)

The Opus 5 prompting guide states that "*be conservative* in a review prompt is followed
literally and reduces the volume of reporting". Taking stock of this repository and measuring
it, **the claim turned out to barely apply to this repository's review-family skills**.

**Stock-take**: of the places whose text says "conservative", only 1 actually suppresses
reporting. The classification has the following 3 kinds, and the guide targets only the first.
Loosening the other 2 by conflating them lowers safety.

| Kind | Example | Handling |
|------|------|------|
| Conservatism that suppresses reporting | Lower the severity when there is no context | Covered by the guide. In scope for measurement |
| Conservatism in the opposite direction (maintaining reporting) | Do **not** lower the severity unless unreachability is confirmed / assume reachability as "could be reached" | Already in the report-all direction. **Do not change** |
| Fail-safes that narrow automatic fixing | Fall back to NEEDS_JUDGMENT / emit UNCERTAIN generously / do not auto-complete | A breakwater against wrong fixes. **Do not change** |

**Measurement**: the single applicable place (`review-testing`'s "if there is no spec or usage
context to judge the blast radius, keep the severity conservatively at WARN") was measured with
2 before/after variants × 2 scenarios, with k=3 for the discriminating scenario (3-role
separation, production-equivalent model, checklist locked by sha256).

- **Severity demotion occurred in 0/3 for both variants**. Executors maintain BLOCK based on
  **the contract evidence the code itself carries** — docstrings, raised exceptions, destructive
  operations. In 1 of those runs the executor explicitly reasoned that "the docstring states the
  blast radius, so demotion to a conservative WARN is unnecessary"
- In the low-impact-area scenario (pure functions) neither variant inflated BLOCK. Removing the
  demotion instruction does not cause severity inflation
- The rewritten version was non-inferior on requirement satisfaction but **no improvement was
  measured**. Since lines and tokens increase, it is not grounds for adoption

**Consequence**: do not rewrite an instruction merely because the word "conservative" appears in
it. First (a) classify whether it is report suppression or a fail-safe, and (b) even on the
suppression side, measure **whether demotion actually happens** before deciding. As long as the
code under review carries its own contract evidence, demotion justified by missing context is in
practice unlikely to occur.

### Whether to delete verification-gate (measured 2026-07-25 / null result)

Claim 1 of the Opus 5 prompting guide — "explicit verification instructions induce
over-verification; deleting them costs no quality and only reduces tokens" — was measured
against `verification-gate.md`. **A token reduction could not be established.**

Measurement: targeting cycle's fixture cy-001, an ablation was built taking the gate body from
88 lines to 30 (deleting the Iron Law / Gate Function / prohibited-expression list /
rationalization-prevention table / verification-pattern table, leaving only the per-skill
integration guidance), and each was run live at n=3.

| | median tokens | median tool calls | independent re-verification of delegated reports |
|---|---|---|---|
| With gate | 110,557 | 34 | 3/3 |
| Without gate | 99,576 | 32 | 3/3 |

- Against a median difference of -9.9% (11.0k), the noise_band (half the between-run spread) is
  about 9.7k. **It barely clears the threshold and would flip with one run's worth of
  variance**. At n=3 one cannot say a reduction exists
- Quality did not degrade in either variant. **In 6/6 runs the behavior of "not trusting the
  delegate's report and re-verifying it oneself" was observed** — including the 3 runs with the
  gate cut
- The reason is plain: `cycle/SKILL.md` itself demands test-run evidence in Phase 2. **The
  gate's enforcement power is already inlined into the referencing skill**, so erasing the
  rhetoric on the shared-contract side does not move runtime behavior

**Consequence**: there are no grounds for deleting the gate. That said, if "the referencing side
already carries the same requirement", the volume on the shared-contract side does not affect
runtime behavior — so if you do cut, **check the referencing side's requirements first**.

**Limits of this measurement (for whoever measures next)**: the ablation is not clean. While the
gate's sections were erased, `cycle/SKILL.md` keeps referencing "apply the Gate Function", so the
no-gate condition was not "no instruction" but "an empty reference target" (1 executor detected
it as a dangling reference). Without simultaneously replacing the wording on the referencing
side, it is not a pure ablation.

### Turning Convergence History into an Asset

As a fixture for `empirical-prompt-tuning`, the plan skill's 4-iteration convergence history is
recorded in `.agents/tmp/empirical/plan-*/fixture.json`. The measurements for rollout batch 1
are in `.agents/tmp/empirical/20260722-lean-rollout/` (summary.md + iterations.jsonl). Refer
there for the full text of category transitions, reduction amounts, and lessons. Use them as
baseline comparison and regression-detection assets when re-tuning.

### Release Units and version bump

A version is a "unit of distribution", not a "unit of change". Bumping per PR makes concurrent
PRs all claim the same number, so every merge leaves the rest conflicting across 3 manifests +
CHANGELOG (a real case: 6 simultaneously open PRs were all 1.66.0).

- **Do not bump the version in a PR**. Append the change to `## Unreleased` in `CHANGELOG.md`
- Bump exactly once at release time. Rename `## Unreleased` to `## <version>` and update
  `.claude-plugin/plugin.json` / `.claude-plugin/marketplace.json` / `.codex-plugin/plugin.json`
  together
- Keep `## Unreleased` singular, in canonical notation, and above the latest version (verified by
  check 12b of `validate_repo.py`). This uniquely determines what gets promoted to a number at
  release time

For an optimization rolled out incrementally across several skills, additionally observe the
following.

- Implementation, verification, and commits are separated per batch, but the entry into
  `## Unreleased` is consolidated into a single entry at rollout completion, covering the
  overall perceptible change, the total reduction, and the verification scope
- Manage the target list and completion conditions in the rollout's parent issue. Keep the
  batch-specific measurement history canonical in the issue and the local empirical artifacts;
  do not create provisional per-batch entries

## Cross-tool Compatibility Notes

- **Unify the body language within a single skill (English is recommended for the body)**: mixing
  English and Japanese hurts readability (user ruling, 2026-07-22). English is also better for
  token efficiency — measured with o200k, the Japanese version of the same content is about +30%
  (commit: 1,607 EN vs 2,091 JA tokens), and plan-reviewer, which had been mixed, went from
  3,758 to 3,025 tokens (-19.5%) from unifying to English alone. The frontmatter `description`
  may stay Japanese because it needs to contain the user's spoken vocabulary (Japanese
  triggers). Quoting the heading names or matching vocabulary of a Japanese contract file (e.g.
  "ユーザー確認") does not count as mixing
- **Do not treat a proxy model's measurements as a guarantee for the production model**: when
  exploration or non-inferiority evaluation is done on a same-generation low-cost model in place
  of the expensive production model, state the evidence scope — equivalent to
  `proxy verified / production untested` — in the fixture's `notes` and the measurement summary
  (a `pass` in the skill-regression ledger is a freshness record of the behavioral surface and
  says nothing about the model range). Do not run production-model sentinels automatically; run
  them only with user approval after presenting the target scenarios, the uncertainty, the
  estimated consumption, and the stop limit. Even without approval, a proxy-passing version can
  be rolled out as a staged canary, but production-accuracy guarantees must not be claimed
- Keep `skills/` as the single source of truth for skill bodies, in natural language readable by
  Claude Code / Codex CLI / Cursor / Gemini CLI and others
- In `SKILL.md` and `references/`, use expressions that do not depend on a specific platform's
  tool API names or model names
- When a platform difference is necessary, do not fork the body into copies; unify it into one
  using shared vocabulary and fallbacks
- **Judge a shared contract's portability on 3 levels**: a contract placed in
  `skills/shared/references/` is a single source of truth read from multiple runtimes. On
  creation or revision, confirm which of these it falls under
  - **tool-agnostic**: the content contains no tool-specific API names and holds as-is across
    multiple runtimes
  - **platform-aware**: there are runtime differences (external review, subagents, interactive
    confirmation), but they can be expressed with shared vocabulary and fallbacks
  - **platform-specific**: when a proprietary API name is unavoidable, state the reason and its
    irreplaceability in the body and minimize the blast radius
- **Do not depend on interactive user confirmation**: depending on the runtime, the means of
  interactive confirmation may only be available in specific modes (confirmed by measurement).
  Any skill body that requires confirmation must state a path that demotes to a safe-side default
  (no-op / report-only / UNCERTAIN / abort) when no response is obtainable in non-interactive
  execution

## Checklist for Adding a New Skill

- [ ] Declared the skill's position on the trunk (station / side line / funnel exception
      category) — see "The Trunk Workflow and the Funnel"
- [ ] Decided whether a command is needed under the skills-first policy (no command by default;
      add a thin wrapper only when a named entry point for a multi-workflow is needed)
- [ ] Updated the main skill tables in AGENTS.md / README.md as needed (keep CLAUDE.md a thin
      wrapper)
- [ ] Updated README.md (command table, skill table, file layout)
- [ ] Updated `.claude-plugin/` / `.codex-plugin/` if the change needs to be reflected in the
      plugin manifests
- [ ] If using multiple agents, went through the decision flow of
      [orchestration-patterns.md](orchestration-patterns.md) and stated the model specification
      (conforming to the model tiers) explicitly on the Agent invocation
- [ ] `python3 scripts/validate_repo.py` passes all checks
- [ ] Appended the change to `## Unreleased` in `CHANGELOG.md` (do not bump the version in a PR)
