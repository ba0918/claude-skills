# Fix-Action Taxonomy 共通契約

doc-audit / context-audit が共有する「検出した finding をどう扱うか」の分類軸。
これは **severity（BLOCK/WARN/INFO/PASS, `severity-and-verdicts.md`）とは直交する別軸**であり、
「その finding に対して自動修正してよいか」を決める。出自は doc-audit の
`references/checks.md` のローカル分類で、context-audit が 3 番目の consumer になるため共有化した。

## 2 軸は直交する

| 軸 | 値 | 意味 | 定義元 |
|----|----|------|--------|
| severity | BLOCK / WARN / INFO / PASS | 問題の重大度（どれだけ困るか） | `severity-and-verdicts.md` |
| fix action | AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY | 修正の自動化可否（どう直すか） | 本ファイル |

例: 重大度 WARN でも AUTO_FIX なことも、REPORT_ONLY なこともある。両者を混同しない。

## 3 つの fix action

### AUTO_FIX

条件: **機械的に検証可能 + 冪等 + データ損失リスクなし**。
同じ操作を何度実行しても同じ結果になる（idempotent）。ツールが差分を提示し、
確認の上で適用する。**削除・本文の意味的書き換えは AUTO_FIX にしない**。

例: 実在ファイルへの明白なパス typo 置換（候補が一意）、frontmatter キーの正規化（body 不変）。

### NEEDS_JUDGMENT

条件: **意味的解釈が必要 / ユーザー意図が曖昧**。
ツールは finding と推奨アクションを提示し、**決定はユーザーが行う**。
迷ったら AUTO_FIX ではなくこちらに倒す（fail-safe）。

例: パス候補が複数あって一意に定まらない、スキル一覧のカバレッジ差分（意図的な省略かもしれない）。

### REPORT_ONLY

条件: **情報提供のみ**。自動アクションは取らない。
what / why / how を含む actionable なレポートとして提示するが、修正はしない。

例: 破壊的操作を許可する語彙、ツール語彙の混入、矛盾候補、secret 疑い（自動マスク禁止）。

## doc-check の `OK` との差異

doc-check（code ⇔ docs）は「一致 = `OK` / 不一致 = 要修正」の 2 値で、fix action の 3 値とは別体系。
`OK` は「問題なし（そもそも finding が出ない）」であり、REPORT_ONLY（「finding は出るが直さない」）とは異なる。
finding が発生した時点で 3 値のいずれかに分類される。

## Gate Function

```
finding に fix action を割り当てる前に自問する:

1. この修正は機械的に検証でき、何度実行しても同じ結果か？（冪等か）
   NO  → AUTO_FIX にしない
2. データ損失（削除・本文の意味的書き換え）を伴うか？
   YES → AUTO_FIX にしない
3. 意図が一意に定まるか？（候補が複数 / 意味解釈が必要ではないか）
   NO  → NEEDS_JUDGMENT
4. そもそもアクション可能か？（情報提供に留まるか）
   情報のみ → REPORT_ONLY

迷ったら安全側（REPORT_ONLY > NEEDS_JUDGMENT > AUTO_FIX の順で保守的）に倒す。
```

## 参照しているスキル

- `doc-audit`（`references/checks.md`）— docs ⇔ docs の不整合分類
- `context-audit`（`references/rule-catalog.md`）— 指示ファイル・メモリの CA-* ルール分類
