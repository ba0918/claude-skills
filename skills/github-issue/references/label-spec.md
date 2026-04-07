# Label Specification

github-issue スキルが管理するラベルと状態遷移の網羅定義。

## Labels

| Label | 意味 | 付与タイミング | 削除タイミング |
|-------|------|---------------|--------------|
| `claude-auto` | 自走対象。信頼境界 — リポジトリ管理者のみ付与可 | ユーザー / Create Workflow | Cycle 完了時（merge & close と同時） |
| `claude-running` | Cycle 実行中（atomic claim 後）| Cycle Step 2 | Step 6（review 遷移）/ 失敗時 (Step 9) |
| `claude-review` | Codex レビュー中 / draft PR レビュー段階 | Cycle Step 6 | Auto merge 成功時 / 失敗時 |
| `claude-failed` | 自走失敗。人間引き継ぎが必要 | 失敗時 (Step 9) | 人間が手動で削除して再投入 |

> **`claude-auto` は信頼境界**: このラベルが付いた issue の本文は Codex に渡される。リポジトリ管理者しか付与できないことをドキュメントで明示する。`require_author_association` で issue 作者の権限もチェックする。

## State × Event 2D Transition Table

行 = 現在の状態（ラベルの組合せ）、列 = イベント。セルは「次状態」または `ERROR`（未定義遷移）。

| State \\ Event              | polling-pickup           | claim-success      | cycle-success           | codex-lgtm + gates-ok | codex-needs-changes | failure              | manual-close                 |
|----------------------------|--------------------------|--------------------|-------------------------|----------------------|---------------------|----------------------|------------------------------|
| `claude-auto`              | → claim-success へ進む    | `+claude-running`  | ERROR                   | ERROR                | ERROR               | `+claude-failed`     | all `claude-*` 削除 + close   |
| `claude-auto +running`     | SKIP（拾わない）          | ERROR              | `-running +review`      | ERROR                | ERROR               | `-running +failed`   | all `claude-*` 削除 + close   |
| `claude-auto +review`      | SKIP（拾わない）          | ERROR              | ERROR                   | merge + close + 全削除 | 同 +review（次 iter） | `-review +failed`    | all `claude-*` 削除 + close   |
| `claude-auto +failed`      | SKIP（拾わない）          | ERROR              | ERROR                   | ERROR                | ERROR               | （冪等）             | all `claude-*` 削除 + close   |
| `claude-auto +running +review` | SKIP                 | ERROR              | ERROR                   | merge + 全削除         | 同状態              | `-running -review +failed` | all 削除 + close           |

### Notes

- **SKIP** = polling で取得しても client-side フィルタで除外される（`claude-running` / `claude-review` / `claude-failed` のいずれかを持つため）
- **ERROR** = 未定義遷移。発生したらバグ。本スキル内で `ERROR: undefined transition <state> + <event>` を出力して abort
- **manual-close** はどの状態からでも可。clean up は polling 起動時の孤児スキャンに任せる

## 並行安全性

- `claude-running` の付与は **assignee 排他 + post-claim re-verify** を組み合わせる（SKILL.md Cycle Step 2 参照）
- `claude-running` が付いている issue は polling から見えない（client-side フィルタ）
- 複数 worker が同時に同じ issue を狙ってもラベル付与に成功するのは 1 人だけ
