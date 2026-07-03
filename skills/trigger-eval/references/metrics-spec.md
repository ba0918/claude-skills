# metrics-spec — trigger-eval メトリクス厳密定義

`aggregate_metrics.py` とその unittest が実装する式の唯一の正典。フィクスチャの期待値はこの式から手計算する。判定は非決定的だが、集計は判定結果 JSON に対して決定的なので、テストは手書きの判定結果 JSON をフィクスチャにする。

## ケース JSON スキーマ

```json
{"case_id": "str", "gold": "skill-name | none", "judgments": ["j1", "j2?"]}
```

- **メトリクス（TP/FN/FP・confusion・specificity・invalid_rate）は j1 のみを正とする**。`(j1, j2)` のペアは **stability 専用**。
- INVALID 正規化は判定単位で適用する（j1 と j2 に独立に）。

## ラベル空間

正規化済み bare skill name の集合 + `none` + `INVALID`（集計専用バケット）。

## 判定の正規化（カウント側）

判定が (a) パース不能、(b) 一覧外のスキル名、(c) 複数スキル、のいずれかなら `INVALID`。**INVALID の生成規則は judge-protocol.md 所掌**（1 回だけ再判定してから確定）。本書はカウント方法のみを所掌する。`aggregate_metrics.normalize_judgment(j, valid_labels)` は不変条件の最終防波堤: `valid_labels = set(skills) | {none}` に無い値・list・None は全て `INVALID`。

## per-skill 集計

スキル S について（判定は j1）:

- **TP** = (gold=S ∧ j1=S)
- **FN** = (gold=S ∧ j1≠S)  — none・他スキル・INVALID を含む
- **FP** = (gold≠S ∧ j1=S)  — gold=none・gold=他スキルの両方を含む
- **recall(S)** = TP / (TP + FN)
- **precision(S)** = TP / (TP + FP)
- **TP+FP=0 のとき precision(S) は undefined**（`None`）とし、macro precision の平均から除外する（fixture に本ケースを含める）。

## 全体集計

- ヘッドライン指標は **macro 平均**:
  - macro recall = recall が defined なスキル（=gold ケースを 1 件以上持つ）で平均
  - macro precision = precision が defined なスキル（TP+FP>0）で平均
- 参考として **micro** も併記: micro recall = ΣTP / Σ(TP+FN)、micro precision = ΣTP / Σ(TP+FP)。

## none の扱い（specificity）

none は recall/precision の行を持たない。

- **specificity** = (gold=none ∧ j1=none) / (gold=none 全件)
- gold=none ∧ j1=S の誤りは **S の FP** に帰属する。
- gold=none ∧ j1=INVALID は specificity の**分母に含め分子に含めない**。
- gold=none ケースが 0 件なら specificity = `None`。

## invalid_rate

- **invalid_rate** = (j1=INVALID の判定数) / 全ケース数。
- INVALID は正解スキルの **FN に数え、どのスキルの FP にも数えない**。
- ケース 0 件なら 0.0。

## stability

- **stability** = 同一ケース `(j1, j2)` の完全一致率（正規化ラベルで比較。INVALID 同士も一致とみなす）。
- **イテレーション横断の推移系列は常に固定サンプル部分集合上で計算する**（母集団を揃えて系列比較可能にするため）。`aggregate(cases, skills, stability_sample_ids=[...])` でサンプルを制限する。全数 2 判定するイテレーション 1 も、系列用の値はサンプル部分集合に制限して算出（全数値は参考として別掲）。
- j2 を持つケースが 0 件なら value = `None`、sample_size = 0。**sample_size は常に明記する**。

## confusion matrix

- 行 = gold、列 = j1（`none` / `INVALID` 列を含む）。出力は**非ゼロセルのみ**（全行列ダンプはしない）。
- **ペアランキング**:
  - `raw(A,B)` = count[gold=A, j1=B] + count[gold=B, j1=A]（降順が主キー）
  - `related_cases(A,B)` = **gold ラベルが A または B のケース総数**
  - `normalized(A,B)` = raw / related_cases（併記。ケース投入数の偏りで上位が歪むのを防ぐ）
  - raw=0 のペアは出力しない。ソートは (raw desc, normalized desc, a, b)。
- ペア空間は `skills ∪ {none}`（INVALID はペアの構成要素にしない）。

## 悪化ガードの defined 遷移規約

per-skill precision が defined ↔ undefined を跨いで遷移したイテレーションでは、そのスキルの **precision 項は 5pt 悪化ガードの比較対象外**（non-comparison）。recall・specificity・invalid_rate はケース集合固定のため常に比較可能。この規約は改稿ループ（SKILL.md Phase 6）が適用するものであり、`aggregate_metrics.py` は per-skill precision の defined/undefined（`None`）を報告するに留める。

## ゼロ除算規約（まとめ）

| 指標 | 分母 0 のとき |
|------|-------------|
| recall(S) | TP+FN=0 → `None`（macro recall から除外） |
| precision(S) | TP+FP=0 → `None`（macro precision から除外） |
| specificity | gold=none 0 件 → `None` |
| invalid_rate | ケース 0 件 → `0.0` |
| stability | j2 ありケース 0 件 → `None`（sample_size=0） |
| normalized(A,B) | related 0 → `0.0` |
