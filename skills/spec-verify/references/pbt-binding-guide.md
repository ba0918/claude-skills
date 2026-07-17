# PBT バインディング指針

bind ワークフローが条項の kind 別 payload から property-based テスト（PBT）を
生成するときの設計指針。条項の語彙・保証レベルの規範は
[clause-schema.md](clause-schema.md)、observation の形式と有効証拠の条件は
[evidence-manifest.md](evidence-manifest.md) が正本であり、本書は再定義しない。
言語の特定は [lang-detect 契約](../../shared/references/lang-detect.md)の手順で行う。

## 共通契約（言語非依存の adapter）

生成する PBT は、ライブラリを問わず次の 5 要素で構成する。各要素の導出元は
条項の kind 別 payload であり、`statement` の自然言語再解釈に依存しない。

| 要素 | 導出元 | 規則 |
|------|--------|------|
| generator | payload の入力領域（`input_domain` / `target` / `states`+`events` / subject×action×resource） | 前提条件は **filter でなく generator の構成で満たす**（後述） |
| oracle | payload の検証述語（`postcondition` / `condition` / 遷移規則 / `effect`） | **副作用なし**: ネットワークアクセス・ファイル書き込み・環境変数変更をしない |
| seed 固定と再現 | ライブラリの seed 機構 | 失敗時は seed（またはライブラリの再現トークン）を記録し、再現コマンドを残す |
| shrink | ライブラリの縮小機構 | 反例は最小化された形で報告させる（自前ジェネレータでも shrink 可能な構成を選ぶ） |
| 分布観測 | ライブラリの statistics / label 機構 | 入力が意図した領域（境界値・等価クラス）に到達しているかを観測する |

### filter 乱用の回避

前提条件を filter（assume / discard 系の機構）で満たすと、discard が増えて
valid 実行ケース数が減る。昇格条件（valid ケース数・失敗数・exit status・
skip/xfail の全条件）は
[clause-schema.md 保証レベル節](clause-schema.md#保証レベル)が正本であり、
filter 乱用は「実行したのに証拠にならないテスト」を生む。

- 前提条件は generator の構成（値域の制限・構造的な組み立て・写像）で満たす。
  例: 「ソート済み配列」は filter(isSorted) でなく「配列を生成してソートする」で作る。
- filter は、構成的に表現できない残余条件だけに限定する。
- discard 数が取得できるライブラリでは observation の `cases_discarded` に記録し
  （[evidence-manifest.md](evidence-manifest.md)）、discard が valid を圧迫していないか
  分布観測で確認する。

### 有効ケース数の確認

実行後、実行結果を observation として記録する
（フィールドと有効証拠の条件は [evidence-manifest.md](evidence-manifest.md) が正本）。
どの実行が成功証拠に数えられるか（昇格条件）は
[clause-schema.md 保証レベル節](clause-schema.md#保証レベル)が正本であるため、
生成時点で「そのテストが毎回 valid ケースを生めるか」を分布観測で確かめておく。

### テスト識別子

生成するテストの名前は、binding の `test_id` としてそのまま記録できる識別子にする
（文字集合規則は [evidence-manifest.md](evidence-manifest.md#識別子digest-の形式規則)）。
空白やシェルメタ文字を含む名前を付けない。

## kind 別の生成パターン

### invariant（`target` / `condition`）

対象データ形を生成し、不変述語を検証する最小形。

```text
property "CLAUSE-ID: condition holds for all target values":
  for_all x in gen_target():        # target の記述から導出した generator
    assert condition(x)             # condition から導出した oracle
```

### pre_post（`input_domain` / `precondition` / `operation` / `postcondition`）

入力を input_domain から生成し、precondition を構成的に満たしたうえで
operation を実行し、postcondition を検証する。

```text
property "CLAUSE-ID: postcondition after operation":
  for_all input in gen_precondition_satisfying(input_domain):
    result = operation(input)       # 対象操作の呼び出し
    assert postcondition(input, result)
```

postcondition が「入力と出力の関係」を含む場合、oracle には入力も渡す
（出力単体の性質に弱めない）。

### transition（`states` / `events` / `transitions` / `forbidden`）

状態機械テスト。ランダムなイベント列を生成し、条項の遷移表をモデルとして
実装と並走させる。

```text
property "CLAUSE-ID: implementation follows the transition table":
  for_all event_sequence in gen_sequences(events):
    model_state = initial; impl = new_implementation()
    for event in event_sequence:
      expected = lookup(transitions, model_state, event)   # guard も評価
      if expected is undefined or (model_state, event) in forbidden:
        assert impl.rejects(event)                         # 禁止・未定義遷移は拒否
      else:
        impl.apply(event)
        model_state = expected.to
        assert impl.state == model_state
```

- 状態機械テスト機構を持つライブラリではそれを使う。持たない場合は上記のように
  「イベント列の生成 + 逐次適用」で代替できる。どちらも不可能なら、その条項は
  unsupported として報告する（bind ワークフローの規則）。
- `forbidden` の検証を省略しない。許可遷移の追従だけでは禁止遷移の混入を検出できない。

### authorization（`subject` / `action` / `resource` / `context` / `effect`）

決定表テスト。判定の入力空間を組で生成し、期待 effect と実装の判定を突合する。

```text
property "CLAUSE-ID: access decision matches the clause":
  for_all (subj, act, res, ctx) in gen_tuples(subject, action, resource, context):
    expected = decide(clauses_in_scope, subj, act, res, ctx)  # deny 優先で解決
    assert authorize(subj, act, res, ctx) == expected
```

- **deny 優先の競合解決**は v1 スキーマが固定する意味論
  （[clause-schema.md](clause-schema.md#kind-別-discriminated-payload)）であり、
  oracle（`decide`）に必ず組み込む。
- allow 側の成功だけでなく、**deny されるべき組が確実に deny される**ことを検証する
  （条項の `counterexamples` を固定ケースとして併置すると境界が明確になる）。
- generator は「境界の内外」を跨ぐように構成する（対象ロール/非対象ロール、
  所有/非所有リソースの両側を生成する）。

## 言語別の例示

代表ライブラリの対応表。**例示であり、特定バージョン依存の API 詳細には踏み込まない**
（正確な呼び出し形式は対象プロジェクトに導入されたライブラリのドキュメントに従う）。

| 言語 | 代表ライブラリ | seed 再現 | shrink | 分布観測 | 状態機械テスト |
|------|---------------|-----------|--------|----------|---------------|
| TypeScript / JavaScript | fast-check | あり | あり | あり | あり（model-based） |
| Python | hypothesis | あり | あり | あり | あり（rule-based） |
| Rust | proptest | あり | あり | 限定的 | 本体には組み込みなし（companion crate またはイベント列生成で代替） |
| Go | rapid | あり | あり | あり | あり |

### TypeScript（fast-check）— 擬似コード

```text
// invariant: 「割引適用後の価格は 0 以上、元値以下」
test("PRICE-INV-001: discounted price stays within [0, original]", () =>
  assertProperty(
    forAll(genOrder(),                 // filter でなく構成で有効な注文を生成
      order => {
        const p = applyDiscount(order)
        return p >= 0 && p <= order.originalPrice
      }),
    { seed: recordedSeedOnFailure }))  // 失敗時に seed を記録・再現
```

- 分布観測はライブラリの統計・ラベル機構で行い、境界値（0 円・上限額）への到達を確認する。
- 状態機械（transition 条項）は model-based テスト機構でモデル = 条項の遷移表、
  実体 = 実装として並走させる。

### Python（hypothesis）— 擬似コード

```text
# pre_post: 「非空リストに対する pop は長さを 1 減らし、返り値は元の末尾」
@given(non_empty_lists())            # 「非空」は assume でなく generator 構成で満たす
def test_LIST_PP_003_pop_shrinks_by_one(xs):
    old_length = len(xs)
    tail = xs[-1]
    result = pop(xs)
    assert result == tail
    assert len(xs) == old_length - 1
```

- 失敗の再現はライブラリの failure database / seed 出力に従い、再現コマンドを
  observation の `command` に記録する。
- transition 条項は rule-based の状態機械テスト機構で表現できる。

### Rust（proptest）/ Go（rapid）— 簡潔に

- **Rust（proptest）**: strategy 合成で precondition を構成的に満たす。失敗時の
  regression ファイル（seed 記録）をコミット対象にするかは対象プロジェクトの規約に従う。
  状態機械テスト機構は本体には組み込まれていないため、transition 条項は
  companion crate を導入する（未導入なら利用者に選択させる — bind ワークフローの規則）か、
  「イベント列を Vec で生成して逐次適用」パターンで代替する。
- **Go（rapid）**: generator 合成と状態機械テスト機構を持つ。テスト名は
  ランナーのフィルタ引数（`-run` 相当）でそのまま指定できる形にし、binding の
  `test_id` と一致させる。
