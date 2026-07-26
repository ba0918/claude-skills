---
name: trigger-eval
description: スキルセットの description 発火精度（recall / precision / stability / confusion matrix）を、description-only の判定 subagent で機械的に実測し、衝突ペアを特定して description 改稿→再評価ループを収束まで回すメタスキル。実測エビデンス（メトリクス差分・holdout ゲート・Tier1↔Tier2 乖離率）で改善を証明する。対象は本リポジトリの skills/ のほか、任意のスキルディレクトリやユーザースコープも指定できる。「trigger-eval」「発火精度」「スキル発火の計測」「トリガー評価」「description 改稿」「confusion matrix でスキル衝突を見たい」で起動。`empirical-prompt-tuning`（本文実行の質）に対し選択層（description→発火）を測る姉妹スキル。
---

# trigger-eval

A meta-skill that measures and improves, as a property of description quality, the "spontaneous skill triggering from natural-language instructions" that degrades as the number of skills grows. By passing the judging agent **nothing but the list of descriptions** (reproducing the model's field of view at real triggering time), it measures recall / precision / stability / confusion matrix mechanically and runs the revise→re-evaluate loop to convergence.

**Positioning**: where [`empirical-prompt-tuning`](../empirical-prompt-tuning/SKILL.md) measures "the quality of executing the body", trigger-eval measures "the selection layer (description → triggering)". It stands in a static/dynamic complementary relation to `validate_repo.py` check 10 (the static presence check for trigger words).

## Minimal execution recipes

```
trigger-eval                # 本リポジトリの skills/ を対象に Phase 0→6
trigger-eval --dir PATH     # 任意のフラットなスキルディレクトリ
trigger-eval --user-scope   # ~/.claude/skills
trigger-eval --no-e2e       # Tier 2 実発火検証をスキップ（デフォルトは実行）
trigger-eval --selection-only  # Tier 1 を selection モードのみ計測（デフォルトは selection + autonomous）
```

No command is created (the skills-first policy; being single-workflow, it needs no named entry point either).

## Architecture: a static pre-pass plus two evaluation tiers

| Tier | Method | Cost |
|----|------|--------|
| Phase 1.5 static collision pre-pass | Compute all pairwise collision candidates deterministically from the vocabulary Jaccard of the descriptions (`static_collisions.py`, no LLM) | Nearly zero |
| Tier 1 selection simulation | Pass a bias-free subagent only the description list plus a batch of fictional instructions, and have it choose the skill to use (or none) as JSON | Low (a lightweight model, ≤20 cases per call, dispatched in parallel) |
| Tier 2 E2E real-triggering verification | Pass the fictional instructions raw to `claude -p` and detect the Skill tool_use from the stream-json. **Run it in a throwaway git worktree** | High (a total cap of 6 sessions, enforced by a driving-side shell loop) |

The detailed contracts for judging and aggregation are split into reference material (progressive disclosure):

- The judging agent's contract: [references/judge-protocol.md](references/judge-protocol.md)
- Case design guidelines: [references/testcase-design.md](references/testcase-design.md)
- The strict definition of the metrics: [references/metrics-spec.md](references/metrics-spec.md)

For the general rules on countering bias see `skills/shared/references/codex-integration.md`, and for the model tiers of subagent invocation see `skills/shared/references/orchestration-patterns.md` (do not restate them).

## Workflow

### Phase 0: Collect the targets

```bash
python3 skills/trigger-eval/scripts/collect_descriptions.py --dir skills \
  --output .claude/tmp/trigger-eval-{ts}/skills.json
```

- Turn the `{name, description}` list into JSON. With no argument, the current repository's `skills/*/SKILL.md`. Apply it generally with `--user-scope` / `--dir PATH`.
- **Normalize the skill names to the bare name with the plugin prefix removed**, and use that same namespace thereafter for the cases' correct labels, the judging choices, and the aggregation.
- **Duplicate bare names are fail-fast** (v1 does not support duplicate namespaces).
- **Out of scope for v1**: the hashed nested structure of the plugin cache (`~/.claude/plugins/cache/<mp>/<plugin>/<hash>/skills/`). Add the glob when it becomes necessary.

### Phase 1: Harvest real-data seeds (optional)

```bash
python3 skills/skill-improve/scripts/collect.py --capture-prompts --days N \
  --output .claude/tmp/trigger-eval-{ts}/prompts.jsonl
```

- Harvest the triggering record and the missed-triggering candidates (the `correction_after_skill` signal plus the masked `user_text_masked`). The output goes only under `.claude/tmp/trigger-eval-{ts}/`.
- collect.py itself **verifies before writing that the path is ignored, via `git check-ignore --quiet <the resolved actual output path>`, and refuses on a non-zero result** (fail-closed; it does not scan the root .gitignore as a string).
- **The masking is a denylist and is not complete**, so treat a harvested body file as sensitive even after masking (delete it in Phase 6).

### Phase 1.5: Static collision pre-pass

```bash
python3 skills/trigger-eval/scripts/static_collisions.py \
  .claude/tmp/trigger-eval-{ts}/skills.json --top-n 30 \
  --output .claude/tmp/trigger-eval-{ts}/collisions.json
```

The top pairs are used for (a) defining the "neighboring skills" for hard-negative generation, (b) prioritizing revisions, and (c) obvious merge candidates that need no judging.

### Phase 2: Generate the test cases and freeze them in advance

**The generator is a dedicated subagent (a lightweight model) separate from the reviser**. Follow [testcase-design.md](references/testcase-design.md):

- 2 positives / 1-2 hard negatives / at least 25% none overall. A single correct label.
- ≤10 skills per call, and **verify that the number of emitted cases == the expected number**.
- **Freeze them into `cases.json` (train) and `cases_holdout.json` (a 20% holdout, stratified so that both sides hold at least 25% none)**. No substitution thereafter. Never show the holdout to the revision loop.
- **Apply the triple anonymization gate before freezing** (re-apply the masker / reject near-matches against the raw seeds / screen for high-entropy tokens).

### Phase 3: Judging round

Pass the judging agent (**a lightweight model, stated explicitly**, a fresh subagent) the description list plus a batch of cases, and collect its JSON answers. Follow [judge-protocol.md](references/judge-protocol.md):

- **Judge in two modes** (selection / autonomous of `judge-protocol.md`). **The default measures both selection and autonomous**, and `--selection-only` restores the former behavior (selection only). The input and output schemas are shared and only the framing differs. Generate `judged-{mode}-iterN.json` separately per mode (never mix them).
- Distributing the input is either **inline passing, or read access to exactly two files: `skills.json` plus the batch file** (「入力の配布方法」 of `judge-protocol.md`).
- Batches of ≤20 cases, dispatched in parallel (at most 4). Shuffle the case order.
- On collection, **verify that "the number of judgments == the number of cases"**. Re-judge a malformed batch exactly once → if it is still malformed, materialize it as `INVALID`.
- For stability, judge the same case independently twice (from the second iteration onward, reduce this to a fixed sample of 20-30 cases; `--full-stability` for all of them).
- State explicitly in the judging prompt that "no tools may be used, and the judgment must come from the given input alone" (a soft guarantee). When passing files, state explicitly as well that no file other than the two permitted ones may be read.

### Phase 4: Aggregation

```bash
# モードごとに同じスクリプトを別々に通す（aggregate_metrics.py は無改修）
python3 skills/trigger-eval/scripts/aggregate_metrics.py \
  .claude/tmp/trigger-eval-{ts}/judged-selection-iterN.json \
  --output .claude/tmp/trigger-eval-{ts}/metrics-selection-iterN.json
# --selection-only でない限り autonomous も同様に集計
python3 skills/trigger-eval/scripts/aggregate_metrics.py \
  .claude/tmp/trigger-eval-{ts}/judged-autonomous-iterN.json \
  --output .claude/tmp/trigger-eval-{ts}/metrics-autonomous-iterN.json
```

Compute recall / precision / specificity / stability / confusion matrix / invalid_rate with the formulas of `metrics-spec.md`. **Never mix the two modes' results**: selection is authoritative for the convergence and regression guards, and autonomous is a reference series (「モード軸」 of `metrics-spec.md`).

On completing a measurement (the selection series of each iteration), append a measurement event per target skill so that runs can be compared ([measurement-identity.md §4](../shared/references/measurement-identity.md#4-既存系の写像表), recommended):
`python3 skills/shared/scripts/measurement_identity.py emit --system trigger-eval --event eval --skill <対象スキル> --repo-root {repo_root} --outcome '{"recall":R,"precision":P,"stability":S}'`

### Phase 5: Revision

- Narrow the revision to the worst offenders (the top confusion pair, or the skill with the lowest recall) and revise its description (**one theme per iteration**).
- Conform to the frontmatter contract of `skill-authoring.md` (trigger words mandatory, a 1024-character cap, no workflow summaries), and make **passing `validate_repo.py` the completion condition for a revision**.
- **When revising, visually confirm consistency with the SKILL.md body** (do not promise capabilities beyond the body for the sake of the trigger rate).
- **One revision = one git unit per skill.** If re-evaluation regresses or validation fails, revert that description to its pre-revision state (the rollback path).

### Phase 6: Re-evaluation → convergence judgment

Repeat Phases 3-5. **The selection-mode series is authoritative** for judging the stopping conditions (autonomous is a reference series and a calibration signal; never mix it into the convergence or regression judgment. See the mode axis of metrics-spec.md). The stopping conditions are any of:

1. **Convergence**: the improvement in macro recall / precision is under +1pt for two consecutive iterations.
2. **Hard cap**: `max_iterations = 5`.
3. **Regression guard**: any skill's recall / precision, or specificity / invalid_rate, regresses by **more than 5pt** against the previous iteration → revert the last revision and stop (a defined↔undefined transition in precision is a non-comparison; see metrics-spec.md).

After stopping:

- (a) **The holdout judgment (mandatory, an adoption gate)**: if the holdout's macro recall / precision is not non-degraded against the pre-loop baseline, **revert the last adopted revision and state "holdout FAIL" explicitly in the report**.
- (b) **Tier 2 real-triggering verification** (a stratified, fixed 6 sessions, with the cap enforced by a driving-side shell loop, **run by default**, skippable with `--no-e2e`). Record the Tier1↔Tier2 divergence rate.

**Tier 2's stratified allocation (fixed)**: 2 positives for the revised skill / 1 positive for the worst unrevised skill / 1 none / 1 hard negative / 1 at random from all cases. **When no revision was adopted (immediate convergence, or everything reverted by a holdout FAIL), reallocate the revised-skill slots to positives for the worst-recall skill.** Always attach a note to the divergence-rate report that it is a stratified small sample and not an estimate of the whole.

### Report

Emit to `.claude/tmp/trigger-eval-{ts}/report.md`:

- The metric trajectory / the top confusions (**only the non-zero cells and the top N pairs, not a full matrix dump**, listing both the raw value and the normalized rate `confusion(A,B)/related_cases(A,B)`)
- **The selection / autonomous modes side by side** (selection only under `--selection-only`). Place selection as the primary metric and autonomous as a reference series, and note the divergence between them as a salience signal. **Never emit a mixed value**
- The revision diffs / the Tier1↔Tier2 divergence rate / the holdout judgment
- **Candidate pairs for merging or redesigned separation** (the top of the static pre-pass, plus pairs whose confusion does not resolve after two revisions)
- Execution metadata (the judging model / the date / the sha256 of `cases.json` and `cases_holdout.json` / the stability sample ledger)

**What is retained is report.md / cases.json / cases_holdout.json / the metrics JSON of each iteration** (the anchors for reproduction and cross-run comparison). **The harvest files containing raw prompt bodies (the `--capture-prompts` output) are deleted.** Prompt deletion of `trigger-eval-*` directories older than 30 days. The failure examples put into report.md are **only cases that passed the anonymization inspection** (transcribing a raw seed is forbidden).

## The four-part set of resource caps

Leave no dimension unbounded:

1. Judging batches of ≤20 cases per call, plus the judgments==cases verification
2. Case generation of ≤10 skills per call, plus the count verification
3. The `max_iterations = 5` hard cap on the revision loop, plus the regression guard
4. JSONL is pre-filtered by mtime and streamed line by line; Tier 2 is 6 sessions × (`--max-turns 2` + a 180s timeout)

## Preventing rationalization

| Excuse | Reality |
|--------|------|
| "Padding the description will fix it" | The 1024-character cap, the trigger-word convention, and the body-consistency check are the ceiling. Passing validate_repo.py is the completion condition |
| "I want to swap the cases out afterwards" | That violates the freeze-in-advance principle. The holdout gate detects the overfitting |
| "Tier 2 is expensive, so always skip it" | It runs by default. Skipping requires an explicit `--no-e2e` |
| "It is not converging, so let us do one more round" | The `max_iterations=5` hard cap |
| "It regressed, but the average improved" | The 5pt regression guard on per-skill recall/precision plus specificity/invalid_rate reverts it |
| "The holdout is bad but train is good, so adopt it" | The holdout is an adoption gate. On FAIL, revert |
| "Showing the body to the judge would raise accuracy" | That diverges from the model's field of view at real triggering time and produces false positives. description-only is the specification |

## Red flags (signs of a trigger-eval violation)

- Passing the SKILL.md body to the judging agent
- Editing the cases after freezing them / showing the holdout to the revision loop
- Adopting despite the regression guard or the holdout gate on the grounds that "it is written in the report", without reverting
- Leaving the `--capture-prompts` output among the retained artifacts
- Always skipping Tier 2 without a reason
- A revised description promising capabilities beyond the SKILL.md body
