# Checker Subagent Protocol

独立した checker subagent による要件採点の起動契約。
3 役分離（チューナー / 実行者 / checker）の核心。

## なぜ分離するか

実行者が自己採点すると、指示が曖昧なほど甘く解釈して ○ を付ける。
測りたい対象（曖昧さ）が採点者のバイアス源になる自己矛盾を構造的に排除する。

## Checker に渡すもの

1. **実行者の成果物**（コード / 出力 / 生成物のテキスト）
2. **要件チェックリスト**（`[critical]` タグ付き）
3. **fixture の入力範囲宣言**（統合 fixture の場合、成果物として渡す artifact の集合を明示）

## Checker に渡さないもの

- **対象プロンプト本文** — プロンプトへの「善意の解釈」を防ぐ
- **実行者の摩擦報告** — 採点に実行者の言い訳が混じるのを防ぐ
- **前回 iteration の結果** — 独立した判断を保証
- **リポジトリ本体・ソースツリー全体** — 成果物ではなく実装を読みに行くと採点対象が反転する（`isolation_violation`）

## 統合 fixture の入力範囲宣言

skill 間 handoff や複数 artifact をまたぐ「統合 fixture」では、fixture 自身が
「checker に渡さなければ評価不能な artifact 集合」を明示する必要がある。
明示しない fixture は、たとえ動作しても再現性が壊れる（元 issue #4 の失敗モード）。

各統合 fixture には次のフィールドを含める:

```json
{
  "fixture_kind": "integration",
  "input_range": {
    "consumer": "<consumer artifact パス or 埋め込み>",
    "reference": "<reference artifact パス or 埋め込み>"
  },
  "input_range_required": ["consumer", "reference"]
}
```

- `input_range_required` に列挙された鍵は checker への入力に **必ず全て**含める
- 一部だけを渡した状態で評価すると `input_range_violation` として harness error
  にすること（candidate failure と混同しない）
- 単一 artifact のみで評価可能な fixture では `fixture_kind: "unit"` とし、
  `input_range_required` は省略してよい

### 実装ガイド

- harness は checker を dispatch する直前に `validate_input_range(dispatch_keys, input_range_required)` を呼び、`(False, "input_range_violation")` が返れば dispatch を中止して
  `harness_error.type = "input_range_violation"` で当該 iteration を記録する
- checker 側テンプレートには "以下の artifact **のみ**を根拠にすること。ここに
  無いソースを開いてはならない" と明記する（isolation の宣言）

## Protocol failure と candidate failure の分離

checker の返答は「候補プロンプトの失敗」と「checker/harness 側の逸脱」を必ず区別する。
両者を混同すると、checker のバグが candidate の precision を下げ、iteration の
学習信号が汚染される（元 issue #4 の主因）。

| チャネル | 意味 | どこに記録するか |
|---------|------|-----------------|
| candidate failure | 要件が満たされなかった（`result: fail`） | `scenarios[].checker_grades` |
| protocol failure | checker/harness 側の逸脱（下表参照） | `scenarios[].harness_error` |

### Protocol failure 分類（`PROTOCOL_FAILURE_TYPES`）

| type | トリガー |
|------|---------|
| `malformed_output` | checker 出力が JSON として parse 不能 / 期待 schema と不一致 |
| `missing_grade` | checklist の全要件を採点していない |
| `extra_grade` | 存在しない要件番号に対する grade が含まれる |
| `duplicate_grade` | 同一要件番号が複数回採点されている |
| `invalid_result_value` | `result` が `pass` / `fail` / `partial` 以外 |
| `empty_checklist` | 呼び出し側が空の checklist を渡した（fixture ロード不良の指標） |
| `isolation_violation` | 成果物ではなくリポジトリ本体を調査した（ログ・宣言・出力から検出） |
| `input_range_violation` | 統合 fixture の `input_range_required` に対して欠落入力で dispatch した |

これらは `scripts/convergence.py` の以下の関数で検出する:
- `validate_checker_output()` — grades の構造・`evidence` 非空・`isolation_note` 存在（integration fixture 時）を検証
- `validate_input_range()` — dispatch 前に `input_range_required` の欠落を検出
- `has_protocol_failure()` — iteration record 内の `harness_error.type` を判定

### Safe-stop（評価不能時の安全停止）

`resolve_exit_verdict()` は最新 iteration に protocol failure があると
`halt` を返す。`resolve_halt_reason()` は `checker_protocol_failure` を返し、
`iteration.halt_reason` に記録する。

- protocol failure iteration は **precision 集計から除外**する（candidate の失敗ではない）
- 収束判定 (`is_converged`) / 発散判定 (`is_diverged`) にも寄与させない
- 再開手順:
  1. harness_error の type に応じて harness / fixture / checker テンプレートを修正
  2. baseline チェックリストの sha256 は保持したまま、当該 iteration を破棄
  3. 次 iteration を新規サブエージェント で dispatch する

> **NG**: protocol failure を「checker がそう言ったから fail」として precision を
> 下げてしまうと、prompt 側を直しても改善しない偽の回帰として現れ、iteration
> ループが空回りする。必ず harness error として分離する。

## Checker への指示テンプレート

```
あなたは独立した採点者です。成果物が要件チェックリストを満たしているかを判定します。

## 成果物
<実行者の成果物をここに貼る>

## 統合 fixture の入力範囲（該当する場合）
以下の artifact **のみ**を根拠にすること。ここに列挙されていないソース
（リポジトリのファイル、ネット、他 iteration の成果物）を開いた場合は、
その旨を "isolation_note" フィールドで自己申告してください。
- consumer: <...>
- reference: <...>

## 要件チェックリスト
0. [critical] <要件テキスト>
1. <要件テキスト>
...

## タスク
各要件について以下を判定し、JSON で返答してください:
- requirement_index: 0-origin の整数
- result: "pass" | "fail" | "partial"
- evidence: 成果物のどの部分が根拠か（1 行）

## 出力形式（厳密。逸脱は harness error として扱われる）
{
  "grades": [
    { "requirement_index": 0, "result": "pass", "evidence": "..." },
    { "requirement_index": 1, "result": "fail", "evidence": "..." }
  ],
  "isolation_note": null
}

- grades は checklist の全要件を過不足なく含めること
- 各 grade の `evidence` は非空文字列であること（`validate_checker_output()` が検証する）
- `fixture_kind == "integration"` の場合、`isolation_note` キーは必須（値は `null` 可）
- 追加のトップレベルキー（例: `--output` 用の値、コメント）は付けない
- 迷った場合でも上記 3 値以外の result を返さない
```

## 精度の算出（チューナー側）

checker の grades を受け取り、チューナーが算出:
- `pass` = 1.0, `partial` = 0.5, `fail` = 0.0
- 精度 = 合計 / 要件数
- 成功判定: `[critical]` 付き要件が**全て pass** のとき成功

## 2 チャネル融合ルール

チューナーは checker の採点と実行者の摩擦報告を突き合わせて次 iteration の修正を決める:

| checker の結果 | 実行者の摩擦報告 | チューナーの行動 |
|---------------|----------------|----------------|
| fail あり | 関連する摩擦あり | 摩擦を手がかりにプロンプトを修正 |
| fail あり | 関連する摩擦なし | 実行者が気づかず誤った = 指示が暗黙の前提を含む。前提を明示 |
| pass | 摩擦あり | 指示は結果的に正しいが分かりにくい。明瞭性を改善 |
| pass | 摩擦なし | 改善不要（収束シグナル） |
