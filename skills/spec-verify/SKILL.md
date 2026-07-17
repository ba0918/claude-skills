---
name: spec-verify
description: 自然言語の仕様・ドキュメントに埋もれた検証可能な契約を条項スキーマ v1 として抽出・正本化し、property-based テスト（PBT）を生成、証拠ベースの保証レベルで仕様と実装のドリフトを機械検知する。第 1 引数でワークフローを指定 - formalize（契約抽出・条項化）/ bind（条項から PBT 生成）/ drift-check（lint + トレーサビリティ検査）/ self-test（mutation による検出力測定）。引数なしは specs/ がなければ導入案内（formalize へ）、あれば drift-check を実行する。「spec-verify」「仕様検証」「契約抽出」「ドリフト検知」「条項化」「PBT 生成」で起動。review-testing は既存テストスイートの品質評価、doc-check は docs⇔code の整合を所有するのに対し、spec-verify は契約の正本化と条項⇔実行証拠の binding・ドリフト機械検知を所有する。
---

# spec-verify — 軽量形式仕様（契約抽出・PBT 生成・ドリフト検知）

自然言語の中に埋もれている「検証可能な契約」を機械可読な条項として正本化し、
条項から property-based テストを生成し、条項⇔実行証拠のトレーサビリティで
ドリフトを機械検知する軽量仕様検証スキル。独自 DSL は導入せず、構造化 JSON
（[条項スキーマ v1](references/clause-schema.md)）を正本とする。

## 責務境界（兄弟スキルとの棲み分け）

| スキル | 所有する領域 |
|--------|-------------|
| **spec-verify**（本スキル） | プロダクト条項の正本化・条項からのテスト生成・条項⇔実行証拠の binding とドリフト機械検知 |
| review-testing | 既存テストスイート自体の品質**評価**（欠陥検出力・安定性） |
| doc-check | docs⇔code の整合検証 |
| tdd | 開発プロセスとしてのテストファースト |

## 二層構造の宣言

機械可読な形式正本（`specs/clauses/*.json`）が持つのは**検証可能な契約のみ**。
意図・判断基準・品質・例外の説明は自然言語ドキュメントが正本であり、
条項側には `statement` / `rationale` として要約参照のみを置く。
両層の役割を交差させない（契約を散文に埋めない・散文を条項に押し込まない）。

## ワークフロー

第 1 引数でワークフローを分岐する:

| 引数 | ワークフロー |
|------|-------------|
| `formalize` | 自然言語→条項化（スコープ指定必須・承認プロトコル付き） |
| `bind` | 条項の kind 別 payload → PBT 生成 + binding 追記（preview → apply） |
| `drift-check` | lint + トレーサビリティ検査 + observation 更新 |
| `self-test` | mutation による生成テストの検出力測定 |
| （なし） | `specs/` がなければ導入案内（→ formalize）、あれば drift-check |

> **プレースホルダ**: 各ワークフローの詳細手順（承認プロトコル・draft 隔離・
> 書き込み境界・段階導入・ゼロからの導入手順）は Step 4 で執筆する。
> 現時点では条項スキーマ v1 の正本化が完了している。

## References

- [条項スキーマ v1（語彙の正本）](references/clause-schema.md) — envelope / kind 別 payload / ID・revision 規則 / 保証レベル / 配置規約 / exit code 契約
- [spec-clause.schema.json](references/spec-clause.schema.json) — 外部エディタ・対象プロジェクト向けの JSON Schema 射影（スクリプトは実行時に読まない）
- [conformance corpus](references/fixtures/README.md) — valid / invalid の適合性検証コーパス
