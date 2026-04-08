---
description: "ready キューを消化し続ける self-driving polling ループを起動する（ラルフループ型、bypass-permissions 前提）"
---

Skill ツールで `claude-skills:issue` を実行する。引数: `polling $ARGUMENTS`

## Flags

- `--once` (default): 1 tick のみ実行して終了
- `--loop`: kill file または safety brake 発動まで tick を繰り返す
- `--max-parallel N`: 同時 claim 上限（default 4）
- `--max-iter N`: loop モードでの tick 回数上限（default 10）
- `--max-wallclock DURATION`: loop モードでの経過時間上限（default 1h）
- `--failed-streak N`: 連続失敗の上限（default 3）
- `--dry-run`: cycle を呼ばず claim 計画のみ返す

## Initial Run Policy

`docs/issues/.polling-initialized` が存在しない場合、このコマンドは **`--dry-run` を強制**する。初回ユーザーが 1 度挙動を確認してから実運用に入るためのセーフティ。

## Safety Brakes

詳細は共通契約 `skills/shared/references/polling-pattern.md` §6 を参照。要点:

- Kill file 2 系統: `docs/issues/.STOP` (graceful) / `docs/issues/.STOP.hard` (hard)
- 3 重ガード: `max_iter` / `max_wallclock` / `failed_streak`
- SIGINT trap と orphan recovery による claim rollback 保証
- `bypass-permissions` 実行時でも上記 3 重ガード（kill file / bounded execution / orphan recovery）が暴走を止める安全網として機能する

## References

- SKILL.md: `skills/issue/SKILL.md` の Polling Workflow セクション
- 共通契約: `skills/shared/references/polling-pattern.md`
- FS adapter: `skills/issue/references/polling-state.md`
- 純関数: `skills/issue/references/polling-state-machine.md`
