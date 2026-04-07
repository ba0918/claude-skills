# Configuration Defaults

すべての値は引数 `--config key=value` で上書き可能。

| Key | Default | 単位 | 説明 |
|-----|---------|------|------|
| `max_review_iterations` | `3` | 回 | Codex レビュー → iterate 修正 のループ上限 |
| `parallel_worktree_limit` | `1` | 個 | parallel-cycle に渡す並列上限。明示オプトインで増やす |
| `polling_interval` | `10m` | 時間 | `/loop` の tick 間隔（参考値） |
| `min_rate_limit_remaining` | `500` | requests | GitHub API 残量がこれ未満なら polling skip |
| `max_diff_lines` | `2000` | 行 | これを超える PR は Codex に渡さず claude-failed |
| `codex_review_timeout` | `5min` | 時間 | Codex 1 回呼び出しのタイムアウト |
| `codex_consecutive_failure_threshold` | `3` | 回 | 一時障害がこの回数連続したら恒久 failed 扱い |
| `auto_merge_strategy` | `squash` | 種別 | `gh pr merge` のマージ方式（`squash` / `merge` / `rebase`）|
| `codex_required_for_merge` | `true` | bool | false にすると Codex なしでもマージ可（非推奨）|
| `require_author_association` | `OWNER,MEMBER,COLLABORATOR` | csv | issue 作者がこれら以外なら polling skip |

## Schedule Path Alternative

`/loop github-issue-polling` の代わりに `schedule` スキル（cron）でも polling を実行できる。長時間 cycle が走る場合や `/loop` を占有したくない場合に有効。

例:
```
schedule create --cron "*/10 * * * *" --command "/github-issue-polling"
```

## Override Example

```
github-issue cycle 42 --config max_review_iterations=5 --config parallel_worktree_limit=2
```

## Validation

- `parallel_worktree_limit >= 1`
- `max_review_iterations >= 1`
- `max_diff_lines >= 100`
- `min_rate_limit_remaining >= 0`
- `auto_merge_strategy ∈ {squash, merge, rebase}`

不正値は起動時にエラー終了する。
