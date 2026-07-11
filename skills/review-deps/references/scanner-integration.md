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
- **出力先を対象ツリー外にする**: scanner の stdout/stderr・JSON 出力・ログは、レビュー対象ディレクトリの
  **外**（作業用スクラッチ領域）へ書く。対象ツリー内へのリダイレクト（`> audit.json` 等を対象ディレクトリで
  実行する、`--output` を対象配下に向ける）は read-only 契約違反になる。カレントディレクトリを対象ツリーに
  置いたままリダイレクトすると一時ファイルが残るため、出力パスは常に対象外の絶対パスで指定する。
- **無効化できないとき**: そのスキャンは**実行せず** `unsupported` に倒す（レビューのために任意コードを走らせない）。
- lockfile / manifest の静的解析（[supply-chain-signals.md](supply-chain-signals.md) の述語）は
  コードを実行しないため、scanner が使えない環境でも成立する。scanner 不在時の主戦力はこちら。

## 構造化出力の最小スキーマ（解釈の指針）

scanner JSON から最低限拾う項目（実 API のフィールドは scanner ごとに異なるため、
[coverage-ledger.md](../../shared/references/coverage-ledger.md) に「解釈できなかったフィールド」を残す）:

- advisory ID（照合の一意キー）
- 深刻度（scanner の分類。severity へのマップは下記「深刻度のマッピング」に従う）
- 影響パッケージ名 / バージョン範囲 / 修正版
- 依存経路（direct / transitive。scanner が出さなければエージェントが lockfile から補完する）

## 深刻度のマッピング（scanner の分類 → 重大度）

scanner の深刻度ラベル（critical / high / moderate / low / info 等、体系は scanner ごとに異なる）を
[severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md) の BLOCK / WARN / INFO へ写像する。

**所有権**: 「脆弱性が存在するか」の判定は scanner が正本でエージェントは覆さない。一方
「重大度（BLOCK/WARN/INFO）」は、存在を前提に**到達可能性・dev/prod を重ねた相関判断**であり
エージェントが所有する。scanner の深刻度ラベルは**出発点**として使い、調整したら理由を注記する。

**既定の出発点**（調整前）:

| scanner 深刻度 | 出発点の重大度 |
|---------------|---------------|
| critical / high | BLOCK |
| moderate | WARN |
| low / info | INFO |

**調整ルール**（出発点から上下させる根拠。適用したら finding に理由を書く）:

- **dev-only 依存で prod ランタイム非到達**が確認できる → 1 段下げる（例: critical の devDependency → WARN）。
  非到達を確認できない場合は下げない（保守的に据え置く）。
- **install-time 発火**（postinstall / build.rs 等、import されなくても `install` で走る）→ 下げない。
  コード到達可能性に関係なく発火するため、dev/prod による減衰を適用しない。
- **任意コード実行・認証情報の外部送出・既知 malware** → scanner 深刻度に関わらず **BLOCK 固定**（下げない）。
- 修正版が存在しない（`fixAvailable=false` 等）ことは重大度を上げる要素ではないが、対応困難として注記する。

深刻度を写像できない（scanner が独自ラベルを出す等）場合は、その旨を
[coverage-ledger.md](../../shared/references/coverage-ledger.md) に残し、出発点表に最も近い段を注記付きで使う。
