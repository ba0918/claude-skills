# Polling Adapter (Label-based)

`skills/github-issue/` の Label state adapter 実装仕様。共通契約 [`skills/shared/references/polling-pattern.md`](../../shared/references/polling-pattern.md) の state adapter interface を GitHub label で実装する。

> **Heading Convention:** 主要節は H2 (`##`)、Interface メソッドなどのサブ節は H3 (`###`) を使用する。Tests チェックリストの `grep '^### '` パターンはこの規約に依存する。

---

## Assumptions

本 adapter は **単一ホスト・単一プロセスのラルフループ前提** とする。

- **単一ホスト前提の理由**:
  - claim は「local lockfile + GitHub label」の混合 consistency domain で、複数ホスト間で GitHub label だけを根拠にした排他は post-verify race が残る
  - retry state を FS (`<state_root>/retry/{N}.json`) に永続化するため、複数ホストから同一 repo を polling すると state が不整合
- **非対応**: 複数ホストからの分散 polling、Windows native（WSL は DrvFs 経由 mount 非対応）
- **対応**: Linux / macOS の local filesystem（ext4, btrfs, xfs, apfs）

複数ホスト対応が必要になった場合は Phase C で「正本を GitHub 側に寄せた再設計」を行う。

---

## Interface Table

共通契約 [§3 Interface Table](../../shared/references/polling-pattern.md#3-interface-table-state-adapter-契約) の 11 メソッドをすべて実装する。下表は Label adapter の実装マッピング詳細版。

| Interface (§3) | Label adapter 実装 |
|---|---|
| `list_ready(limit)` | §`list_ready(limit)` |
| `claim(slug)` | §`claim(slug)` |
| `release(slug)` | §`release(slug)` |
| `mark_done(slug)` | §`mark_done(slug)` |
| `mark_failed(slug, kind)` | §`mark_failed(slug, kind)` |
| `retry_count(slug)` | §`retry_count(slug)` |
| `increment_retry(slug)` | §`increment_retry(slug)` |
| `kill_file_path()` | §`kill_file_path()` |
| `archive_month_boundary()` | §`archive_month_boundary()` |
| `rollback_orphans(now)` | §`rollback_orphans(now)` |
| `sanitize_slug(raw)` | §`sanitize_slug(raw)` |

### list_ready(limit)

`gh issue list --label claude-auto --state open --json number,title,labels,author,authorAssociation --limit {limit}` を **単一呼び出し** で取得。

1. client-side filter:
   - `claude-running` を持つ → 除外
   - `claude-review` を持つ → 除外（running substate）
   - `state_of_failure(labels) is not None` → 除外（§Label Mapping 参照）
   - `authorAssociation` が `require_author_association` に含まれない → 除外
2. **filter 後の件数が `limit` 未満でも再 fetch しない**（次 tick で再取得。repeat fetch による fetch storm 防止。stale state の伝播は `tick_interval_loop_mode = 30s` の範囲内に限定される）
3. 戻り値は `list[Slug]` で `slug = f"issue-{number}"` 形式

### claim(slug)

3 段防御は **adapter 内部実装の詳細** として隠蔽する。SKILL.md は `claim(slug)` を呼ぶだけ。

詳細は §`claim() 3 段防御` を参照。失敗時は `ClaimFailed{reason}` を返し quiet abort（retry しない）。

**Input validation**: `issue_number` は整数であることを事前検証する。`int(slug.removeprefix("issue-"))` で変換失敗、または非整数（負値、zero-padded、`0`）なら `fail_closed("invalid issue_number")` する。正規表現 `^[1-9][0-9]*$` にマッチすること。

### release(slug)

```
gh issue edit ${N} --remove-label claude-running --remove-assignee @me
```

best-effort 実行。失敗しても warn ログのみで続行する（次 tick の `rollback_orphans()` が回収）。

### mark_done(slug)

3 段を **この順序で** 実行。各段の失敗は次 tick の `rollback_orphans()` step ⑤ (closed issue 残ラベル掃除) で recover する。

```
# 1. PR merge
gh pr merge <PR> --squash --delete-branch

# 2. Issue close
gh issue close ${N}

# 3. Label cleanup (単一 edit)
gh issue edit ${N} \
  --remove-label claude-auto \
  --remove-label claude-review \
  --remove-label claude-failed-transient \
  --remove-label claude-failed-permanent \
  --remove-label claude-failed
```

部分失敗（例: close 成功 + ラベル掃除失敗）は next tick の `rollback_orphans()` step ⑤ が「closed issue with `claude-*` label」として検出し掃除する。

### mark_failed(slug, kind)

**単一 `gh issue edit` で新旧ラベルを atomic dual-write + verification + recovery marker**。

```
mark_failed(slug, kind) -> Result:
  labels_add = ["claude-failed-transient", "claude-failed"] if kind == TRANSIENT
               else ["claude-failed-permanent", "claude-failed"]

  for attempt in [1, 2, 3]:  # 最大 3 回、間隔 0s/1s/2s backoff
    try:
      gh issue edit ${N} --add-label <labels_add[0]> --add-label <labels_add[1]>
      labels_now = gh issue view ${N} --json labels --jq '.labels[].name'
      if all(L in labels_now for L in labels_add):
        record_fs_state(slug, kind)  # FS retry state 更新と同 tick で完了
        return Ok
    except GhApiError as e:
      if attempt == 3: break
      sleep(attempt - 1)  # 0s, 1s, 2s

  # 全 attempt 失敗 — compensating action で claim を ready に戻す
  # Crash-safe ordering invariant:
  #   CA-1: recovery marker を FS に write_atomic で永続化 (release より先)
  #   CA-2: release(slug) で claude-running / assignee を外す
  # この順序により CA-1 と CA-2 の間でクラッシュしても marker で必ず回収される。
  # 逆順 (release → marker) では release 後 marker 書き失敗で 0 ラベル + marker なし
  # で追跡不能になる。
  warn_log(f"[mark_failed] verification failed after 3 attempts: {slug}")
  try:
    record_recovery_marker(slug)   # CA-1: FS marker を write_atomic 永続化
  except FsError:
    fail_closed("cannot write recovery marker — polling abort")
  release(slug)                    # CA-2: GitHub 上のラベル/assignee を外す (best-effort)
  return Err("dual_write_failed")  # 次 tick で rollback_orphans() step ④ が拾う
```

**許容される中間状態**:
- 付与側: 0 ラベル（全失敗、recovery marker 付き）または 2 ラベル（正常）。1 ラベル状態は verify で検出して再試行
- **0 ラベル放置禁止**: verification が最終的に通らない場合、必ず `<state_root>/recovery/{N}` マーカーを置いて next tick の `rollback_orphans()` で再評価させる

### retry_count(slug)

**FS state 参照**: `<state_root>/retry/{issue_number}.json` を読み `{retry_count, last_failed_at, run_id}` を返す。

- ファイル無し → `0` (初回扱い)
- JSON parse 失敗 → warn log + ファイルを `<issue_number>.json.corrupt.{ts}` にリネームして隔離 + `0` (再作成)
- **2 回連続で parse 失敗** (隔離後も新 write が再度 parse 失敗) した場合は `fail_closed("retry state corruption")` で polling abort
- `run_id` フィールドは UUID v4 形式、read 時に `^[0-9a-f-]{36}$` 正規表現で検証し不一致なら warn + 無視

### increment_retry(slug)

**FS state 更新**: `write_atomic` 手順で `.tmp` → fsync → rename → parent fsync。単一プロセス前提で read-modify-write の atomicity は flock で保護。

- comment 投稿は **廃止**（race condition + 信頼境界バイパス両方を排除）
- 新しい count 値を返す

### kill_file_path()

`(<state_root>/.STOP, <state_root>/.STOP.hard)` の絶対パスペアを返す。`state_root` 解決は §`state_root Resolution` を参照。

### archive_month_boundary()

**GitHub では no-op**（close = archive 相当）。ただし `<state_root>/.last_archive_month` キャッシュは更新する（共通契約 §9 の unchanged invariant 維持）。

### rollback_orphans(now)

5 段階で実行。各段は `_check_*()` プライベートサブメソッドに分解する。詳細は §`rollback_orphans Sub-Steps` を参照。

### sanitize_slug(raw)

共通契約 [§4 Pure Function Signatures](../../shared/references/polling-pattern.md#4-pure-function-signatures) の `sanitize_slug` を呼ぶだけ。

Label adapter 固有の `sanitize_repo_slug` は `nameWithOwner → path segment` 変換専用として併存する。**責務分離の canonical 記述は [`cleanup-spec.md`](cleanup-spec.md#sanitize_slug-vs-sanitize_repo_slug-責務分離) に 1 箇所のみ配置** し、本ファイルからはそこへのリンク参照のみとする（DRY 違反防止）。

---

## Label Mapping

**本節が canonical SSOT** である。plan / `label-spec.md` / 他 references は本節への直リンクのみ持ち、マッピング表の本文を複製してはならない。

### State Mapping Table

| 共通契約 State (§2) | GitHub ラベル集合 | 備考 |
|---|---|---|
| `ready` | `{claude-auto}` のみ | `claude-running` / `claude-review` / `claude-failed-*` / `claude-failed` 非付与 |
| `running` | `{claude-auto, claude-running}` | 初期 running |
| `running` (substate: review) | `{claude-auto, claude-running, claude-review}` OR `{claude-auto, claude-review}` | **GitHub 固有中間状態**。共通契約 §2 の `running` に subsume される |
| `done` | （close 済み）| close と同時に全 `claude-*` 削除 |
| `failed/transient` | `{claude-auto, claude-failed-transient}` (+ alias `claude-failed` dual-write) | 次 tick で retry 可 |
| `failed/permanent` | `{claude-auto, claude-failed-permanent}` (+ alias `claude-failed` dual-write) | 人間判断待ち |
| `archives` | — | GitHub は close=archives 相当、ラベル不要 |

### is_running predicate (substate unification)

```
is_running(labels) := "claude-running" ∈ labels OR "claude-review" ∈ labels
```

`claude-review` は共通契約 §2 の state 集合には現れない。Label adapter 内部の running substate として隔離し、`list_ready()` の client-side filter で両方とも除外する。

### state_of_failure Precedence Rule

```
# Precedence: 新ラベルが存在する場合、旧 alias は無視する（stale 残留対策）
state_of_failure(labels):
  if "claude-failed-transient" ∈ labels:  return TRANSIENT
  if "claude-failed-permanent" ∈ labels:  return PERMANENT
  if "claude-failed" ∈ labels:             return PERMANENT  # legacy alias
  return None

is_failed_transient(labels) := state_of_failure(labels) == TRANSIENT
is_failed_permanent(labels) := state_of_failure(labels) == PERMANENT
is_any_failed(labels)       := state_of_failure(labels) is not None
```

**Invalid state 検出**: `claude-failed-transient` と `claude-failed-permanent` の両方が同時に付いている場合は invalid state として warn ログ + `failed/permanent` 扱い（fail-closed）。

---

## state_root Resolution

### 取得とフォールバック

```python
def state_root(name_with_owner: str) -> Path:
  # 1. XDG fallback chain
  xdg_base = env("XDG_STATE_HOME") or expanduser("~/.local/state")

  # 2. Repo slug (path segment 変換)
  repo_slug = sanitize_repo_slug(name_with_owner)  # cleanup-spec.md 参照

  # 3. Clone ID: git remote URL を正規化後に SHA-1 16 hex 文字で識別
  git_remote_url = fetch_git_remote_url()
  normalized = normalize_git_url(git_remote_url)
  clone_id = sha1(normalized).hex[:16]  # 64-bit 空間

  target = path.join(xdg_base, "claude-skills", "github-issue", f"{repo_slug}-{clone_id}")

  # 4. 作成 (idempotent)
  mkdir(target, mode=0o700, parents=True, exist_ok=True)

  # 5. 衝突検知: .clone_url を O_CREAT|O_EXCL で排他作成
  stored_url_file = target / ".clone_url"
  if stored_url_file.exists():
    if read(stored_url_file) != normalized:
      fail_closed(f"state_root clone_id collision: {target}")
  else:
    # O_CREAT|O_EXCL 排他作成 (複数プロセス同時初回起動時の TOCTOU race 回避)
    try:
      fd = open(stored_url_file, O_WRONLY|O_CREAT|O_EXCL, mode=0o600)
      write(fd, normalized)
      fsync(fd)
      close(fd)
      fsync(parent_dir_fd)
    except FileExistsError:
      # 別プロセスが先に作成 → 再 read して一致検証
      if read(stored_url_file) != normalized:
        fail_closed(f"state_root clone_id collision after race: {target}")

  # 6. ownership 検証 (共有 HOME 対策)
  if stat(target).uid != getuid():
    fail_closed(f"state_root ownership mismatch: {target}")

  # 7. FS 種別検証 (unsupported FS fail-closed)
  fs_type = statfs(target).f_type
  if fs_type in UNSUPPORTED_FS:  # NFS, CIFS, tmpfs, DrvFs
    fail_closed(f"unsupported filesystem: {fs_type}")

  return target

def fetch_git_remote_url() -> str:
  # Primary: git remote get-url origin
  try:
    return shell("git remote get-url origin").strip()
  except GitNotFound:
    pass
  # Fallback: gh repo view
  try:
    return shell("gh repo view --json url --jq .url").strip()
  except GhError:
    fail_closed("cannot resolve git remote URL")

def normalize_git_url(url: str) -> str:
  # 正規化ルール:
  # 0. URL 文字集合の厳格な許可リスト検証
  # 1. lowercase
  # 2. trailing slash / .git を削除
  # 3. git@host:owner/repo.git → https://host/owner/repo
  # 4. ssh://git@host/owner/repo → https://host/owner/repo

  # STEP 0: URL 文字集合の厳格な許可リスト検証
  # 許可: [a-zA-Z0-9._\-/:@] のみ (path segment / scheme separator で十分)
  # 禁止: `..` 連続, `\`, spaces, tabs, newline, shell metachar ($, `, ', ", ;, &, |, <, >)
  if not re.match(r'^[a-zA-Z0-9._\-/:@]+$', url):
    fail_closed(f"invalid git remote url character set: {url!r}")
  if ".." in url:
    fail_closed(f"git remote url contains path traversal: {url!r}")

  lower = url.lower()
  # git@github.com:foo/bar.git → https://github.com/foo/bar
  if match := re.match(r'^git@([^:]+):(.+?)(?:\.git)?$', lower):
    return f"https://{match.group(1)}/{match.group(2)}"
  # ssh://git@github.com/foo/bar.git → https://github.com/foo/bar
  if lower.startswith("ssh://"):
    lower = re.sub(r'^ssh://(?:git@)?', 'https://', lower)
  # https://...[.git][/] → canonical
  lower = re.sub(r'\.git$', '', lower)
  lower = lower.rstrip("/")
  return lower
```

### 作成失敗時の挙動（fail-closed）

| 失敗ケース | 挙動 |
|---|---|
| `permission denied` (mkdir) | warn log + polling abort (fail-closed) |
| `quota exceeded` | 同上 |
| `parent 作成エラー` | 同上 |
| `clone_id collision` (stored_url mismatch) | warn log + polling abort + operator 通知 |
| `git remote 取得失敗` | polling abort (fail-closed) |
| `unsupported FS` (NFS / CIFS / tmpfs / WSL DrvFs 経由) | **warn log + polling abort (fail-closed)**。fsync/rename atomicity が保証されないため silent data corruption を構造的に排除 |
| `ownership 不一致` (`stat.uid != getuid()`) | fail-closed |
| URL 文字集合不正 | fail-closed |
| URL `..` 含有 | fail-closed |

本 adapter は **ephemeral fallback を持たない**。state_root が使えない環境では polling 自体を起動させない。

### `state_root/` 配下の構造と permission 契約

```
<state_root>/                           dir mode 0700
  .clone_url                            file mode 0600  # URL 衝突検知用
  .STOP                                 file mode 0600  # graceful stop
  .STOP.hard                            file mode 0600  # hard stop
  .polling-initialized                  file mode 0600  # 初回フラグ
  .last_archive_month                   file mode 0600  # "YYYY-MM" キャッシュ
  retry/                                dir mode 0700
    {issue_number}.json                 file mode 0600  # {retry_count, last_failed_at, run_id}
  claim/                                dir mode 0700
    {issue_number}.lock                 file mode 0600  # flock(2) 用 lockfile
  recovery/                             dir mode 0700
    {issue_number}                      file mode 0600  # 空ファイル、dual-write 失敗マーカー
```

---

## Platform Assumptions

本 adapter は **Linux / macOS の local filesystem** を前提とする。使用する API は POSIX.1-2008 の基本関数 (`open`/`fsync`/`rename`) + OS 依存 API (`flock(2)` = BSD 拡張、`statfs(2)`/`fstatfs(2)` で FS 種別判定) の組み合わせで、**純 POSIX 準拠ではなく「Linux/macOS local FS 前提」** として運用する。Windows native / 非 Linux kernel での動作は非対応。

全ての state file 更新は以下の手順で **atomic** に行う:

```
write_atomic(path, content):
  tmp = path + ".tmp." + pid + ".{random}"
  open(tmp, O_WRONLY|O_CREAT|O_EXCL, mode=0o600)
  write(tmp, content)
  fsync(tmp_fd)                  # データの永続化
  close(tmp)
  rename(tmp, path)              # 同一ディレクトリ内の atomic rename
  fsync(parent_dir_fd)           # ディレクトリエントリの永続化
```

- **Supported FS**: ext4, btrfs, xfs, apfs（local filesystem のみ）
- **Unsupported / fail-closed**: NFS, CIFS, tmpfs（rename atomicity や fsync 意味論が非標準）、Windows DrvFs 経由の WSL mount（permission mode 不反映）。`statfs(2)` で判定し、検出時は **warn log + polling abort (fail-closed)**。silent data corruption を防ぐため warn のみでは済ませない
- **ownership 検証**: state_root を開いた時に `stat(path).uid != getuid()` なら fail-closed（共有 HOME で他ユーザーが作った state_root に誤って書き込まない）
- **stale lockfile**: `<state_root>/claim/{N}.lock` は pid を書き、flock(2) で保持。プロセス終了時に自動解放。pid が死亡している場合は `rollback_orphans()` が 5 分以上経過を条件に削除

### `.polling-initialized` Lifecycle

- **作成責務**: polling-adapter が **初回 tick 成功後** に自動作成（`write_atomic` 経由）
- **tick 成功の定義**: tick が `halt_reason=None` または `halt_reason="dry_run"` で完了した時点
- **更新**: 一度作成されたら更新しない（mtime は最終初期化時刻として残る）
- **削除**: ユーザーが `rm <state_root>/.polling-initialized` で手動削除すると次 tick が再度 `--dry-run` 強制（意図的な再確認用途）
- **alias 廃止時**: 削除対象ではない（1.16.0 の alias 廃止 cycle でもそのまま残す）

---

## FS Retry State

### Schema

`<state_root>/retry/{issue_number}.json`:

```json
{
  "retry_count": 2,
  "last_failed_at": "2026-04-08T16:40:19Z",
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Atomic Write

`write_atomic` 手順で更新:

1. `{issue_number}.json.tmp.{pid}.{random}` に書き込み
2. `fsync(tmp_fd)` でデータ永続化
3. `rename(tmp, target)` で atomic に置換
4. `fsync(parent_dir_fd)` でディレクトリエントリ永続化

### `run_id` (UUID v4) 生成/検証

- 生成: 各 tick 開始時に一度 `uuid4()` で発行、loop 内は同一値を使い回す
- 形式: UUID v4 （`xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`）
- Read 時検証: `^[0-9a-f-]{36}$` 正規表現にマッチしない場合は warn log + そのフィールドを無視（`null` 扱い）
- 不一致時も他フィールド（`retry_count`, `last_failed_at`）は読み続行する

### Corrupt JSON 検出時の隔離リネーム

1. 読み込み時に JSON parse に失敗したら、warn log を出す
2. ファイルを `<issue_number>.json.corrupt.{unix_timestamp}` にリネームして隔離
3. `retry_count = 0` として扱い、次の write で新規ファイルが作成される
4. **2 回連続で parse 失敗** (隔離後も新しい write が再度 parse 失敗) したら `fail_closed("retry state corruption")` で polling abort する
5. 隔離済みファイルは手動調査用に残す（TTL なし、運用者判断で削除）

---

## error_kind Enum

`mark_failed` / `classify_failure` で使用する `error_kind` は以下の閉じた enum に限定する。未知値は `"unknown"` に正規化し、`classify_failure` は `unknown → Permanent` で fail-closed する。

```
error_kind ∈ {
  # Transient (retry 可能)
  "network",           # Network I/O error, HTTP 5xx, SIGPIPE, broken pipe
  "rate_limit",        # GitHub/Codex API rate limit (HTTP 403 rate, 429)
  "timeout",           # Codex or gh CLI timeout
  "lock",              # lockfile contention (同一マシン内他プロセスが保持)
                       # SPECIAL: failed_streak に非カウント (silent skip)

  # Permanent (人間判断待ち)
  "test",              # Test failure
  "compile",           # Build/compile failure
  "abort",             # Cycle explicit abort
  "lgtm_parse_fail",   # Codex JSON parse error (1 回リトライ後も失敗)
  "sanitize_failed",   # sanitize_slug rejection
  "security",          # secret scanner hit, auth 失敗, untrusted content policy 違反
  "not_found",         # gh CLI 404 (issue/PR 消失)
  "tool_missing",      # gh CLI 不在、gh バージョン非対応、git 不在
  "unknown"            # 未知の例外 (fail-closed として Permanent)
}
```

### Transient / Permanent 分類

- **Transient** (4 種): `network`, `rate_limit`, `timeout`, `lock`
- **Permanent** (9 種): `test`, `compile`, `abort`, `lgtm_parse_fail`, `sanitize_failed`, `security`, `not_found`, `tool_missing`, `unknown`

### error_kind Handling Rules

`failed_streak` カウント規約 (共通契約 §6 safety brake への GitHub adapter 固有追加):

- **`lock` は `failed_streak` 非カウント** (silent skip)
  - 理由: 「別プロセスが処理中」を意味するため、当該 issue の skip として扱う
  - issue 固有の失敗ではないため `failed_streak` をインクリメントしない
  - tick 全体の失敗扱いにすると safety brake が誤発動する
- それ以外の error_kind はすべて `failed_streak` をインクリメントする

`normalize_github_error` の詳細定義は [`codex-review-loop.md §normalize_github_error`](codex-review-loop.md#normalize_github_error) を参照。

---

## claim() 3 段防御

以下の 3 段を **この順序で** 実行する。1 つでも失敗したら `ClaimFailed{reason}` で quiet abort（retry しない）。

```
claim(slug) -> ClaimResult:
  # Input validation: issue_number は整数事前検証
  try:
    N = int(slug.removeprefix("issue-"))
  except ValueError:
    fail_closed(f"invalid issue_number: {slug!r}")
  if not re.match(r'^[1-9][0-9]*$', str(N)) or N != int(str(N)):
    fail_closed(f"invalid issue_number format: {N}")

  # ① Local lockfile (flock(2) non-blocking)
  lock_path = state_root / "claim" / f"{N}.lock"
  try:
    lock_fd = open(lock_path, O_WRONLY|O_CREAT, mode=0o600)
    flock(lock_fd, LOCK_EX | LOCK_NB)
    write(lock_fd, str(pid))
    fsync(lock_fd)
  except BlockingIOError:
    return ClaimFailed("LockBusy")  # quiet abort

  # ② gh issue edit で assignee + claude-running 付与
  try:
    shell(f"gh issue edit {N} --add-assignee @me --add-label claude-running")
  except GhError as e:
    close(lock_fd)
    return ClaimFailed(f"gh edit failed: {e}")

  # ③ re-verify (post-claim race 検出)
  result = shell(f"gh issue view {N} --json assignees,labels")
  if "@me" not in result.assignees or "claude-running" not in result.labels:
    # Partial claim rollback
    shell(f"gh issue edit {N} --remove-label claude-running --remove-assignee @me")
    close(lock_fd)
    return ClaimFailed("post-claim verify failed")

  return ClaimOk(lock_fd)  # lock_fd はプロセス終了まで保持
```

- **lockfile は process 終了時に自動解放**（`close` or `exit` で kernel が flock を解除）
- **stale lockfile** は `rollback_orphans()` が 5 分経過 + pid dead 条件で削除

SKILL.md 側は 3 段防御の内部構造を知らず、`claim(slug)` を呼ぶだけで済む（Layer Separation）。

---

## rollback_orphans Sub-Steps

`rollback_orphans(now)` は 5 段階で実行する。各段は **early return なし、全部走り切る**。各段階は内部プライベートサブメソッドに分解し、各段の単体テスト可能性を担保する。

```
rollback_orphans(now) -> list[Slug]:
  recovered = []
  recovered += _check_worktree_orphans(now)      # ①
  recovered += _check_stale_locks(now)           # ②
  recovered += _check_long_running(now)          # ③
  recovered += _check_recovery_markers(now)      # ④
  recovered += _check_closed_with_labels(now)    # ⑤
  return recovered
```

### ① `_check_worktree_orphans(now)`

既存 [`cleanup-spec.md`](cleanup-spec.md) の 24h + merged 条件に従い worktree 孤児を削除する。

### ② `_check_stale_locks(now)`

`<state_root>/claim/*.lock` を走査:
- mtime が 5 分以上経過 かつ pid が dead なら削除
- lockfile 内に書かれた pid で `kill(pid, 0)` して ESRCH なら dead 判定

### ③ `_check_long_running(now)`

`claude-running` 付きで長時間経過した issue を `release()` する:

1. `gh issue list --label claude-running --state open --json number,createdAt,updatedAt` で列挙
2. 各 issue について基準時刻を決定:
   - PR 未作成: `issue.created_at` を基準 → 48h 超過で `release()`
   - PR 存在: `pr.head commit pushed_at`（なければ `pr.created_at`）を基準 → 48h 超過で `release()`
3. **`issue.created_at` から 7 日以上経過したら強制 `release()` する hard cap**
   - 理由: `updated_at` はコメントで更新されるため外部ユーザーによる孤児 pinning DoS リスクあり、採用しない
   - 7 日 hard cap は外部攻撃者が無限に running 状態を引き延ばせないことを保証

**per-tick API cap**: `gh issue view` 呼び出しは 1 tick あたり最大 `rollback_gh_fetch_cap` (default 10) 件に制限。超過分は次 tick に持ち越す。

### ④ `_check_recovery_markers(now)`

`<state_root>/recovery/*` を走査し `mark_failed` 失敗 issue を再評価する。

各 marker について対応 issue の状態:
- **closed** (`mark_done` 完了済み) → マーカー削除（後片付け不要）
- `claude-auto` **無し** → マーカー削除（既に人間が対処済み）
- `claude-auto` のみ → マーカー削除、次 tick で通常 claim 対象
- `claude-auto + running/review` → `release(slug)` で claude-running/review を外し、その後マーカー削除。次 tick で再評価
- `claude-auto + failed-{transient,permanent}` → マーカー削除（前回試行が遅延して成功していた、または人間が手動で付与）

**per-tick API cap**: step ③ と合算で `rollback_gh_fetch_cap` (default 10) 件まで。超過分は次 tick に持ち越す。

**Stale marker 7 日 TTL**: mtime が 7 日以上経過した marker は「stale / bug」として warn log + 削除する（無限残留防止）。

**マーカー削除の atomicity**: マーカー削除は上記判定後の最後のステップ。削除前にクラッシュしても次 tick で同じ判定が冪等に走るため問題ない。

### ⑤ `_check_closed_with_labels(now)`

closed issue に `claude-*` ラベルが残っていれば掃除する (`mark_done` の部分失敗 recover):

```
gh issue list --state closed --label claude-auto --json number --limit 100
# 各 issue について label cleanup を実行 (mark_done step 3 の再実行)
```

---

## Parallel Precedence

`parallel_worktree_limit` と `max_parallel` の関係は [`config-defaults.md`](config-defaults.md) の precedence 表を参照。実効上限は `effective_parallel = min(max_parallel, parallel_worktree_limit)`。
