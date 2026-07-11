---
name: review-testing
description: テストスイート自体の品質を三層（欠陥検出力・契約検証・安全網の安定性）で評価し、testing-anti-patterns の 5 鉄則を三値判定付きの検出述語として執行する focused レビュー。プロダクトコードではなくテストコードを第一級の入力として扱う（codebase-review が構造的に除外する `*.test.*` を主対象にする）。総合点は出さず、findings + coverage ledger を成果物とする read-only レビュー。「テスト品質レビュー」「テストの品質を見て」「テストアンチパターン検出」「このテストは意味があるか」「テストの欠陥検出力」「安全網として機能しているか」「review-testing」で起動。依存やセキュリティではなくテスト自体の健全性が対象。
---

# Review: Testing Quality

テストスイートを「それ自体が安全網として機能しているか」という観点で評価する focused レビュー。
コードベースの設計原則が Testability 最優先である以上、テストの品質は最重要の検証対象だが、
`codebase-review` は `*.test.*` を対象から構造的に除外している。本スキルがその空白を埋める。

**対象**: テストファイルと、それが守るべきプロダクトコードの対応関係。テストコードを第一級入力として読む。
**非対象**: 依存ライブラリの健全性（→ `review-deps`）、攻撃シナリオ（→ `attack-review`）、
プロダクトコード自体の品質スコアリング（→ `codebase-review`）。

## 契約（最初に宣言する）

- **read-only**: ファイル編集・テストの書き換え・自動修正は一切行わない。指摘は findings として出力し、
  修正は既存の修正系ワークフロー（tdd / iterate / sweep-fix 等）へ渡す。
- **総合点を出さない**: 「テスト品質 82 点」型のスコアは出さない。成果物は findings と
  [coverage ledger](../shared/references/coverage-ledger.md)。総合点は「何を測れなかったか」を隠すため。
- **三値判定**: 各 finding は
  [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md) の
  CONFIRMED / FALSE_POSITIVE / UNCERTAIN で検証する。根拠を書けない CONFIRMED は UNCERTAIN に降格する。
- **評価範囲を必ず台帳化する**: 見た領域を `reviewed`、意図的に外した領域を `skipped`、
  ツール未対応で見られない領域を `unsupported`、証拠不足で結論できない領域を `inconclusive` として
  [coverage-ledger.md](../shared/references/coverage-ledger.md) の様式で報告する。
  finding が 0 件でも「問題なし」と「見ていない」を混同しない。

## 三層評価（+ 補助層）

テスト品質を独立した 3 つの中核層（1〜3）で評価し、補助層として可読性（4）を見る。
各層の詳細な判定基準は
[references/evaluation-criteria.md](references/evaluation-criteria.md) を参照する。

1. **欠陥検出力（P0）**: 重要な契約を壊す変更に対してテストが反応するか。
   意味のある mutant（契約を変える改変）が生存するなら finding。mutation score の点数化はしない。
2. **契約検証（P0）**: 公開 API・状態遷移・権限境界・失敗経路に対応テストがあるか。
   カバレッジ率はスコアに入れず、未到達領域の探索補助にのみ使う。
3. **安全網の安定性（P1）**: 時刻・乱数・順序・ネットワークへの暗黙依存を証拠化する（flaky の芽）。
4. **可読性（P2）**: テスト名から仕様（What）が読めるか（information-placement の原則）。

## アンチパターン執行

`rules/testing-anti-patterns.md` の 5 鉄則を、検出述語・証拠要件・三値判定に変換した執行仕様を
[references/anti-pattern-detection.md](references/anti-pattern-detection.md) が所有する。
候補抽出（grep / AST）→ データフロー確認 → 三値判定の順で、各述語に
positive / negative の [fixtures](references/fixtures/) を対応させて回帰確認できる状態にしてある。

## TDD 後付けの扱い（誤検出防止）

「今回 TDD だったか」と「テストが今有効か」は別軸。git 履歴だけからの TDD 後付け推定は
squash / rebase で崩れる弱い証拠なので UNCERTAIN 止まりにする。cycle の RED/GREEN 実行ログがあれば
CONFIRMED に昇格できる。既存バグへ後から足した回帰テスト自体は罰しない（安全網の追加を阻害するため）。

## ワークフロー

1. **対象決定**: 引数（ディレクトリ / glob / 差分）からテストファイル集合とその対応プロダクトを特定する。
   テストが 1 件も無ければ、その事実を coverage ledger の `unsupported` / `skipped` として報告して終了する。
2. **候補抽出**: anti-pattern-detection.md の検出述語で候補を機械的に集める（シェルコマンドでの検索・AST 走査）。
3. **文脈検証**: 各候補をデータフロー・call site で検証し、CONFIRMED / FALSE_POSITIVE / UNCERTAIN を付ける。
   規模が大きい場合はサブエージェントに層ごと（欠陥検出力 / 契約検証 / 安定性）の分析を委譲し、
   結果ファイルだけを集約する（メインコンテキスト節約）。
4. **三層評価**: evaluation-criteria.md に沿って各層を評価し、意味のある finding のみ残す。
5. **レポート**: [references/report-template.md](references/report-template.md) の様式で findings + coverage ledger を出力する。

## セキュリティ

- read-only を厳守する（テストの書き換え・スナップショット更新・`--update` 系の実行を禁止）。
- テスト内のフィクスチャに含まれる秘匿値（トークン・鍵・認証情報）を finding の証拠にそのまま転記しない。
- テストの実行が必要な場合も、破壊的副作用（外部 API 実行・DB 書き込み）を伴うものは実行せず静的に評価する。
