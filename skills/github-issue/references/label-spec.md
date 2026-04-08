# Label Specification

github-issue スキルが管理するラベルの網羅定義。

> **Drift Prevention (共通契約 §11 遵守)**: 状態遷移表と純関数シグネチャは共通契約 [`polling-pattern.md`](../../shared/references/polling-pattern.md) に集約されている。本ファイルでは再定義せず直リンクのみ。Label Mapping の SSOT は [`polling-adapter.md §Label Mapping`](polling-adapter.md#label-mapping) に一本化されている。

## Labels

| Label | 意味 | 付与タイミング | 削除タイミング |
|-------|------|---------------|--------------|
| `claude-auto` | 自走対象。信頼境界 — リポジトリ管理者のみ付与可 | ユーザー / Create Workflow | Cycle 完了時（merge & close と同時） |
| `claude-running` | Cycle 実行中（atomic claim 後）| Cycle Step 2 | Step 6（review 遷移）/ 失敗時 (Step 9) |
| `claude-review` | Codex レビュー中 / draft PR レビュー段階 | Cycle Step 6 | Auto merge 成功時 / 失敗時 |
| `claude-failed-transient` | 自走失敗（一時エラー、次 tick で retry 可）| `mark_failed(slug, TRANSIENT)` | 次 tick で成功時 / 恒久昇格時 |
| `claude-failed-permanent` | 自走失敗（恒久エラー、人間判断待ち）| `mark_failed(slug, PERMANENT)` | 人間が手動で削除して再投入 |
| `claude-failed` | **DEPRECATED alias**（precedence: permanent）。1.14.0 では dual-write で後方互換、1.16.0 で削除予定 | `mark_failed` の dual-write で transient/permanent と同時付与 | 人間が手動で削除して再投入 |

> **`claude-auto` は信頼境界**: このラベルが付いた issue の本文は Codex に渡される。リポジトリ管理者しか付与できないことをドキュメントで明示する。`require_author_association` で issue 作者の権限もチェックする。

## State Machine (共通契約 §2 直リンク)

状態遷移の定義は共通契約に集約されている。本ファイルでは再定義しない。

- **States**: [`polling-pattern.md §2 Lifecycle State Machine`](../../shared/references/polling-pattern.md#2-lifecycle-state-machine) の `ready` / `running` / `done` / `failed/transient` / `failed/permanent` / `archives`
- **Transition Table**: [`polling-pattern.md §2 Lifecycle State Machine`](../../shared/references/polling-pattern.md#2-lifecycle-state-machine) の Transition Table セクションを参照
- **`transition()` 純関数**: [`polling-pattern.md §4 Pure Function Signatures`](../../shared/references/polling-pattern.md#4-pure-function-signatures) を参照

> `claude-review` は共通契約 §2 の state 集合には現れない。Label adapter 内部の running substate として隔離されており、`is_running(labels) := "claude-running" ∈ labels OR "claude-review" ∈ labels` で running に subsume される。詳細は [`polling-adapter.md §Label Mapping`](polling-adapter.md#label-mapping) を参照。

## Label Mapping (SSOT 直リンク)

共通契約 state → GitHub ラベル集合のマッピング表は [`polling-adapter.md §Label Mapping`](polling-adapter.md#label-mapping) が canonical SSOT。本ファイルで複製しない（DRY 違反防止）。

## Backward Compatibility

### 読み込み時 (Precedence Rule)

`state_of_failure()` 関数の定義は [`polling-adapter.md §state_of_failure Precedence Rule`](polling-adapter.md#state_of_failure-precedence-rule) を参照。要点:

- 新ラベル (`claude-failed-transient` / `claude-failed-permanent`) が存在する場合、旧 `claude-failed` alias は無視する（stale 残留対策）
- 旧 `claude-failed` 単独の場合のみ legacy alias として `PERMANENT` 扱い
- `claude-failed-transient` と `claude-failed-permanent` の両方が同時に付いている場合は **invalid state として warn ログ + `failed/permanent` 扱い (fail-closed)**

### 書き込み時 (Atomic Dual-Write + Verification)

`mark_failed(slug, kind)` は **単一 `gh issue edit` コマンドで新旧ラベルを同時付与** する（API 呼び出し 2 倍化と部分失敗の両方を回避）:

- `gh issue edit ${N} --add-label claude-failed-transient --add-label claude-failed`
- または `gh issue edit ${N} --add-label claude-failed-permanent --add-label claude-failed`

付与後に `gh issue view ${N} --json labels` で label 集合を再取得して verification:

- 不一致時は **最大 3 回 backoff 再試行** (0s / 1s / 2s)
- 最終失敗時は `<state_root>/recovery/{N}` マーカー + `release(slug)` で次 tick の `rollback_orphans()` で再評価
- **0 ラベル放置を構造的に防ぐ**

詳細擬似コードと crash-safe ordering invariant (CA-1: marker write → CA-2: release の順序) は [`polling-adapter.md §mark_failed(slug, kind)`](polling-adapter.md#mark_failedslug-kind) を参照。

### Recovery Marker

`mark_failed` の verification が最終的に通らない場合、`<state_root>/recovery/{issue_number}` マーカー（空ファイル）を置いて next tick の `rollback_orphans()` で必ず再評価させる。詳細は [`polling-adapter.md §rollback_orphans Sub-Steps`](polling-adapter.md#rollback_orphans-sub-steps) の `_check_recovery_markers` を参照。

### Migration Exit Strategy

| Phase | バージョン | 状態 |
|---|---|---|
| 導入 | 1.14.0 | dual-write 開始、旧 reader も alias で検知可能 |
| 監視 | 1.14.x | `claude-failed` 単独付与 issue 件数を定期確認（手動） |
| 告知 | 1.15.0 | `label-spec.md` に「1.16.0 で alias 廃止」の告知を追加、同 release note 記載 |
| 廃止 | 1.16.0 以上 | alias 読み込み precedence を削除、旧 reader 非対応 |

**廃止条件**（いずれかを満たすこと、別 cycle の plan で確認）:

1. 全 `claude-failed` 単独 issue を新ラベルに migrate 完了
2. 1.15.0 告知から最低 4 週間経過
3. `require_alias_compat` config が `false` にできる運用体制確立

### Downgrade 非対応

**1.14.0 以降から 1.13.x への downgrade は非対応**。

- 新ラベル（`claude-failed-transient` / `claude-failed-permanent`）付き issue が旧 reader から見えなくなり **silent data loss** となるため
- `plugin.json` release note と本ファイルで明記

## Alias 廃止予告

旧 `claude-failed` alias は **1.16.0 で削除予定**。告知方法:

- 1.15.0 リリース時に `label-spec.md` の該当行に「DEPRECATED — removed in 1.16.0」を明記
- 同 release note に移行手順を記載
- 告知から最低 4 週間の移行期間を設ける

## 並行安全性

- `claude-running` の付与は **assignee 排他 + post-claim re-verify + local flock(2)** の 3 段防御（SKILL.md Cycle Step 2 参照、3 段防御の詳細は [`polling-adapter.md §claim() 3 段防御`](polling-adapter.md#claim-3-段防御) に集約）
- `claude-running` / `claude-review` / `claude-failed-*` が付いている issue は polling から見えない（client-side フィルタ）
- 複数 worker が同時に同じ issue を狙ってもラベル付与に成功するのは 1 人だけ
- **単一ホスト前提**: 複数ホストからの分散 polling は非対応。詳細は [`polling-adapter.md §Assumptions`](polling-adapter.md#assumptions) を参照
