---
name: review-deps
description: 依存ライブラリの健全性をレビューする focused スキル。既知脆弱性の照合は ecosystem scanner（npm audit / cargo audit / osv-scanner 等）を正本とし、エージェントは相関分析（dev/prod・到達可能性による優先順位付け、install script の意味づけ、lockfile diff の異常検知、typosquat・メンテナ交代等のサプライチェーン信号）を担う。manifest / lockfile / 依存 diff を第一級入力として扱う（codebase-review が除外する lockfile が主対象）。scanner 不在・ネットワーク不可は unsupported として台帳化する read-only レビュー。「依存レビュー」「依存関係の脆弱性を見て」「lockfile をチェック」「サプライチェーンリスク」「npm audit の結果を整理して」「typosquat 検出」「依存の健全性」「review-deps」で起動。テスト品質やコード品質ではなく依存の健全性が対象。
---

# Review: Dependency Health

依存ライブラリの健全性を継続的ヘルスの観点でレビューする focused スキル。
既知脆弱性の照合は機械（scanner）が正本で、エージェントの価値は**相関分析**にある。
`codebase-review` が構造的に除外する lockfile・manifest・依存 diff を第一級入力として扱う。

**対象**: manifest（package.json / Cargo.toml 等）・lockfile・依存の更新差分・install script。
**非対象**: 攻撃シナリオの網羅（→ `attack-review`）、テスト品質（→ `review-testing`）、
アプリケーションコードの品質（→ `codebase-review`）。

## 契約（最初に宣言する）

- **read-only**: `npm audit fix` / `cargo update` / lockfile 再生成のコミット等、依存を変更する操作は禁止。
  findings として出力し、修正は既存の修正系ワークフローへ渡す。
  **レビュー対象ディレクトリへの書き込みも一切禁止する**（依存の変更だけでなく、scanner の出力ファイル・
  一時ファイル・ログを対象ツリー内に作ることも含む）。scanner の stdout/stderr は必ず対象外の作業領域
  （スクラッチディレクトリ）へリダイレクトする。read-only の遵守は「レポートでそう宣言したか」ではなく
  「対象ディレクトリの状態が実行前後で不変か」で判定される — 一時ファイルの取り残しも違反にあたる。
- **機械が正本、エージェントは相関**: 既知事実（advisory 照合・checksum・署名検証）は scanner と
  機械検証の結果のみを採用する。**hash / 署名の正当性をエージェントが「読んで判断」してはならない**。
  エージェントは scanner が出せない相関（依存経路・到達可能性・dev/prod・diff の意味づけ）を担う。
- **総合点を出さない**: 「依存健全性 80 点」型のスコアは出さない。成果物は findings と
  [coverage ledger](../shared/references/coverage-ledger.md)。
- **三値判定**: 各 finding は
  [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md) の
  CONFIRMED / FALSE_POSITIVE / UNCERTAIN で検証する。
- **評価範囲を必ず台帳化する**: scanner で確認できた領域を `reviewed`、対象外にした依存群を `skipped`、
  scanner 不在・ネットワーク不可・レジストリ metadata 無しで見られない領域を `unsupported`、
  候補はあるが証拠不足の領域を `inconclusive` として
  [coverage-ledger.md](../shared/references/coverage-ledger.md) の様式で報告する。

## 役割分担

| 担当 | 領域 | 根拠 |
|------|------|------|
| **scanner（正本）** | 既知脆弱性の advisory 照合、checksum / integrity 検証 | [references/scanner-integration.md](references/scanner-integration.md) |
| **エージェント（相関）** | 優先順位付け（dev/prod・到達可能性）、install script の意味づけ、lockfile diff 異常、typosquat・メンテナ交代 | [references/supply-chain-signals.md](references/supply-chain-signals.md) |

scanner が出した advisory を、エージェントが「この依存は dev のみ / テスト経路からしか到達しない」等の
文脈で優先順位付けする。scanner が無い環境では既知脆弱性照合は `unsupported`（エージェントは代替しない）。

**深刻度の所有権**: 脆弱性の**存在**判定は scanner が正本で覆さない。一方 finding の**重大度**
（BLOCK/WARN/INFO）は、存在を前提に到達可能性・dev/prod を重ねた相関判断としてエージェントが決める。
scanner 深刻度ラベルからの写像ルールと調整根拠は
[references/scanner-integration.md](references/scanner-integration.md) の「深刻度のマッピング」に従う。

## ワークフロー

1. **入力特定**: manifest / lockfile / 依存 diff を集める。エコシステム（npm / cargo / pip / go 等）を判定する。
2. **scanner 実行（graceful degradation）**: 「存在検出 → 実行 → 構造化出力の解釈 → 不在時 unsupported」。
   詳細と隔離実行の前提は [references/scanner-integration.md](references/scanner-integration.md)。
3. **相関分析**: scanner の advisory に依存経路・到達可能性・dev/prod を重ねて優先順位を付ける。
   lockfile diff・install script・typosquat・メンテナ交代の信号を
   [references/supply-chain-signals.md](references/supply-chain-signals.md) の述語で検証する。
4. **三値判定**: 各候補を CONFIRMED / FALSE_POSITIVE / UNCERTAIN に振る。検出できない限界は明記する。
5. **レポート**: [references/report-template.md](references/report-template.md) の様式で findings + coverage ledger を出力する。

## セキュリティ

- **install script を走らせない前提で scanner を実行する**: 依存の再解決・スキャンは postinstall 等の
  install script を実行し得る。script 無効化（`--ignore-scripts` 相当）・隔離実行を
  scanner-integration.md で前提化する。無効化できない場合はその領域を実行せず `unsupported` に倒す。
- **秘匿情報をレポートに混入させない**: レジストリ認証情報・トークン・環境変数を findings の証拠に転記しない。
- **hash / 署名の正当性判断をエージェントに委ねない**: 機械検証（scanner / clean 環境での再生成）の結果のみを採用する。
