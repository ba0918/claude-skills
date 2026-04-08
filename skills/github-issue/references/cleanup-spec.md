# Cleanup Specification

worktree とブランチの孤児検出 / クリーンアップ規則。

> **Drift Prevention (共通契約 §11 遵守)**: Kill file / SIGINT trap / orphan recovery 純関数などの共通仕様は [`polling-pattern.md`](../../shared/references/polling-pattern.md) に集約されている。本ファイルには GitHub 固有の部分（`sanitize_repo_slug` / worktree 命名 / 24h 検出 / Partial Claim Rollback）のみ残す。

## sanitize_slug vs sanitize_repo_slug 責務分離

> **Canonical Location**: 本節が canonical SSOT。`polling-adapter.md` / `SKILL.md` / 他 references は本節への直リンクのみ持ち、責務分離の定義を複製しない。

本スキルには 2 つの類似 sanitize 関数が存在する。**責務が異なるため混同禁止**:

| 関数 | 定義元 | 入力 | 用途 | 責務 |
|---|---|---|---|---|
| `sanitize_slug(raw)` | 共通契約 [`polling-pattern.md §4`](../../shared/references/polling-pattern.md#4-pure-function-signatures) | issue slug / state slug（例: `issue-42`）| 共通契約の `list_ready` / `claim` / `mark_*` API に渡す slug の正規化 | polling 契約レベルの slug 形式整備 |
| `sanitize_repo_slug(raw)` | 本ファイル §`sanitize_repo_slug()` | `nameWithOwner`（例: `owner/repo`）| lockfile / worktree / `state_root` のディレクトリ名に埋め込む path segment 変換 | **GitHub 固有**の path traversal / shell metachar 防御 |

**混同禁止のルール**:

- `sanitize_slug` は共通契約の純関数で、Label / FS 両 adapter が同じものを使う
- `sanitize_repo_slug` は GitHub Label adapter 固有で、`nameWithOwner` → path segment 専用
- 両者はシグネチャもホワイトリストも目的も異なる
- 新規コード追加時は必ずこの表を参照し、適切な関数を選択する

本規約は `polling-adapter.md` と `SKILL.md` から本節への直リンクで参照される（**canonical は本節の 1 箇所のみ**）。

## sanitize_repo_slug()

lockfile / worktree パス / `state_root` ディレクトリ名に `nameWithOwner`（例 `owner/repo`）を埋め込む際は、必ずホワイトリスト方式でサニタイズする。

```
sanitize_repo_slug(name_with_owner: str) -> str:
  # ホワイトリスト: [a-zA-Z0-9._-] のみ通す。それ以外は '_' に置換。
  # これにより '/', null byte, パストラバーサル文字, シェルメタ文字を構造的に排除。
  value = regex_replace(name_with_owner, r"[^a-zA-Z0-9._-]", "_")
  # Defense in depth: '.' はホワイトリストで通すため、'..' が残り得る。
  # 監査ツール / レビュアーが path traversal の痕跡を読み違えないよう '__' に潰す。
  value = value.replace("..", "__")
  return value

# 例:
# sanitize_repo_slug("owner/repo")        -> "owner_repo"
# sanitize_repo_slug("ev/il;rm -rf /")    -> "ev_il_rm_-rf__"
# sanitize_repo_slug("a/../b")            -> "a___b" (双方向で '..' が消える)
```

> 旧実装の `tr / -` は `/` 以外の危険文字（空白、`;`, `$`, null byte 等）を素通しするため使用しない。

## Worktree 命名規約

```
gh-issue-{issue_number}-{yyyymmddhhmmss}
```

例: `gh-issue-42-20260408041530`

- `issue_number`: GitHub issue 番号
- `yyyymmddhhmmss`: 作成時刻（`date +%Y%m%d%H%M%S`）

ブランチ名も同じく `gh-issue-{N}-{timestamp}` を使う。

## 孤児検出ルール (24h 条件)

以下を **すべて** 満たす worktree のみクリーンアップ対象とする。

1. ディレクトリ名が `gh-issue-{N}-{timestamp}` パターンに合致
2. `timestamp` が現在時刻から **24 時間以上前**
3. 対応する issue `#N` の状態が以下のいずれか:
   - issue が close 済み
   - issue に `claude-running` ラベルが**付いていない**
4. 対応するブランチが merge 済み (`git branch --merged main` に含まれる) または対応する PR が closed/merged

> **保守的クリーンアップ**: 上記 4 条件すべてを AND で要求する。1 つでも怪しければ削除しない。

本検出は `rollback_orphans()` step ① (`_check_worktree_orphans`) から呼ばれる。詳細は [`polling-adapter.md §rollback_orphans Sub-Steps`](polling-adapter.md#rollback_orphans-sub-steps) を参照。

## 削除手順

```bash
# 1. 削除対象を列挙
git worktree list --porcelain | parse → candidates

# 2. 各候補について再確認
for wt in candidates:
  N = extract_issue_number(wt.name)
  ts = extract_timestamp(wt.name)

  if age(ts) < 24h: skip
  state = gh issue view ${N} --json state,labels
  if "claude-running" in state.labels: skip   # 直前の再確認
  if not (issue closed or branch merged): skip

  # 3. 削除実行
  git worktree remove <path> --force
  git branch -D <branch>   # ブランチも削除（merged 済み前提）
```

## 起動タイミング

- **Polling Workflow** の `rollback_orphans()` step ① で実行（毎 tick 冒頭でクリーンアップ）
- 手動 `cycle` 実行時は実行しない（並走中の他 worker に影響しないため）

## Partial Claim Rollback

Cycle Workflow Step 2 の atomic claim 3 段防御（[`polling-adapter.md §claim() 3 段防御`](polling-adapter.md#claim-3-段防御) 参照）は順序実行のため、途中段階で失敗した際に副作用が残る可能性がある。lockfile 取得には成功したが assignee / label 設定に失敗したケースは、以下の手順で明示的にロールバックする:

1. `gh issue edit ${N} --remove-label claude-running` を best-effort で実行（既に付与されていた場合）
2. `gh issue edit ${N} --remove-assignee @me` を best-effort で実行（自分が assignee になっていた場合）
3. dual-write label が一部付与されていた場合は **`-transient -permanent -claude-failed` の順** で削除する（precedence rule との整合性維持）
4. `flock` の解除はプロセス終了で自動。`exec 8>&-` で明示クローズしてもよい
5. ロールバック自体が失敗してもプロセスは abort 続行（次 tick の冪等性で復旧）
6. `[claim-rollback] issue=#${N} reason=<…>` を stderr にログ

これにより部分 claim による「assignee は付いているが lock は解放済み」のような中途半端な状態を最小化する。

## ログ

クリーンアップ実行時は標準出力に以下を記録:

```
[cleanup] removed worktree: gh-issue-42-20260407041530 (issue closed, branch merged)
[cleanup] removed worktree: gh-issue-99-20260406120000 (issue !running, age 36h)
```
