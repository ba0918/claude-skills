# Supply-Chain Signals — 検出述語と限界

scanner が出せない相関的なサプライチェーン信号の検出述語。判定は
[severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md) の
CONFIRMED / FALSE_POSITIVE / UNCERTAIN に従い、検出できない領域は
[coverage-ledger.md](../../shared/references/coverage-ledger.md) の `unsupported` / `inconclusive` に載せる。

各述語には positive / negative の [fixtures](fixtures/) が対応する（回帰確認用）。

**大原則**: hash / 署名の正当性はエージェントが読んで判断しない。機械検証の結果のみ採用する。
本ファイルの述語は「機械が正誤を出せない、文脈依存の異常」を対象にする。

**証拠の裏取り**: finding の証拠として書く具体値（取得元 URL・書込先パス・環境変数名・resolved ホスト等の
IOC）は、対象ファイルの**該当行を実際に読んで正確に転記する**。記憶・推測・「ありがちな値」で埋めない。
特に書込先パスは「一時領域か永続領域か（`/tmp` か `$HOME` 配下か）」で脅威の性質が変わるため、
setup.js 等の該当行を引用して裏取りする。裏取りできない項目は具体値を創作せず「未確認」と明記する。

## 信号 1: lockfile diff の異常

- **候補抽出**: lockfile diff で、resolved URL がレジストリ外（別ホスト・git URL・file: 参照）に変わった、
  integrity hash が同一バージョンのまま変化した、直接依存が増えていないのに transitive が大量に入れ替わった。
- **証拠要件**: 同一バージョン指定なのに integrity が変わった等の「manifest の意図と lockfile の実体の乖離」を diff で示す。
  integrity hash 値そのものの正誤は判断せず、「同一バージョンで hash が変わった」という**機械的事実**を証拠にする。
- **三値**: 乖離を diff で示せた → CONFIRMED / 正当な理由（レジストリ移行・バージョン更新に伴う変化）が説明できる → FALSE_POSITIVE /
  diff だけでは意図が読めない → UNCERTAIN。
- **fixtures**: [positive](fixtures/lockfile-anomaly.positive.json) / [negative](fixtures/lockfile-anomaly.negative.json)

## 信号 2: install script（lifecycle script）

- **候補抽出**: manifest の `postinstall` / `preinstall` / `install`（npm）、`build.rs`（cargo）等の
  lifecycle hook。特に外部ネットワークアクセス・エンコードされたペイロード・別ファイルの実行を含むもの。
- **証拠要件**: script の**内容**が何をするかを、次の 4 項目をすべて埋める形で構造化して説明する
  （どれか 1 つでも欠けたら証拠不足として finding を UNCERTAIN に降格する）:
  1. **取得元** — 何を外部から取ってくるか（URL・ホスト・取得するバイナリ/コード）。無ければ「なし」と明記。
  2. **書込先** — どこに何を書くか（ホームディレクトリ・システムパス・実行権限付与の有無）。無ければ「なし」と明記。
  3. **参照する秘匿情報** — 読み取る環境変数・認証情報・鍵（値は転記せず名前と送出有無のみ）。無ければ「なし」と明記。
  4. **実行するコマンド** — subprocess・eval・chmod+x での実行など。無ければ「なし」と明記。

  「意味づけ」がエージェントの役割。ただし script を**実行して**確かめてはならない（静的に読む）。
- **三値**: 危険な挙動（データ送出・任意コード取得）をコード上で示せた → CONFIRMED /
  正当なビルド処理（ネイティブモジュールのコンパイル等）と説明できる → FALSE_POSITIVE /
  難読化で意図が読み切れない → UNCERTAIN（`inconclusive` 領域として ledger にも記録）。
- **fixtures**: [positive](fixtures/install-script.positive.json) / [negative](fixtures/install-script.negative.json)

## 信号 3: typosquat

- **候補抽出**: 著名パッケージ名との編集距離が小さい依存名（`lodahs` vs `lodash`、
  スコープ偽装 `@types-node` vs `@types/node`、ハイフン/アンダースコア差異）。
- **証拠要件**: 正規パッケージ名との差分と、当該依存が正規のものでない（別メンテナ・低ダウンロード・最近公開）ことを示す。
  レジストリ metadata が無い環境では「名前の類似」までしか言えない → UNCERTAIN 止まり。
- **三値**: 類似名 + 別出所を示せた → CONFIRMED / 正規のスコープ/別名だと確認できた → FALSE_POSITIVE /
  metadata 無しで名前類似のみ → UNCERTAIN。
- **fixtures**: [positive](fixtures/typosquat.positive.json) / [negative](fixtures/typosquat.negative.json)

## 信号 4: メンテナ交代 / 保守状態（限界の明記）

- **候補**: 短期間での publish 権限者の変更、長期未更新後の突然のメジャー更新、メンテナ数の急減。
- **限界**: これらはレジストリ metadata（publish 履歴・オーナー情報）が無ければ**判定不能**。
  ネットワーク不可・metadata 非公開の環境では必ず `unsupported` に載せる。エージェントが憶測で CONFIRMED にしない。

## 検出できない限界（必ず ledger に残す）

- 難読化された install script の真意 → `inconclusive`。
- レジストリ metadata を要する信号（typosquat の出所確認・メンテナ交代）→ metadata 無しなら `unsupported`。
- transitive 依存の到達可能性は、呼び出しグラフ解析が無ければ保守的に「到達し得る」とし、断定は避ける。
