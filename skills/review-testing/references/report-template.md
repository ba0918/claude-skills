# Report Template — review-testing

review-testing の出力様式。**総合点は出さない**。findings と
[coverage ledger](../../shared/references/coverage-ledger.md) の 2 本立てが成果物。
finding の重大度・三値判定は
[severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md) に従う。

    # Test Quality Review — {対象}

    Scope: {ディレクトリ / glob / 差分}
    Date: {YYYY-MM-DD HH:MM}
    Contract: read-only / 総合点なし / findings + coverage ledger
    Target integrity: {実行前後の機械確認結果、または動的評価未実行}

## Findings

各 finding は「層 / 重大度 / 三値 / 証拠 / 対象」を持つ。証拠を書けない CONFIRMED は載せない（UNCERTAIN へ降格）。

| # | 層 | Anti-Pattern | Severity | Verdict | 対象 (file:line) | 証拠 |
|---|----|--------------|----------|---------|------------------|------|
| 1 | 層1 欠陥検出力 | AP1 モック検証 | WARN | CONFIRMED | foo.test.ts:42 | モック戻り値をそのまま検証。実振る舞い未検証 |
| 2 | 層2 契約検証 | 失敗経路未検証 | BLOCK | CONFIRMED | auth.ts:88 | 拒否側のテストが存在しない（call site 列挙済み） |
| 3 | 層3 安定性 | 時刻依存 | WARN | UNCERTAIN | order.test.ts:12 | 直接 Date 参照。flaky 再現に実行トレースが必要 |

### 詳細（CONFIRMED かつ BLOCK のみ展開）

- #2 失敗経路未検証 (auth.ts:88): 認可の拒否側（権限のない主体）に対応テストが無い。
  許可側のみ検証している。証拠: denyAccess の call site とテスト参照の不在一覧。
  修正は review-testing のスコープ外（tdd / iterate へ）。

## Coverage Ledger

この節は finding が 0 件でも必須。見た範囲と見ていない範囲を区別する。

| 対象 | 判定 | 理由 / 昇格条件 |
|------|------|----------------|
| src/**/*.test.ts (N files) | reviewed | 全ファイルに 5 述語 + 三層を適用 |
| テストファイル探索範囲（0 files の場合） | reviewed | glob と探索結果を確認。テスト不在を層2の契約対応と照合 |
| e2e/ | skipped | 本レビューは単体テスト品質に限定（利用者指定） |
| mutation sensitivity | unsupported | mutation runner 未導入。導入すれば層1を reviewed に昇格 |
| 非同期順序依存 | inconclusive | flaky 再現に実行トレースが必要。ログがあれば結論可 |
| TDD 順守 | inconclusive | git 履歴のみ。RED/GREEN ログがあれば CONFIRMED 可 |

Fixture regression（検出述語 / fixture を変更したレビューでのみ記載）: {AP1〜AP4 positive=CONFIRMED / negative=FALSE_POSITIVE、AP5 positive=UNCERTAIN / negative=FALSE_POSITIVE}

## Notes

- 総合スコアは意図的に出していない（何を測れなかったかを coverage ledger が明示する）。
- 修正は行っていない（read-only）。修正系ワークフローへ引き継ぐ。
