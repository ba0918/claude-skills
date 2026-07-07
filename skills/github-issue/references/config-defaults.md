# Configuration Defaults

> **SSOT Note**: 共通契約 [`polling-pattern.md §10 Default Config`](../../shared/references/polling-pattern.md#10-default-config-保守的初期値) にある値（`max_parallel` / `max_iter` / `max_wallclock` / `failed_streak_limit` / `transient_retry_limit` / `tick_interval_loop_mode` / `dry_run` 等）は共通契約側を SSOT として参照し、本ファイルでは再定義しない。本ファイルには **GitHub 固有の config のみ** を記載する。

すべての値は引数 `--config key=value` で上書き可能。

## GitHub 固有 Config

| Key | Default | 単位 | 説明 |
|-----|---------|------|------|
| `max_review_iterations` | `3` | 回 | Codex レビュー → iterate 修正 のループ上限 |
| `parallel_worktree_limit` | `1` | 個 | parallel-cycle に渡す worktree 物理並列上限。明示オプトインで増やす。共通契約 `max_parallel` とは別責務（下記 Precedence 参照） |
| `polling_interval` | `10m` | 時間 | `/loop` コマンドの外部呼び出し間隔（参考値）。共通契約 §10 の `tick_interval_loop_mode`（tick 内部の `--loop` リトライ間隔、default 30s）とは **別概念**。`/loop` は tick 単位で polling を起動し、その内部で `--loop` モードが `tick_interval_loop_mode` 毎に再 tick する |
| `min_rate_limit_remaining` | `500` | requests | GitHub API 残量がこれ未満なら polling skip |
| `max_diff_lines` | `2000` | 行 | これを超える PR は Codex に渡さず claude-failed |
| `codex_review_timeout` | `5min` | 時間 | Codex 1 回呼び出しのタイムアウト |
| `codex_consecutive_failure_threshold` | `3` | 回 | Codex API の連続一時障害がこの回数連続したら恒久 failed 扱い。`transient_retry_limit`（§10）とは独立パラメータ（[詳細](codex-review-loop.md#codex_consecutive_failure_threshold-vs-transient_retry_limit)）|
| `auto_merge_strategy` | `squash` | 種別 | `gh pr merge` のマージ方式（`squash` / `merge` / `rebase`）|
| `codex_required_for_merge` | `true` | bool | **Locked (not user-overridable)**: GitHub merge は不可逆操作のため fail-closed を強制する。`--config codex_required_for_merge=false` で上書きしようとしても警告を出して `true` にリセットする。|
| `require_author_association` | `OWNER,MEMBER,COLLABORATOR` | csv | issue 作者がこれら以外なら polling skip |
| `enable_base64_scan` | `false` | bool | secret-scanner の汎用 Base64 パターンを有効化するか。誤検知が多いため既定 off。詳細は [`secret-scanner.md`](secret-scanner.md) |
| `rollback_gh_fetch_cap` | `10` | 件 | `rollback_orphans()` step ③ / ④ の 1 tick あたり `gh issue view` API 呼び出し上限。超過分は次 tick に持ち越す（fetch storm 防止）|

## Parallel Precedence Rule

`parallel_worktree_limit` と共通契約 `max_parallel`（§10）は責務が異なるため、両者を同 tick 内で併用する場合は **`min(...)` を実効上限** とする:

| パラメータ | 所在 | 責務 |
|---|---|---|
| `max_parallel` | 共通契約 §10 | tick あたり claim 上限。issue 単位の論理的な並行度 |
| `parallel_worktree_limit` | 本ファイル (GitHub 固有) | worktree 物理リソース上限。`parallel-cycle` skill に渡す並列数 |

実効上限:

```
effective_parallel = min(max_parallel, parallel_worktree_limit)
list_ready(effective_parallel)  # claim 数自体を物理上限に合わせる
```

これにより claim だけ進んで worktree が wait する状態を防ぐ。`parallel_worktree_limit` の default は 1 のため、明示的に上書きしない限り直列実行となる。

## Schedule Path Alternative

`/loop github-issue-polling` の代わりに `schedule` スキル（cron）でも polling を実行できる。長時間 cycle が走る場合や `/loop` を占有したくない場合に有効。

例:
```
schedule create --cron "*/10 * * * *" --command "/github-issue-polling --stateless"
```

> **必ず `--stateless` を付けること**: cron 起動は 1 invocation = 1 tick でプロセスが毎回死ぬため、
> `--stateless` なしでは `max_iter` / `max_wallclock` / `failed_streak` の 3 重ガードが毎回リセットされ実質無効になる
> （共通契約 [`§6.5 Tick Session`](../../shared/references/polling-pattern.md#65-tick-session-ステートレス実行の-safety-brake-永続化) 参照）。

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
- `rollback_gh_fetch_cap >= 1`

不正値は起動時にエラー終了する。
