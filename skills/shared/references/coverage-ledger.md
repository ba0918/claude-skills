# Coverage Ledger

評価範囲台帳。レビュー系スキルが「何をどこまで見たか」を明示するための共通契約。
`review-testing` / `review-deps` をはじめとする focused レビューが出力に必ず含める。
重大度（BLOCK/WARN/INFO/PASS）と 3 値検証（CONFIRMED/FALSE_POSITIVE/UNCERTAIN）は
[severity-and-verdicts.md](severity-and-verdicts.md) が所有し、本契約はそれらと直交する
「評価範囲」の軸のみを定義する。

## なぜ必要か

総合点（「テスト品質 82 点」等）や PASS の羅列は、**何を測れなかったか**を隠す。
scanner が無かった領域、意図的に除外した領域、証拠不足で結論を出せなかった領域が、
どれも「問題なし」と同じ見た目になってしまう。coverage ledger は
「問題なし（reviewed かつ finding なし）」と「見ていない（skipped / unsupported）」を
構造的に区別し、レビューの空白を可視化する。

## The Iron Law

```
finding が 0 件でも、評価範囲が空でないことを ledger で示せない限り「問題なし」と言ってはならない。
見ていない領域は skipped / unsupported として必ず ledger に載せる。黙って落とさない。
```

## 4 値定義

| 値 | 意味 | 使い分け基準 |
|----|------|-------------|
| **reviewed** | 十分な入力と検証手段があり、実際に評価した | 対象ファイルを読み、検出述語を適用できた。finding の有無は問わない（PASS は reviewed の結果の一つ） |
| **skipped** | 意図的に評価対象から外した | スコープ外、利用者が明示除外、非対象の生成物など。**理由を必ず併記する** |
| **unsupported** | ツール・エコシステム・環境が未対応で評価不能 | scanner 不在、ネットワーク不可、レジストリ metadata 無しでメンテナ交代を判定できない等。**何があれば reviewed に昇格できるか併記する** |
| **inconclusive** | 見たが、結論を出せる証拠が足りなかった | 候補は観測したが検証述語を満たす証拠が不足。**不足している証拠を併記する** |

- 各エントリは「対象（ファイル / 領域 / エコシステム）＋値＋理由」の 3 点を持つ。
  理由のない `skipped` / `unsupported` / `inconclusive` は台帳として無効（The Iron Law に反する）。
- `reviewed` 以外は必ず理由を書く。`reviewed` も、非自明な検証手段を使った場合はその手段を記す。

## severity（PASS）との直交性

重大度の **PASS**（観点単位で問題が検出されなかった）は「評価した結果」であり、
評価範囲の軸とは別物。**PASS は `reviewed` の部分集合**として現れる。

```
reviewed  → finding あり（BLOCK/WARN/INFO） または finding なし（= PASS）
skipped / unsupported / inconclusive → そもそも PASS を名乗る資格がない
```

`skipped` な領域を PASS として報告するのは Iron Law 違反。両軸を混同しないこと。

## inconclusive（評価範囲軸）と UNCERTAIN（finding 検証軸）の別軸性

この 2 語は似ているが所属する軸が違う。混同すると「どこを見ていないか」と
「見た候補を対処してよいか」が一緒くたになる。

| 語 | 所属する軸 | 問い | 定義元 |
|----|-----------|------|--------|
| **inconclusive** | 評価範囲（本契約） | この**領域**を結論づける証拠があったか | 本ファイル |
| **UNCERTAIN** | finding 検証（3 値判定） | この**個別候補**を対処してよいか | [severity-and-verdicts.md](severity-and-verdicts.md) |

- `inconclusive` は領域に付く（例: 「非同期処理の網羅性は、実行トレースが無く inconclusive」）。
- `UNCERTAIN` は個々の finding 候補に付く（例: 「この public API がテスト専用かは call site から判断不能で UNCERTAIN」）。
- ある領域が `reviewed` でも、その中の個別候補が `UNCERTAIN` であることは両立する。逆に領域全体が
  `inconclusive` なら、その中の候補は finding として昇格させない（証拠基盤ごと欠けている）。

## report envelope への統合規約

レビューレポートは、findings セクションとは別に **Coverage Ledger セクションを必ず含む**。
最小様式:

```
## Coverage Ledger

| 対象 | 判定 | 理由 / 昇格条件 |
|------|------|----------------|
| src/**/*.test.ts（12 files） | reviewed | 全ファイルにアンチパターン述語を適用 |
| e2e/（Playwright） | skipped | 本レビューは単体テスト品質に限定（利用者指定） |
| mutation sensitivity | unsupported | mutation runner 未導入。導入すれば reviewed に昇格 |
| 非同期順序依存 | inconclusive | flaky 再現に実行トレースが必要。ログがあれば結論可 |
```

- ledger は「finding が 0 件」のときこそ最重要（空レポートとの差を作る唯一の手段）。
- 各レビュースキルは、自スキルが構造的に見られない領域を既定の `unsupported` / `skipped`
  エントリとしてテンプレートに持っておくと、報告漏れを防げる。

## この契約を使うスキルの義務

`reviewed` / `skipped` / `unsupported` / `inconclusive` のうち 3 種以上を使うスキルは、
本ファイルへ相対 md リンクを張ること（`scripts/validate_repo.py` の `CONTRACT_VOCAB` が
機械的に要求する。宣言だけで実体をインライン再発明するドリフトを止めるため）。
