# Report Template — review-deps

review-deps の出力様式。**総合点は出さない**。findings と
[coverage ledger](../../shared/references/coverage-ledger.md) の 2 本立てが成果物。
finding の重大度・三値判定は
[severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md) に従う。

    # Dependency Health Review — {対象}

    Scope: {manifest / lockfile / 依存 diff}
    Ecosystem: {npm / cargo / pip / go / ...}
    Scanner: {実行した scanner とバージョン、または "unavailable"}
    Contract: read-only / 総合点なし / findings + coverage ledger

## Findings

各 finding は「種別 / 重大度 / 三値 / 証拠 / 対象」を持つ。scanner 由来か相関由来かを明示する。

| # | 種別 | Severity | Verdict | 対象 (package@version) | 証拠 |
|---|------|----------|---------|------------------------|------|
| 1 | scanner: 既知脆弱性 | BLOCK | CONFIRMED | left-pad@1.0.0 | GHSA-xxxx（scanner 出力）。prod 経路から到達 |
| 2 | 相関: install script | WARN | UNCERTAIN | build-tool@2.1.0 | postinstall が難読化。静的読解では意図不明 |
| 3 | 相関: lockfile 異常 | WARN | CONFIRMED | ui-lib@3.0.0 | 同一バージョンで integrity hash が変化 |

### 詳細（CONFIRMED かつ BLOCK のみ展開）

- #1 left-pad@1.0.0 (GHSA-xxxx): scanner が既知脆弱性を報告。依存経路は prod（direct）。
  到達可能性: アプリの入力処理から到達する。優先度が高い。
  修正は review-deps のスコープ外（依存更新ワークフローへ）。

## Coverage Ledger

この節は finding が 0 件でも必須。

| 対象 | 判定 | 理由 / 昇格条件 |
|------|------|----------------|
| npm 依存（N packages） | reviewed | npm audit + lockfile 静的解析を適用 |
| 既知脆弱性照合（cargo） | unsupported | cargo audit 未導入。導入すれば reviewed に昇格 |
| メンテナ交代 | unsupported | レジストリ metadata へアクセス不可。オンライン環境で再実行すれば判定可 |
| 難読化 postinstall の真意 | inconclusive | 静的読解では意図不明。動的解析は隔離環境が必要 |

## Notes

- 既知脆弱性の存在判定は scanner が正本。エージェントは優先順位付けと相関のみ担った。
- hash / 署名の正当性はエージェント判断していない（機械検証の結果のみ採用）。
- install script は実行していない（静的読解のみ / read-only）。
