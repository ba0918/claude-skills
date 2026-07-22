---
name: ledger
description: greenfield の要件・仕様・ドメイン知識を人間と裁定し、現在有効な合意を状態付きの台帳として正本化する。仕様の空白を暗黙補完させず、未裁定事項を可視化したいときに使う。workflow は extract / session / status / orient。「合意台帳」「ledger」「裁定セッション」「台帳を作って」「合意を裁定して」「何が決まって何が未裁定か」で起動する。
---

# ledger — 合意台帳

現在有効な合意を状態付きで正本化し、LLM が仕様の空白を暗黙補完することを防ぐ。

## Core invariants

- LLM は提案者になれるが承認者にはなれない。`AGREED` は、人間が同一 revision の claim に明示回答した承認イベントからのみ生成する。
- 実装の根拠にできるのは `AGREED` / `DELEGATED` 行だけである。合意がなければ `UNDECIDED` として可視化する。
- headless で人間の回答が得られない場合、extract は draft preview まで、session は状態遷移なしで止める。status は読み取り専用で実行できる。

## Workflow routing

第1引数で一つだけ選ぶ。

| 引数 | 実行方法 |
|---|---|
| `extract` | 実行前に [extract-workflow.md](references/extract-workflow.md) だけを完全に読み、その手順に従う |
| `session` | 実行前に [session-workflow.md](references/session-workflow.md) だけを完全に読み、その手順に従う |
| `orient` | 実行前に [orient-workflow.md](references/orient-workflow.md) だけを完全に読み、その手順に従う |
| `status` | 下記 fast path だけで完結する。参照先を含む他ファイルを読まない |
| なし | 台帳がなければ extract を案内し、あれば status fast path を実行する |

## status fast path

status は台帳を変更しない。この節が必要事項をすべて含むため、スキーマ正本、語彙正本、テンプレート、他workflowを読まず、人間向けの短い裁定ビューを次の順で出す。

1. 停止要因（実装を止める高リスク未裁定）
2. 高リスク未裁定の上位
3. 期限切れ委任
4. 次の一手
5. 再開地点

冒頭は「未裁定 N 件 / 高リスク M 件」とし、合意済み全件と履歴は詳細送りにする。全体は1〜2スクロールに収める。内部状態語はそのまま見せず、`UNDECIDED` は「未裁定」、`DELEGATED` は「任せた（範囲: …）」のように人間向けに言い換える。入力に claim がなければ内容を補完せず、件数と不足情報だけを示す。

## Completion

変更を伴うworkflowは、実行した検証コマンド、exit code、検出件数、変更、未解決事項を報告する。status は読み取り専用であり、状態遷移や承認イベントを生成しない。
