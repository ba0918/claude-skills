# Scanner Integration — ecosystem scanner の実行と degradation

既知脆弱性の照合は ecosystem scanner が正本。本ファイルは「存在検出 → 実行 → 構造化出力の解釈 →
不在時 unsupported」の graceful degradation フローと、隔離実行の前提を定義する。
評価範囲は [coverage-ledger.md](../../shared/references/coverage-ledger.md) に記録する。

## エコシステム別 scanner

| エコシステム | scanner（例） | 出力 | 備考 |
|-------------|--------------|------|------|
| npm / pnpm / yarn | `npm audit --json` / osv-scanner | JSON | lockfile 必須 |
| Rust / cargo | `cargo audit --json` | JSON | RustSec advisory DB |
| Python | `pip-audit -f json` / osv-scanner | JSON | requirements / lock |
| Go | `govulncheck -json` / osv-scanner | JSON | 到達可能性解析付き |
| 汎用 | `osv-scanner --format json` | JSON | 複数エコシステム横断 |

具体的なコマンド名はプラットフォーム・環境に依存する。ここでは「advisory DB と照合する scanner を
シェルコマンドで実行し、構造化出力を解釈する」という抽象手順を定義する。

## degradation フロー

```
1. 存在検出: scanner バイナリと advisory DB / ネットワークが利用可能か確認する
     └ 無い → その照合を coverage ledger の `unsupported` に載せる（何があれば昇格するか併記）。エージェントは代替判定しない
2. 実行: install script を無効化した隔離環境で scanner を実行する（下記「隔離実行」）
3. 構造化出力の解釈: JSON を読み、advisory ID・深刻度・影響バージョン・修正版を抽出する
4. 相関へ受け渡し: 抽出した事実に、依存経路・dev/prod・到達可能性を重ねて優先順位付けする
     （優先順位付けはエージェント、脆弱性の存在判定は scanner が正本）
```

- **scanner の結果を書き換えない**: エージェントは advisory の真偽を判断しない。scanner が「脆弱」と言えば脆弱、
  出せなければ `unsupported`。false positive の可能性を注記するのは可だが、判定を覆さない。
- **ネットワーク不可**: advisory DB へアクセスできない環境では既知脆弱性照合は成立しない → `unsupported`。
  ローカルにキャッシュされた DB があればそのスナップショット時点である旨を注記して `reviewed`（鮮度は注記）。

## 隔離実行（install script を走らせない）

依存の再解決・スキャンは postinstall 等の install script を実行し得る。これはレビュー中の
任意コード実行に等しいため、次を前提とする。

- **script 無効化**: `--ignore-scripts` 相当のオプションで lifecycle script を止めて実行する。
- **隔離**: ネットワーク・書き込みを制限したサンドボックスで実行する。
- **無効化できないとき**: そのスキャンは**実行せず** `unsupported` に倒す（レビューのために任意コードを走らせない）。
- lockfile / manifest の静的解析（[supply-chain-signals.md](supply-chain-signals.md) の述語）は
  コードを実行しないため、scanner が使えない環境でも成立する。scanner 不在時の主戦力はこちら。

## 構造化出力の最小スキーマ（解釈の指針）

scanner JSON から最低限拾う項目（実 API のフィールドは scanner ごとに異なるため、
[coverage-ledger.md](../../shared/references/coverage-ledger.md) に「解釈できなかったフィールド」を残す）:

- advisory ID（照合の一意キー）
- 深刻度（scanner の分類。severity へのマップは注記付きで行う）
- 影響パッケージ名 / バージョン範囲 / 修正版
- 依存経路（direct / transitive。scanner が出さなければエージェントが lockfile から補完する）
