# conformance corpus — 条項スキーマ v1 適合性検証コーパス

[clause-schema.md](../clause-schema.md)（語彙の正本）に対する valid / invalid の
fixture 集。ハンドロール検証（`spec_lint`）と
[spec-clause.schema.json](../spec-clause.schema.json)（外部向け射影）の双方を
同一コーパスで検証し、正本と射影の乖離を防ぐ。

すべての fixture は架空の図書貸出システムを題材にした**合成データ**であり、
実在の credential・個人情報を含まない（clause-schema.md の「機密情報の規約」節）。

## 期待判定一覧

「schema 検出」列は、参照整合を表現できない JSON Schema 単体で
その違反を検出できるか（`yes` / `no`）。`no` の違反は lint のみが検出する。

### valid/

| fixture | 期待判定 | 網羅する要素 |
|---------|----------|--------------|
| `valid/invariant_minimal.json` | valid | 必須フィールドのみの最小条項（invariant） |
| `valid/all_kinds.json` | valid | 4 kind 全網羅 + rationale / examples / counterexamples / refs の任意フィールド |
| `valid/predicates_escape_hatch.json` | valid | `predicates`（escape hatch）使用例 + authorization の `context` / `allow` |
| `valid/lifecycle_superseded.json` | valid | `superseded_by` 配列の使用例（分割 tombstone・後継なし廃止の空配列）、revision > 1 |

### invalid/

| fixture | 期待判定 | 違反種別 | schema 検出 |
|---------|----------|----------|-------------|
| `invalid/unknown_kind.json` | invalid | `unknown-kind`（enum 外の kind） | yes |
| `invalid/missing_statement.json` | invalid | `missing-required`（envelope 必須フィールド欠落） | yes |
| `invalid/payload_missing_required.json` | invalid | `payload-missing-required`（kind 別 payload の必須キー欠落） | yes |
| `invalid/duplicate_id.json` | invalid | `duplicate-id`（ファイル内 ID 重複） | no |
| `invalid/dangling_superseded_by.json` | invalid | `dangling-superseded-by`（存在しない後継 ID への参照） | no |
| `invalid/self_superseded_by.json` | invalid | `self-superseded-by`（自己参照） | no |
| `invalid/cycle_superseded_by.json` | invalid | `cycle-superseded-by`（A→B→A の循環） | no |
| `invalid/nonpositive_revision.json` | invalid | `invalid-revision`（正整数でない revision） | yes |
| `invalid/bad_id_charset.json` | invalid | `invalid-id`（ID パターン違反・小文字） | yes |
| `invalid/unknown_schema_version.json` | invalid | `unknown-schema-version`（入力破損として exit 2） | yes |
| `invalid/unknown_envelope_key.json` | invalid | `unknown-key`（envelope の未知キー。fail-closed） | yes |
| `invalid/empty_statement.json` | invalid | `empty-required-string`（必須 string フィールドの空文字列） | yes |
| `invalid/non_object_toplevel.json` | invalid | `not-an-object`（トップレベルが object でない。入力破損として exit 2） | yes |
| `invalid/missing_clauses_key.json` | invalid | `missing-toplevel-key`（トップレベル必須キー `clauses` の欠落。入力破損として exit 2） | yes |

補足:

- `unknown-schema-version` / `not-an-object` / `missing-toplevel-key` は
  他の invalid（exit 1 相当の違反検出）と異なり、**入力破損（exit 2）**に分類される
  （[clause-schema.md](../clause-schema.md) のファイル構造節と exit code 契約参照）。

### corpus 化できないケースと除外根拠

次の入力破損ケースは fixture ファイルとして置かず、`spec_lint` のユニットテスト内で
文字列リテラル・生成入力として検証する:

- **壊れた JSON**（構文エラー）・**空ファイル**: JSON としてパースできないため、
  「fixture を JSON として読み込み validator に適用する」という本コーパスの
  適用手順自体が成立しない（スキーマ検証より前のパース層で exit 2 になる）。
  corpus には JSON としてパース可能な入力のみを置く。
- **重複 JSON key**: 違反がテキスト表現にしか存在せず、一般の JSON パーサでは
  パース後に消えるため、fixture ファイルとして期待判定を固定できない
  （validator 実装によって読み取り結果が変わる）。

## manifest corpus（証拠マニフェスト）

[evidence-manifest.md](../evidence-manifest.md)（証拠マニフェスト形式の正本）に対する
valid / invalid の fixture 集。`trace_matrix` のマニフェスト構造検証に CI で機械適用する。

本 corpus が検証するのは**マニフェスト単体の構造**のみである。条項ファイルとの突合が
必要な検出（dangling / stale / revision 食い違い / 保証レベル算出）は fixture では
期待判定を固定できないため、`trace_matrix` のユニットテスト内で条項ファイルと
組にして検証する。

### manifest/valid/

| fixture | 期待判定 | 網羅する要素 |
|---------|----------|--------------|
| `manifest/valid/empty.json` | valid | 空の bindings / observations（graceful 対象） |
| `manifest/valid/bound_with_observation.json` | valid | 多対多 binding（1 テスト複数条項・1 条項複数テスト）+ property / example の observation + 任意フィールド（cases_discarded / skipped / xfail） |

### manifest/invalid/

| fixture | 期待判定 | 違反種別 |
|---------|----------|----------|
| `manifest/invalid/bad_test_id.json` | invalid | `invalid-test-id`（test_id の文字集合違反。空白・シェルメタ文字） |
| `manifest/invalid/missing_observation_key.json` | invalid | `missing-required`（observation の必須キー payload_digest 欠落） |
| `manifest/invalid/unknown_binding_key.json` | invalid | `unknown-key`（binding の未知キー。fail-closed） |
| `manifest/invalid/bad_digest.json` | invalid | `invalid-digest`（payload_digest の形式違反） |
| `manifest/invalid/unknown_schema_version.json` | invalid | `unknown-schema-version`（入力破損として exit 2） |
| `manifest/invalid/bindings_not_array.json` | invalid | `manifest-key-not-array`（入力破損として exit 2） |

補足:

- `unknown-schema-version` / `manifest-key-not-array` は他の invalid
  （exit 1 相当のエントリ違反）と異なり、**入力破損（exit 2）**に分類される
  （[evidence-manifest.md](../evidence-manifest.md) の入力破損節参照）。

## 外部 JSON Schema validator による検証手順

spec-clause.schema.json と本コーパスの等価性は、draft-07 対応の任意の
JSON Schema validator で確認できる。例:

```bash
# 例 1: Python の jsonschema パッケージ（要 pip install jsonschema）
python3 - <<'EOF'
import json, pathlib
from jsonschema import Draft7Validator

base = pathlib.Path("skills/spec-verify/references")
schema = json.loads((base / "spec-clause.schema.json").read_text())
validator = Draft7Validator(schema)

for group, expect_valid in (("valid", True), ("invalid", False)):
    for path in sorted((base / "fixtures" / group).glob("*.json")):
        errors = list(validator.iter_errors(json.loads(path.read_text())))
        print(f"{path.name}: {'valid' if not errors else 'invalid'}")
EOF

# 例 2: Node.js の ajv-cli（要 npm install -g ajv-cli）
ajv validate --spec=draft7 -s skills/spec-verify/references/spec-clause.schema.json \
  -d "skills/spec-verify/references/fixtures/valid/*.json"
```

**期待結果**: `valid/` は全件 valid。`invalid/` は「schema 検出 = yes」の
fixture のみ invalid になり、「schema 検出 = no」の 4 件
（duplicate-id / dangling / self / cycle）は **schema 単体では valid と判定されるのが正しい**
（参照整合は JSON Schema の表現範囲外で、lint のみが検証する）。

## 限界（本リポジトリ CI での扱い）

本リポジトリの検証は標準ライブラリのみで動く方針のため、外部 JSON Schema
validator を CI では実行しない。CI が本コーパスを機械適用するのは
ハンドロール検証（`spec_lint`）に対してのみであり、schema.json 側の等価性は
上記手順を手元で実行して確認する運用となる。構造的な同期
（required / enum / ID pattern / payload 必須キー）は、
(1) clause-schema.md の表 ⇔ `spec_lint` のコード内定数、
(2) コード内定数 ⇔ spec-clause.schema.json、の三者を突合する同期テストが
CI で担保する（clause-schema.md の表パース契約参照）。
