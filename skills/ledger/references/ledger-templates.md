# ledger 提示テンプレート集

合意台帳（[agreement-ledger.md](../../shared/references/agreement-ledger.md)）の各ワークフローが使う
テンプレート。台帳ファイル・CONTEXT 語彙ファイルは LLM 向け（機械検証正本）、裁定行提示・status 裁定ビューは
**人間向け**である。テンプレート内の値はすべて合成・匿名データであり、機密情報を書かない。

## 状態語 → 人間向けラベル対応表

status 裁定ビューには**生の状態語を出さない**。次の対応で変換する:

| 状態語（台帳・LLM 向け） | 人間向けラベル |
|--------------------------|---------------|
| `AGREED` | 合意済み |
| `DELEGATED` | 任せた（範囲: …） |
| `PROVISIONAL` | 暫定（再評価: …） |
| `UNDECIDED` | 未裁定 |
| `REJECTED` | 却下 |

## 台帳ファイルテンプレート（JSON・LLM 向け）

トップレベルは `schema_version` と `rows`。各行は発話サイズの主張 1 つ。extract は全行を `UNDECIDED` /
`PROVISIONAL` で生成する（`AGREED` は session の人間承認からのみ）。

```json
{
  "schema_version": 1,
  "rows": [
    {
      "id": "NAV-001",
      "revision": 1,
      "state": "UNDECIDED",
      "claim": "トップナビはグローバル固定で全画面共通とする",
      "term_refs": ["T-NAV"],
      "observations": ["既存モックにヘッダー領域がある"],
      "assumptions": ["全画面でナビが必要と仮定"]
    },
    {
      "id": "AUTH-010",
      "revision": 2,
      "state": "AGREED",
      "claim": "ログインは合成 SSO のみを受け付ける",
      "approval": {
        "row_id": "AUTH-010",
        "revision": 2,
        "digest": "<claim + term_refs から再算出される digest>",
        "session_id": "S-20260721-01",
        "actor_kind": "human",
        "prior_state": "UNDECIDED"
      }
    },
    {
      "id": "IMPL-020",
      "revision": 1,
      "state": "DELEGATED",
      "claim": "一覧画面のページング実装方式は実装側に委ねる",
      "delegation": {
        "subject": "実装エージェント",
        "operation": "ページング UI/データ取得の実装",
        "scope": "現 plan のみ",
        "expiry": "本 plan 完了時",
        "revocation": "台帳行を UNDECIDED へ戻す"
      }
    },
    {
      "id": "PERF-030",
      "revision": 1,
      "state": "PROVISIONAL",
      "claim": "初期表示は 100 件を上限に仮置きする",
      "reeval_condition": "pilot で実データ件数を観測したら再評価する"
    }
  ]
}
```

## CONTEXT 語彙ファイルテンプレート（JSON・LLM 向け）

`ledger_lint --context` が読む機械可読形式（[context-vocabulary.md](../../shared/references/context-vocabulary.md)）。

```json
{
  "schema_version": 1,
  "terms": [
    {"id": "T-NAV", "term": "ナビ", "state": "確定"},
    {"id": "T-SESSION", "term": "セッション", "state": "競合中"}
  ]
}
```

## 裁定行提示テンプレート（人間向け・session）

1 行 = 1 決定。数十秒で読めるサイズに保つ:

```
[NAV-001] トップナビはグローバル固定で全画面共通とする
  なぜ今:   画面レイアウトの前提。ここが決まらないと各画面の実装が始められない
  観測事実: 既存モックにヘッダー領域がある
  推奨:     グローバル固定（理由: 画面間の一貫性 / 覆す条件: 画面ごとに異なるナビが要ると判明したら）
  影響下流: 全画面のレイアウト・ヘッダーコンポーネント

  → OK（承認） / 違う（却下・一言理由） / 任せる（委任） / 保留（未裁定のまま）
```

高リスク行は default を無効化し明示回答を必須にする（Enter で流さない）。

## 語彙提示テンプレート（人間向け・語の裁定）

語の意味が競合しているときの 4 択:

```
語「セッション」の意味が競合しています
  候補A: ログインセッション（認証の有効期間）
  候補B: 裁定セッション（この台帳の対話 1 回）
  → 候補A / 候補B / 別語へ分離（両方を別の語にする） / 保留
```

## status 裁定ビュー テンプレート + サンプル出力（人間向け）

冒頭に決定に必要な情報だけを置き、詳細は後送り:

```
未裁定 5 件 / 高リスク 2 件

■ 停止要因（実装を止めている高リスク未裁定）
  - [AUTH-011] 認証の失敗時リダイレクト先が未裁定 → 画面遷移が決められない

■ 高リスク未裁定 上位
  1. [AUTH-011] 認証失敗時リダイレクト先
  2. [DATA-002] 永続データのスキーマ確定

■ 期限切れ委任
  - [IMPL-020] ページング実装（任せた範囲: 現 plan / 期限切れ: 本 plan 完了済み）→ 再確認

■ 次の一手
  裁定セッションを AUTH-011 → DATA-002 の順で回す

■ 再開地点
  前回セッション S-20260721-01 は NAV 系まで完了。AUTH 系が未着手
```

合意済み全件・却下・履歴はこの下に折りたたむ（人間はまず上記だけ読めば動ける）。
