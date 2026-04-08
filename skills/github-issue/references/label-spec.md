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

### transition() — Pure Function

上記表を switch/match 形式の純関数として表現する。テスト容易性のため副作用なし、未定義遷移は `InvalidTransition` エラーを返す。

```
# State enum: AUTO | RUNNING | REVIEW | FAILED | RUNNING_REVIEW | CLOSED_CLEAN
# Event enum: POLLING_PICKUP | CLAIM_SUCCESS | CYCLE_SUCCESS
#           | CODEX_LGTM_GATES_OK | CODEX_NEEDS_CHANGES | FAILURE | MANUAL_CLOSE

def transition(state, event) -> NextState | InvalidTransition:
  match (state, event):
    # AUTO
    case (AUTO, POLLING_PICKUP):       return AUTO            # no-op: 状態は変えず次フェーズで CLAIM_SUCCESS により RUNNING に遷移
    case (AUTO, CLAIM_SUCCESS):        return RUNNING
    case (AUTO, FAILURE):              return FAILED
    case (AUTO, MANUAL_CLOSE):         return CLOSED_CLEAN

    # RUNNING
    case (RUNNING, POLLING_PICKUP):    return RUNNING         # SKIP（フィルタ除外）
    case (RUNNING, CYCLE_SUCCESS):     return REVIEW
    case (RUNNING, FAILURE):           return FAILED
    case (RUNNING, MANUAL_CLOSE):      return CLOSED_CLEAN

    # REVIEW
    case (REVIEW, POLLING_PICKUP):     return REVIEW          # SKIP
    case (REVIEW, CODEX_LGTM_GATES_OK):return CLOSED_CLEAN    # merge + close + 全削除
    case (REVIEW, CODEX_NEEDS_CHANGES):return REVIEW          # 次イテレーション
    case (REVIEW, FAILURE):            return FAILED
    case (REVIEW, MANUAL_CLOSE):       return CLOSED_CLEAN

    # FAILED
    case (FAILED, POLLING_PICKUP):     return FAILED          # SKIP
    case (FAILED, FAILURE):            return FAILED          # 冪等
    case (FAILED, MANUAL_CLOSE):       return CLOSED_CLEAN

    # RUNNING_REVIEW (中間状態)
    case (RUNNING_REVIEW, POLLING_PICKUP):     return RUNNING_REVIEW
    case (RUNNING_REVIEW, CODEX_LGTM_GATES_OK):return CLOSED_CLEAN
    case (RUNNING_REVIEW, CODEX_NEEDS_CHANGES):return RUNNING_REVIEW
    case (RUNNING_REVIEW, FAILURE):            return FAILED
    case (RUNNING_REVIEW, MANUAL_CLOSE):       return CLOSED_CLEAN

    case _:
      return InvalidTransition(state, event)
```

呼び出し側は `InvalidTransition` を受け取ったら `ERROR: undefined transition <state> + <event>` を出力して abort する。新規状態/イベントを追加する際は本関数のケースを必ず追記すること（網羅性は型システム/テストで担保）。

### Notes

- **SKIP** = polling で取得しても client-side フィルタで除外される（`claude-running` / `claude-review` / `claude-failed` のいずれかを持つため）
- **ERROR** = 未定義遷移。発生したらバグ。本スキル内で `ERROR: undefined transition <state> + <event>` を出力して abort
- **manual-close** はどの状態からでも可。clean up は polling 起動時の孤児スキャンに任せる

## 並行安全性

- `claude-running` の付与は **assignee 排他 + post-claim re-verify** を組み合わせる（SKILL.md Cycle Step 2 参照）
- `claude-running` が付いている issue は polling から見えない（client-side フィルタ）
- 複数 worker が同時に同じ issue を狙ってもラベル付与に成功するのは 1 人だけ
