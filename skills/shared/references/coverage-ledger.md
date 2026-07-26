# Coverage Ledger

The evaluation-scope ledger. A shared contract that lets review-family skills state explicitly
"what they looked at, and how far". Focused reviews such as `review-testing` / `review-deps`
always include it in their output. Severity (BLOCK/WARN/INFO/PASS) and the 3-value verification
(CONFIRMED/FALSE_POSITIVE/UNCERTAIN) are owned by
[severity-and-verdicts.md](severity-and-verdicts.md), and this contract defines only the
"evaluation scope" axis, which is orthogonal to them.

## Why It Is Needed

An overall score ("test quality: 82 points") or a list of PASSes hides **what could not be
measured**. Areas with no scanner, areas deliberately excluded, and areas where evidence was
insufficient to reach a conclusion all end up looking identical to "no problems". The coverage
ledger structurally distinguishes "no problems (reviewed with no findings)" from "not looked at
(skipped / unsupported)" and makes the blanks in a review visible.

## The Iron Law

```
finding が 0 件でも、評価範囲が空でないことを ledger で示せない限り「問題なし」と言ってはならない。
見ていない領域は skipped / unsupported として必ず ledger に載せる。黙って落とさない。
```

## The 4 Values

| Value | Meaning | How to choose it |
|----|------|-------------|
| **reviewed** | There were sufficient inputs and means of verification, and it was actually evaluated | The target files were read and the detection predicates could be applied. Whether there were findings does not matter (PASS is one possible result of reviewed) |
| **skipped** | Deliberately left out of the evaluation | Out of scope, explicitly excluded by the user, non-target generated artifacts, and so on. **Always state the reason** |
| **unsupported** | Cannot be evaluated because the tooling, ecosystem, or environment does not support it | No scanner, no network access, no registry metadata to determine a maintainer handover, etc. **Also state what would be needed to promote it to reviewed** |
| **inconclusive** | It was looked at, but there was not enough evidence to reach a conclusion | Candidates were observed but the evidence satisfying the verification predicate was insufficient. **Also state the missing evidence** |

- Each entry carries 3 things: the target (file / area / ecosystem) + the value + the reason.
  A `skipped` / `unsupported` / `inconclusive` without a reason is invalid as a ledger (it
  violates The Iron Law).
- Always write a reason for anything other than `reviewed`. Even for `reviewed`, note the means
  of verification when a non-obvious one was used.

## Orthogonality with severity (PASS)

The severity **PASS** (no problems detected for a given dimension) is "the result of an
evaluation" and is a different thing from the evaluation-scope axis. **PASS appears as a subset
of `reviewed`.**

```
reviewed  → finding あり（BLOCK/WARN/INFO） または finding なし（= PASS）
skipped / unsupported / inconclusive → そもそも PASS を名乗る資格がない
```

Reporting a `skipped` area as PASS is an Iron Law violation. Do not conflate the two axes.

## inconclusive (the scope axis) and UNCERTAIN (the finding-verification axis) are different axes

These 2 words look similar but belong to different axes. Conflating them lumps together "where
we have not looked" and "whether we may act on a candidate we did look at".

| Word | Axis it belongs to | The question | Defined in |
|----|-----------|------|--------|
| **inconclusive** | Evaluation scope (this contract) | Was there evidence to conclude about this **area**? | This file |
| **UNCERTAIN** | Finding verification (the 3-value judgement) | May we act on this **individual candidate**? | [severity-and-verdicts.md](severity-and-verdicts.md) |

- `inconclusive` attaches to an area (e.g. "the coverage of asynchronous processing is
  inconclusive — there is no execution trace").
- `UNCERTAIN` attaches to an individual finding candidate (e.g. "whether this public API is
  test-only cannot be determined from the call sites, so UNCERTAIN").
- An area being `reviewed` and an individual candidate within it being `UNCERTAIN` can coexist.
  Conversely, if a whole area is `inconclusive`, the candidates within it are not promoted to
  findings (the evidentiary base itself is missing).

## Integration Convention for the report envelope

A review report **always includes a Coverage Ledger section**, separate from the findings
section. The minimal form:

```
## Coverage Ledger

| 対象 | 判定 | 理由 / 昇格条件 |
|------|------|----------------|
| src/**/*.test.ts（12 files） | reviewed | 全ファイルにアンチパターン述語を適用 |
| e2e/（Playwright） | skipped | 本レビューは単体テスト品質に限定（利用者指定） |
| mutation sensitivity | unsupported | mutation runner 未導入。導入すれば reviewed に昇格 |
| 非同期順序依存 | inconclusive | flaky 再現に実行トレースが必要。ログがあれば結論可 |
```

- The ledger matters most precisely when there are 0 findings (it is the only way to make a
  difference from an empty report).
- Each review skill can prevent reporting gaps by keeping, in its template, default
  `unsupported` / `skipped` entries for the areas it structurally cannot see.

## Obligations of Skills Using This Contract

A skill using 3 or more of `reviewed` / `skipped` / `unsupported` / `inconclusive` must place a
relative md link to this file (mechanically required by `CONTRACT_VOCAB` in
`scripts/validate_repo.py`, to stop the drift of declaring the vocabulary while reinventing the
substance inline).
