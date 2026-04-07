# Cleanup Specification

worktree とブランチの孤児検出 / クリーンアップ規則。

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

## ログ

クリーンアップ実行時は標準出力に以下を記録:

```
[cleanup] removed worktree: gh-issue-42-20260407041530 (issue closed, branch merged)
[cleanup] removed worktree: gh-issue-99-20260406120000 (issue !running, age 36h)
```
