# Cleanup Specification

worktree とブランチの孤児検出 / クリーンアップ規則。

## sanitize_repo_slug()

lockfile / worktree パスに `nameWithOwner`（例 `owner/repo`）を埋め込む際は、必ずホワイトリスト方式でサニタイズする。SKILL.md からも本関数を参照する。

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

## 孤児検出ルール

以下を **すべて** 満たす worktree のみクリーンアップ対象とする。

1. ディレクトリ名が `gh-issue-{N}-{timestamp}` パターンに合致
2. `timestamp` が現在時刻から **24 時間以上前**
3. 対応する issue `#N` の状態が以下のいずれか:
   - issue が close 済み
   - issue に `claude-running` ラベルが**付いていない**
4. 対応するブランチが merge 済み (`git branch --merged main` に含まれる) または対応する PR が closed/merged

> **保守的クリーンアップ**: 上記 4 条件すべてを AND で要求する。1 つでも怪しければ削除しない。

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

- **Polling Workflow Step 4** で実行（毎 tick 冒頭でクリーンアップ）
- 手動 `cycle` 実行時は実行しない（並走中の他 worker に影響しないため）

## Partial Claim Rollback

Cycle Workflow Step 2 の atomic claim 3 段防御は順序実行のため、途中段階で失敗した際に副作用が残る可能性がある。lockfile 取得には成功したが assignee / label 設定に失敗したケースは、以下の手順で明示的にロールバックする:

1. `gh issue edit ${N} --remove-label claude-running` を best-effort で実行（既に付与されていた場合）
2. `gh issue edit ${N} --remove-assignee @me` を best-effort で実行（自分が assignee になっていた場合）
3. `flock` の解除はプロセス終了で自動。`exec 8>&-` で明示クローズしてもよい
4. ロールバック自体が失敗してもプロセスは abort 続行（次 tick の冪等性で復旧）
5. `[claim-rollback] issue=#${N} reason=<…>` を stderr にログ

これにより部分 claim による「assignee は付いているが lock は解放済み」のような中途半端な状態を最小化する。

## ログ

クリーンアップ実行時は標準出力に以下を記録:

```
[cleanup] removed worktree: gh-issue-42-20260407041530 (issue closed, branch merged)
[cleanup] removed worktree: gh-issue-99-20260406120000 (issue !running, age 36h)
```
