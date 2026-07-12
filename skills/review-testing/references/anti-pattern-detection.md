# Anti-Pattern Detection — 5 鉄則の執行仕様

`rules/testing-anti-patterns.md` の 5 鉄則を、検出述語・証拠要件・三値判定に変換した執行仕様。
ルール本文の複製ではなく「テストコードから機械的に候補を拾い、文脈で確定する」ための手順を定義する。

各述語の判定は [severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md) の
CONFIRMED / FALSE_POSITIVE / UNCERTAIN に従う。**根拠（call site 一覧・データフロー）を書けない
CONFIRMED は UNCERTAIN に降格する**。判定できなかった領域は
[coverage-ledger.md](../../shared/references/coverage-ledger.md) の `inconclusive` に載せる。

各述語には positive（検出すべき）/ negative（誤検出してはならない）の
[fixtures](fixtures/) が対応する。**検出述語または fixture 自体を変更したときの回帰確認**に使う。
通常のプロジェクトレビューでは対象コードへ述語を直接適用し、同梱 fixture の再評価は必須ではない。

## 共通手順

```
1. 候補抽出: 述語ごとの grep / AST パターンでテストファイルから候補を集める
2. 文脈検証: データフロー・call site 全列挙で「本当に該当するか」を確認する
3. 三値判定: 根拠付きで CONFIRMED / 字面一致だが非該当なら FALSE_POSITIVE / 根拠不足なら UNCERTAIN
4. 保守ゲート（述語 / fixture 変更時のみ）: fixtures の positive を検出し negative を検出しないことを照合する
```

## AP1: モックの振る舞いをテストしている

**鉄則**: モック要素の存在をアサートしない。実コンポーネントの振る舞いを検証する。

- **候補抽出**: `*-mock` / `mock` を含む testid・要素へのアサーション、モックの戻り値をそのまま検証するアサーション。
- **証拠要件**: そのアサーションが「モックが動いたこと」しか保証しておらず、実装の振る舞いに触れていないことを、
  アサーション対象の出所（モック定義）まで辿って示す。
- **三値**: モック存在の確認だと辿れた → CONFIRMED / 実要素も併せて検証している → FALSE_POSITIVE /
  モックか実体か判別する材料が無い → UNCERTAIN。
- **fixtures**: [positive](fixtures/ap1-mock-behavior.positive.test.ts) / [negative](fixtures/ap1-mock-behavior.negative.test.ts)

## AP2: プロダクトコードにテスト専用メソッド

**鉄則**: テストからしか呼ばれないメソッドを production クラスに置かない。

- **候補抽出**: production コードのメソッドで、参照元がテストファイルのみのもの（`destroy` / `reset` / `_forTest` 等が兆候）。
- **証拠要件**: **call site を全列挙**し、production 経路からの呼び出しがゼロであることを示す。
  1 箇所でも production 呼び出しがあれば該当しない。
- **三値**: call site 全列挙で production 呼び出しゼロを示せた → CONFIRMED /
  production からも使われている → FALSE_POSITIVE /
  ライブラリの公開 API で外部呼び出しが観測範囲外 → UNCERTAIN（公開 API は罰しない）。
  **export された class / method は、対象内 call site がテストだけでも外部利用を否定できないため UNCERTAIN**。
- **fixtures**: [positive](fixtures/ap2-test-only-method.positive.ts) / [negative](fixtures/ap2-test-only-method.negative.ts)

## AP3: 理解していない依存をモックしている

**鉄則**: テストが依存する副作用をモックで消さない。

- **候補抽出**: モック対象が、同じテストが結果として依存している副作用（ファイル書き込み・重複検出・キャッシュ登録等）を持つケース。
- **証拠要件**: モックした対象の実メソッドが持つ副作用を列挙し、そのうちテストのアサーションが依存しているものを特定する。
  依存する副作用をモックが消しているなら該当。
- **三値**: 「テストが依存する副作用をモックが消している」とデータフローで示せた → CONFIRMED /
  モックしたのは真に外部・低速な処理だけ（副作用は本物が実行される）→ FALSE_POSITIVE /
  依存関係が追い切れない → UNCERTAIN。
- **fixtures**: [positive](fixtures/ap3-mock-understanding.positive.test.ts) / [negative](fixtures/ap3-mock-understanding.negative.test.ts)

## AP4: 不完全なモック

**鉄則**: 知っているフィールドだけの部分モックを作らない。実 API の完全なスキーマを再現する。

- **候補抽出**: モックレスポンスのオブジェクトと、それを消費する production コードが参照するフィールド集合の差分。
- **証拠要件**: 実 API のレスポンススキーマ（型定義・ドキュメント・サンプル）に対しモックが欠くフィールドを列挙し、
  そのうち downstream が参照するものを示す。参照されるフィールドが欠けていれば「テストは通るが統合で壊れる」。
- **三値**: downstream が参照するフィールドの欠落を示せた → CONFIRMED /
  欠落フィールドはどこからも参照されない → FALSE_POSITIVE /
  実スキーマが不明で欠落を確定できない → UNCERTAIN。
- **fixtures**: [positive](fixtures/ap4-incomplete-mock.positive.test.ts) / [negative](fixtures/ap4-incomplete-mock.negative.test.ts)

## AP5: 後付けのテスト（TDD 逸脱）

**鉄則**: テストは実装の後付けにしない（TDD 先行）。ただし検出は慎重に扱う。

- **候補抽出**: 実装コミットの後にテストが追加された痕跡（同一ファイルの追加順・PR 差分）。
- **証拠要件**: git 履歴だけは squash / rebase で崩れる**弱い証拠**。cycle の RED/GREEN 実行ログがあれば強い証拠。
- **三値**: RED/GREEN ログで先行が確認できた（順守 or 逸脱）→ CONFIRMED /
  既存バグへの回帰テスト後付けと分かる → FALSE_POSITIVE（**罰しない**。安全網追加を阻害しないため）/
  git 履歴のみで判断 → **UNCERTAIN 止まり**。
- **別軸の分離**: 「今回 TDD だったか」（本述語）と「テストが今有効か」（AP1–AP4・三層評価）は別軸。
  後付けでも現在有効なテストは層 1・層 2 で正当に評価する。
- **fixtures**: [positive](fixtures/ap5-tests-after-fact.positive.md) / [negative](fixtures/ap5-tests-after-fact.negative.md)

## 検出できない限界（明記する）

- 動的に組み立てられるモック・メタプログラミングされたテストは静的抽出をすり抜ける → その領域は `inconclusive`。
- 外部ライブラリの公開 API がテスト専用に見えるケースは常に UNCERTAIN（外部呼び出しは観測範囲外）。
- これらの限界を coverage ledger に明示し、「検出述語が届かなかった」ことを「問題なし」と混同しない。
