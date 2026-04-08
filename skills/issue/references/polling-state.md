# Issue FS State Adapter

> **本ファイルの位置づけ:** `skills/shared/references/polling-pattern.md` で定義された共通契約の **FileSystem 実装仕様**。共通契約の本文は複製せず、§ 参照で引用する。

共通契約: [../../shared/references/polling-pattern.md](../../shared/references/polling-pattern.md)

---

## 1. Directory Layout

`state_root` = `docs/issues/`

```
docs/issues/
  .STOP                          # graceful kill file (契約 §6.1)
  .STOP.hard                     # hard kill file (契約 §6.1)
  .polling-initialized           # 初回起動ポリシー用マーカー (契約 §10)
  .last_archive_month            # month boundary cache (契約 §9)
  issue-status.md                # 既存 index (create workflow 互換)
  ready/{slug}.md                # claim 可能
  running/{slug}/
    issue.md                     # 本体
    .claim                       # pid + started_at (orphan recovery 用)
  done/{slug}.md
  failed/
    transient/{slug}.md          # frontmatter に retry_count
    permanent/{slug}.md
  archives/
    YYYY-MM/{slug}.md            # 月次アーカイブ
    {legacy-flat-files}          # 既存の close workflow 由来
```

既存 `close workflow` の `archives/` フラット配置と共存する（同名衝突は FS 上で発生しえない前提）。

---

## 2. Interface Implementation (契約 §3 の FS 実装)

| Method | FS 実装 |
|---|---|
| `list_ready(limit)` | `ready/` を `readdir` で走査し `limit` 件見つかり次第 return（**早期打ち切り必須**、全件スキャン禁止） |
| `claim(slug)` | `mkdir running/{slug}` → `rename ready/{slug}.md running/{slug}/issue.md` → `write running/{slug}/.claim` (pid + started_at)。途中失敗時は Partial Claim Rollback（§4） |
| `release(slug)` | `rename running/{slug}/issue.md ready/{slug}.md` → `rmdir running/{slug}` |
| `mark_done(slug)` | `rename running/{slug}/issue.md done/{slug}.md` → `rmdir running/{slug}` |
| `mark_failed(slug, kind)` | `rename running/{slug}/issue.md failed/{kind}/{slug}.md` → `rmdir running/{slug}` |
| `retry_count(slug)` | frontmatter `retry_count` 読み取り（未定義は 0） |
| `increment_retry(slug)` | frontmatter `retry_count` を +1 して書き戻し、新値を返す |
| `kill_file_path()` | `(abspath(state_root/.STOP), abspath(state_root/.STOP.hard))` |
| `archive_month_boundary()` | §5 参照 |
| `rollback_orphans(now)` | §6 参照 |
| `sanitize_slug(raw)` | §3 参照 |

---

## 3. `sanitize_slug()` 実装規約

共通契約 §4 の純関数 `sanitize_slug` の FS 実装ルール:

1. ホワイトリスト `[a-zA-Z0-9._-]` 以外の全文字を `_` に置換
2. `..` を `__` に置換（path traversal 防止）
3. 先頭 `.` / `/` / 空文字を拒否（`InvalidSlug`）
4. 長さ上限 128 文字（超過は truncate + ハッシュ suffix）
5. 変換後のパスが `realpath(state_root)` の配下に収まることを `realpath` で再検証（シンボリックリンク経由の脱出検出）

> 既存 `github-issue` の `sanitize_repo_slug` を一般化したもの。将来 `skills/shared/` 側へ純関数として昇格予定。

---

## 4. Partial Claim Rollback

`claim()` は「`mkdir` → `rename` → `write .claim`」の 3 段。途中失敗時の rollback 手順:

| 失敗地点 | Rollback |
|---|---|
| `mkdir running/{slug}` 失敗 | 何もせず `ClaimFailed` を返す |
| `rename` 失敗 | 作成済み `running/{slug}` を `rmdir`、`ClaimFailed` |
| `.claim` 書き込み失敗 | `running/{slug}/issue.md` を `ready/{slug}.md` へ戻す → `rmdir` → `ClaimFailed` |

いずれの分岐でも **`running/` に孤児ディレクトリを残さない**ことを保証する。

---

## 5. Month Boundary Archive (O(1))

```
archive_month_boundary():
  cur_month = now.strftime("%Y-%m")
  cached = read(state_root/.last_archive_month)   # 無ければ ""
  if cached == cur_month: return 0                # ← O(1) early return
  # 境界跨ぎ: done/ をスキャンして archives/{cached}/ に移動
  moved = move_all(done/*, archives/{cached}/)
  write(state_root/.last_archive_month, cur_month)
  return moved
```

同月内の tick では **ディレクトリスキャンを一切行わない**。

---

## 6. Orphan Recovery (契約 §6.4)

```
rollback_orphans(now):
  recovered = []
  for slug in listdir(running/):
    claim_file = running/{slug}/.claim
    if not exists(claim_file): continue
    (pid, started_at) = parse(claim_file)
    if is_alive(pid): continue                    # 正常実行中
    # 死亡 pid: rollback
    rename(running/{slug}/issue.md, ready/{slug}.md)
    rm(claim_file); rmdir(running/{slug})
    recovered.append(slug)
  return recovered
```

`is_alive(pid)` は `kill(pid, 0)` 相当。`started_at` は監査ログ用（将来の timeout-based recovery に拡張可能）。

---

## 7. Kill File Path

```
kill_file_path():
  root = realpath(state_root)                     # cwd 非依存
  return (f"{root}/.STOP", f"{root}/.STOP.hard")
```

**必ず絶対パスで解決**。相対パスは禁止（cwd 変動で検出漏れの原因となる）。

---

## 8. 参照

- 共通契約（状態機械・interface・純関数・Tick・Safety Brakes）: [../../shared/references/polling-pattern.md](../../shared/references/polling-pattern.md)
- 純関数仕様（transition / classify_failure / ...）: [./polling-state-machine.md](./polling-state-machine.md)
