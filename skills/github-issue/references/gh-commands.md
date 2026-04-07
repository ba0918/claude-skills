# gh CLI Semantic Wrappers

gh CLI 呼び出しの意味論的ラッパー一覧。本スキル内で直接 `gh` を呼ぶ箇所はこの表に対応していること。

## Auth / Repo

| 用途 | コマンド |
|------|---------|
| gh インストール確認 | `gh --version` |
| 認証確認 | `gh auth status` |
| リポジトリ情報 | `gh repo view --json nameWithOwner,defaultBranchRef` |
| Rate limit | `gh api rate_limit --jq '.rate.remaining'` |

## Issue

| 用途 | コマンド |
|------|---------|
| Issue 一覧（claude-auto） | `gh issue list --label claude-auto --state open --json number,title,body,labels,assignees,author,authorAssociation --limit 100` |
| Label 一覧 | `gh label list --json name,description,color` |
| Issue 詳細 | `gh issue view <N> --json number,title,body,labels,assignees,author,authorAssociation` |
| Issue 作成 | `gh issue create --title <T> --body <B> --label <L>` |
| Assignee 追加 | `gh issue edit <N> --add-assignee @me` |
| Label 追加 | `gh issue edit <N> --add-label <L>` |
| Label 削除 | `gh issue edit <N> --remove-label <L>` |
| Comment 投稿 | `gh issue comment <N> --body <B>` |
| Issue close | `gh issue close <N>` |

## Pull Request

| 用途 | コマンド |
|------|---------|
| Draft PR 作成 | `gh pr create --draft --title <T> --body <B>` |
| PR diff 取得 | `gh pr diff <PR>` |
| PR checks 状態 | `gh pr checks <PR>` |
| Draft 解除 | `gh pr ready <PR>` |
| Squash merge | `gh pr merge <PR> --squash --delete-branch` |

## 注意事項

- **`--search` は使わない**: GitHub Search API は 30 req/min の制限があり、polling では `--label` フィルタ + client-side 除外を使う
- **`gh pr merge --auto` は使わない**: 順序保証のため明示的に `gh pr ready` → `gh pr merge` の順で実行
- **`gh pr create --draft` 必須**: auto merge ゲートを通過するまで draft 解除しない
- **JSON 出力で `--jq` を活用**: shell parsing を避ける
