---
description: "GitHub `claude-auto` issue を self-driving で消化する polling ループ tick。`/loop` と組み合わせて常駐運用、単一ホスト前提"
---

Skill ツールで `claude-skills:github-issue` を実行する。引数: `polling $ARGUMENTS`

## Flags

issue-polling と完全同形式:

- `--once` (default): 1 tick のみ実行して終了
- `--loop`: kill file または safety brake 発動まで tick を繰り返す
- `--max-parallel N`: 同時 claim 上限（default 4、共通契約 §10 参照）
- `--max-iter N`: loop モードでの tick 回数上限（default 10）
- `--max-wallclock DURATION`: loop モードでの経過時間上限（default 1h）
- `--failed-streak N`: 連続失敗の上限（default 3）
- `--dry-run`: cycle を呼ばず claim 計画のみ返す

## Initial Run Policy

`<state_root>/.polling-initialized` が存在しない場合、`--dry-run` を強制する（共通契約 §10 の初回起動ポリシー準拠）。state_root は `$XDG_STATE_HOME/claude-skills/github-issue/{repo_slug}-{clone_id}/` に解決される。

- `XDG_STATE_HOME` 未設定時は `~/.local/state` が fallback
- `repo_slug` は `sanitize_repo_slug(nameWithOwner)`（path segment 変換）
- `clone_id` は `sha1(normalize_git_url(remote_url))[:16]`（64-bit）
- 詳細は [`../skills/github-issue/references/polling-adapter.md#state_root-resolution`](../skills/github-issue/references/polling-adapter.md#state_root-resolution) を参照

## Safety Brakes

詳細は共通契約 [`skills/shared/references/polling-pattern.md §6`](../skills/shared/references/polling-pattern.md#6-safety-brakes) を参照。要点:

- **Kill file 2 系統**: `<state_root>/.STOP` (graceful) / `<state_root>/.STOP.hard` (hard stop)
- **3 重ガード**: `max_iter` / `max_wallclock` / `failed_streak`
  - `failed_streak` カウントからは `error_kind == "lock"` を **除外** する（別プロセス処理中の silent skip 扱い）
- **SIGINT / SIGTERM trap**: 現在の claim を rollback してから exit
- **Orphan recovery**: 次 tick 冒頭で `rollback_orphans()` が 5 段階の回収を実行
- **単一ホスト前提**: 複数ホストからの分散 polling は非対応（retry state は FS 側にあり、複数ホストから同 repo を polling すると state 不整合）

## Troubleshooting

- **`permission denied` on state_root**: `XDG_STATE_HOME` を書き込み可能なパスに設定、または `~/.local/state` の権限を確認
- **`unsupported filesystem` で polling abort**: NFS / CIFS / tmpfs / WSL DrvFs 経由の mount は非対応。local FS (ext4 / btrfs / xfs / apfs) に state_root を配置すること
- **`state_root clone_id collision`**: 別リポジトリの remote URL が同じ clone_id にマッピングされた稀なケース。`<state_root>/.clone_url` を確認し、不整合なら state_root を削除して再起動
- **alias 廃止予告**: `claude-failed` ラベル単独の issue は 1.16.0 で非対応になる。告知は 1.15.0 で開始
- **Downgrade 非対応**: 1.14.0 以降から 1.13.x への downgrade は silent data loss のため非対応（新ラベル付き issue が旧 reader から見えなくなる）

## References

- SKILL.md: [`../skills/github-issue/SKILL.md`](../skills/github-issue/SKILL.md) — Polling Workflow
- 共通契約: [`../skills/shared/references/polling-pattern.md`](../skills/shared/references/polling-pattern.md)
- Label adapter: [`../skills/github-issue/references/polling-adapter.md`](../skills/github-issue/references/polling-adapter.md)
- Label spec: [`../skills/github-issue/references/label-spec.md`](../skills/github-issue/references/label-spec.md)
- Config defaults: [`../skills/github-issue/references/config-defaults.md`](../skills/github-issue/references/config-defaults.md)
