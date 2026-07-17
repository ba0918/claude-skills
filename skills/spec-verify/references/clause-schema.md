# 条項スキーマ v1（語彙の正本）

spec-verify が扱う条項ファイルのスキーマ定義。**この文書が唯一の正本**であり、
[spec-clause.schema.json](spec-clause.schema.json) は外部エディタ・対象プロジェクト向けの
射影にすぎない（スクリプトは実行時に schema.json を読まない）。
正本・コード・射影の drift は同期テストが機械的に防止する。
同期テストは **(1) 本文書の表 ⇔ `spec_lint` のコード内定数、
(2) コード内定数 ⇔ [spec-clause.schema.json](spec-clause.schema.json) の
required / enum / pattern / payload 必須キー、の三者を突合する**
（表 ⇔ 定数、定数 ⇔ schema.json の 2 辺で 3 者が閉じる）。

**表のパース契約**: 同期テストは見出し（節名）で表を特定する。パース対象の節:
「ファイル構造」「共通 envelope」「kind 別 discriminated payload」「ID・revision 規則」
「exit code 契約（spec_lint / trace_matrix 共通）」。
**節名を変更する場合は同期テストも同時に更新する**こと。
データ行の判定は「行頭が `|` で、先頭セル（または第 2 セル）が
バッククォート付きトークンである行」。
各表の**列順を変更する場合も同期テストを同時に更新する**こと。
型トークンは `string` / `integer` / `object` / `array[string]` / `array[object]`、
必須トークンは `required` / `optional` に固定する。
「kind 別 discriminated payload」の `transitions` / `forbidden` の説明セルにある
「`from` / `event` / `to`（必須、string）と `guard`（任意、string）」という prose 形式も
同期テストの突合対象である（ネスト規則のフィールド名と必須/任意をこの形式から読み取る）。
「exit code 契約」節では、入力上限表（第 2 セルが値、第 3 セルが破損カテゴリ）と、
破損カテゴリの箇条書き（`- ` + バッククォート付きスラッグで始まる行）を突合対象とする。

## ファイル構造

条項ファイルのトップレベルは次の 2 キーのみを持つ object とする:

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `schema_version` | `integer` | `required` | ファイルレベルのスキーマ版数。v1 は `1` 固定。未知の値は入力破損として扱う（exit 2） |
| `clauses` | `array[object]` | `required` | 条項（共通 envelope）の配列 |

`schema_version` を条項単位でなく**ファイルレベル**に置くのは、
1 ファイル内で版数が混在する状態を構造的に禁止するため。

トップレベルが object でない入力、およびトップレベル必須キーを欠く入力は
ファイル構造の破損であり、`schema_version` 未知と同様に
**入力破損として扱う（exit 2）**。条項単位の違反検出（exit 1 相当）には進まない。

## 検証の共通規則（未知キー・非空）

本スキーマの全 object（トップレベル・envelope・payload・`transitions` / `forbidden` の
各要素）に共通して適用する規則。各表の個別セルには繰り返さない（固定注記）:

- **未知キーは fail-closed（違反）**: envelope・payload とも、各表に列挙されていない
  キーを持つ入力は違反として検出する（射影では `additionalProperties: false` に相当）。
  typo されたキーがサイレントに無視され「書いたつもりの契約が存在しない」状態に
  なる事故を防ぐため。
- **string は非空**: 非空要件（`minLength 1` 相当）の対象は、各表で型トークンが
  `string` のすべてのフィールドと `array[string]` のすべての要素である。
  必須・任意を問わない。「値なし」は空文字列でなく**キー自体の省略**で表現する
  （任意フィールドのみ可。必須フィールドの空文字列は欠落と同じ違反）。

## 共通 envelope

すべての条項が持つフィールド。`payload` 以外は kind に依存しない。

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `id` | `string` | `required` | 条項 ID。「ID・revision 規則」のパターンに従う namespace 付き ASCII 識別子。ファイル内で一意 |
| `revision` | `integer` | `required` | 正整数（1 以上）。意味変更のたびに +1 する単調増加カウンタ |
| `kind` | `string` | `required` | 検証意味論の種別。enum: `invariant` / `pre_post` / `transition` / `authorization` |
| `statement` | `string` | `required` | 人間向けの宣言文（自然言語）。digest 算出対象外（文言修正で証拠が失効しない） |
| `payload` | `object` | `required` | kind 別 discriminated payload（次節）。テスト生成と digest 算出はこの payload に基づき、statement の自然言語再解釈に依存しない |
| `rationale` | `string` | `optional` | この契約が必要な理由・背景 |
| `examples` | `array[string]` | `optional` | 条項を満たす具体例。**合成・匿名データ限定**（「機密情報の規約」節参照） |
| `counterexamples` | `array[string]` | `optional` | 条項に違反する具体例。同上 |
| `refs` | `array[string]` | `optional` | 外部仕様（OpenAPI / JSON Schema 等）への参照。**不透明な識別子/URI として保存し、スクリプトは dereference しない**（開かない・取得しない・存在確認もしない） |
| `superseded_by` | `array[string]` | `optional` | 後継条項 ID の配列。**このキーが存在する条項は tombstone**（ライフサイクル節参照）。空配列は「後継なしの廃止」 |
| `predicates` | `array[string]` | `optional` | escape hatch: ホスト言語述語への参照。**不透明文字列**であり、スクリプトは import・eval・実行・存在確認をしない。述語参照そのものは証拠に寄与せず、保証レベルは通常どおり observation からのみ算出される |

## kind 別 discriminated payload

`payload` の必須キーは `kind` で決まる。bind ワークフローはこの payload から
テストを生成する（statement を再解釈しない）。

| kind | フィールド | 型 | 必須 | 説明 |
|------|-----------|-----|------|------|
| `invariant` | `target` | `string` | `required` | 不変条件が対象とするデータ形の宣言的記述 |
| `invariant` | `condition` | `string` | `required` | 対象に対して常に成り立つべき不変述語の宣言的記述 |
| `pre_post` | `input_domain` | `string` | `required` | 入力領域の記述（ジェネレータ設計の基礎になる） |
| `pre_post` | `precondition` | `string` | `required` | 事前条件 |
| `pre_post` | `operation` | `string` | `required` | 対象操作の識別・記述 |
| `pre_post` | `postcondition` | `string` | `required` | 事後条件 |
| `transition` | `states` | `array[string]` | `required` | 状態集合（1 要素以上） |
| `transition` | `events` | `array[string]` | `required` | イベント集合（1 要素以上） |
| `transition` | `transitions` | `array[object]` | `required` | 許可遷移。各要素は `from` / `event` / `to`（必須、string）と `guard`（任意、string）を持つ |
| `transition` | `forbidden` | `array[object]` | `optional` | 禁止遷移。各要素は `from` / `event`（必須、string）を持つ |
| `authorization` | `subject` | `string` | `required` | 主体（ロール・属性の記述） |
| `authorization` | `action` | `string` | `required` | 操作 |
| `authorization` | `resource` | `string` | `required` | 対象リソース |
| `authorization` | `context` | `string` | `optional` | 文脈条件（時間帯・所有関係等） |
| `authorization` | `effect` | `string` | `required` | enum: `allow` / `deny` |

**authorization の競合解決規則**: 同一の (subject, action, resource) 組に
`allow` と `deny` の両方が適用可能な場合、**deny を優先**する。
この規則は条項ファイルに書くものではなく、v1 のスキーマ自体が固定する意味論である。

## ID・revision 規則

| 項目 | 規則 |
|------|------|
| `id` パターン | `^[A-Z][A-Z0-9]*(-[A-Z0-9]+)*-[0-9]{3,}$` |
| `id` の構成 | 大文字英数の namespace セグメント（1 個以上、`-` 区切り）+ 末尾に 3 桁以上の連番。**先頭セグメントは英字始まり**（`[A-Z][A-Z0-9]*`）、**中間セグメントは英数字**（`[A-Z0-9]+`、全数字のセグメントも可）。例: `LIB-INV-001`, `CHAT-USAGE-042` |
| `id` の一意性 | 同一ファイル内で重複禁止（lint が検出）。プロジェクト横断の一意性は運用規約 |
| `revision` | 正整数（1 以上）。意味変更（payload の変更）ごとに +1。単調増加であり rollback 禁止 |

ID は namespace 付き opaque 識別子であり、スクリプトは ID の内部構造
（セグメントの意味）を解釈しない。連番は人間の採番規約にすぎない。

## ライフサイクル（変更分類）

どの編集がどの操作に当たるかの分類表:

| 変更の種類 | id | revision | 表現方法 |
|-----------|-----|----------|----------|
| 文言修正（`statement` / `rationale` / `examples` 等、payload 以外の編集） | 維持 | 維持 | そのまま編集する |
| 意味変更（`payload` の変更） | 維持 | +1 | 同一条項の改訂として編集する |
| 廃止（後継なし） | 維持 | 維持 | `superseded_by: []` を付与して tombstone 化する |
| 分割 | 維持 | 維持 | 旧条項に `superseded_by: [新ID1, 新ID2, ...]` を付与し、新条項を追加する |
| 統合 | 維持 | 維持 | 統合される各旧条項に `superseded_by: [統合先ID]` を付与する |

### tombstone 規則

- `superseded_by` キーが存在する条項が tombstone。**tombstone の削除は違反**
  （履歴の断絶）。ただし lint が検出できるのは、削除された ID への参照が
  他の条項の `superseded_by` や証拠マニフェストに残っている場合のみ。
- lint が機械検出する参照整合違反: `superseded_by` の**自己参照**、
  **循環**（A→B→A）、**存在しない後継 ID への参照**。
- **集計との関係**: tombstone 条項（`superseded_by` キーを持つ条項）は
  **保証レベル算出・未検証条項検出の対象外**とし、トレーサビリティのサマリーには
  **件数のみ別掲**する（未検証件数には含めない）。廃止済みの契約が
  `unverified` を水増しして、現役条項の「見ていない」を埋没させないため。

### 単一スナップショット lint の限界（v1）

lint は現在のファイル群という単一スナップショットしか見ない。したがって
**削除済み ID の再利用**や **revision の rollback** は機械検出できない。
「ID 再利用禁止」「revision 単調増加」は **v1 では規約であり機械保証ではない**。
履歴レジストリ / VCS 比較による機械保証は v2 で扱う。

## 保証レベル

条項の保証レベルは**証拠（observation）から算出する。自己申告は禁止**
（binding の手書き追加だけでは昇格しない）。「証拠ゼロ = 見ていない」を
可視化する思想は [coverage-ledger](../../shared/references/coverage-ledger.md) と同一である。

| レベル | v1 算出 | 定義 / 算出規則 |
|--------|---------|-----------------|
| `unverified` | 算出可（既定） | 有効な証拠がゼロ。「問題なし」ではなく「見ていない」を表す |
| `example_only` | 算出可 | 具体例ベースのテストの成功 observation が 1 件以上 |
| `property` | 算出可 | property テストの observation で、**valid（discard を除く）実行ケース数 ≥ 1 かつ失敗 0 かつ exit 0** |
| `model_checked` | 予約 | v1 では対応する検証可能な証拠種別がないため受理しない（warning + `unverified` 扱い） |
| `proved` | 予約 | 同上 |

- 「実行ケース数」は **valid ケース数**（discard を除く）を指す。
  skip / xfail / valid ケース 0 件 / exit 非 0 / 失敗数 > 0 の observation は
  成功証拠に数えない。
- **前方互換規則**: 未知・未対応の証拠種別を持つ observation は
  warning を出して最下位（`unverified`）扱いとし、**エラーにしない**。
  将来の証拠種別追加で旧スクリプトが壊れないようにするため。

## 配置規約（対象プロジェクト側）

| 対象 | パス | 扱い |
|------|------|------|
| 条項ファイル | `specs/clauses/*.json` | コミット対象（正本） |
| 証拠マニフェスト | `specs/evidence/manifest.json` | コミット対象 |
| 生成マトリクス | stdout / 一時領域 | ephemeral。コミットしない |
| draft（未承認条項） | `.agents/artifacts/spec-verify/drafts/` | 正本ツリーから隔離（[artifact-store 契約](../../shared/references/artifact-store.md)準拠）。lint / trace の探索対象外。承認（apply）時に `specs/clauses/` へ移す |

draft を正本ツリーに置かないのは、無承認の条項が lint / トレーサビリティ集計に
混入して「承認済みの契約」として扱われる事故を構造的に防ぐため。

## exit code 契約（spec_lint / trace_matrix 共通）

両スクリプトはこの契約を共有する。定義はこの表が一箇所の正本である。

| exit | report-only（既定） | strict（`--strict`） | モード依存 |
|------|---------------------|----------------------|-----------|
| `0` | 実行成功。**検出があっても 0**（対象ゼロ件の案内も 0） | 実行成功かつ検出なし | あり |
| `1` | 発生しない | 違反・検出あり | あり |
| `2` | 入力破損・使用法エラー | 入力破損・使用法エラー | **なし（モード非依存）** |

- 警告（revision 単調性のファイル単体警告、未対応証拠種別の warning 等）は
  exit code に**影響しない**。
- 検出の有無は exit code と独立に、機械出力（JSON）の `findings_present`
  フィールドで分離して表現する。CI は exit code で、ツールは JSON で判定できる。
- exit 2 のとき、保証レベル算出とマトリクスの publish は行わない
  （診断専用出力のみ。部分結果を正本として消費させない）。

### 入力上限と破損カテゴリ（exit 2 の内訳）

入力上限は次のとおり。超過は入力破損（exit 2）として扱い、条項単位の検証
（exit 1 相当の違反検出）には進まない。値は lint 実装のコード内定数と
同期テストで突合される:

| 上限項目 | 値 | 破損カテゴリ |
|---------|-----|-------------|
| ファイルサイズ（1 ファイル） | `1000000` バイト | `file-too-large` |
| 条項数（1 ファイル） | `10000` 件 | `too-many-clauses` |
| ネスト深さ | `16` 段 | `too-deep` |

exit 2 の破損カテゴリ（機械出力 `diagnostics[].category` のスラッグ）は
次の一覧が正本である（同期テストが lint 実装の raise 箇所と突合する）:

- `invalid-json` — JSON として parse できない（空ファイル・エンコーディング破損を含む）
- `duplicate-json-key` — 同一 object 内の JSON key 重複
- `not-an-object` — トップレベルが object でない
- `missing-toplevel-key` — トップレベル必須キーの欠落
- `clauses-not-array` — `clauses` が配列でない
- `unknown-schema-version` — `schema_version` が未知（v1 は `1` 固定）
- `file-too-large` — ファイルサイズ上限超過
- `too-many-clauses` — 条項数上限超過
- `too-deep` — ネスト深さ上限超過
- `unreadable` — ファイルが読み取り不能
- `path-escape` — 対象が root 外（symlink 経由の脱出を含む）

## 機密情報の規約

`examples` / `counterexamples` / `statement` / `rationale` は
**合成・匿名データ限定**とする。実在の credential・API キー・個人情報を書かない。
lint は自由文フィールドに secret 検出を適用するが、検出時は黙って書き換えず、
報告して修正を要求する（仕様正本の無断改変はドリフトそのものだから）。

## why-not（採らなかった選択肢）

- **YAML を採らない**: 実行環境の標準ライブラリに YAML パーサがなく、
  外部依存ゼロの方針と両立しない。JSON は標準ライブラリで厳密に
  （重複キー拒否まで含めて）パースできる。
- **Markdown + frontmatter を採らない**: kind 別 payload のネスト構造・
  リスト構造（`transitions` の from/event/to 等）を frontmatter で表現するには
  表現力が不足し、結局 JSON 相当の構造を埋め込むことになる。
  可読性は statement / rationale と逆生成ドキュメントで担保する。
