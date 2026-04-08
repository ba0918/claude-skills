# github-issue Polling Contract Unification (Phase B)

**Cycle ID:** `20260408164019`
**Started:** 2026-04-08 16:40:19
**Status:** 🟢 Complete (all 10 steps done, 17/18 tests verified mechanically)
**Issue:** 20260408152003_github-issue-polling-unification
**Source Plan (Phase A):** [docs/plans/20260408150529_polling-pattern-unification.md](20260408150529_polling-pattern-unification.md)

---

## 📝 What & Why

Phase A で確立した共通契約 `skills/shared/references/polling-pattern.md` に `skills/github-issue/` を準拠させるリファクタ。`github-issue` 側に点在する状態機械・安全ブレーキ・tick 仕様は共通契約へ直リンク参照化し、label adapter / Codex gate / fail-closed merge 等の **GitHub 固有部分のみ** を local references に残す。併せて `claude-failed` ラベルを `claude-failed-transient` / `claude-failed-permanent` に二分割し、Phase A の `classify_failure` 純関数と整合させる。

Phase A 完了時に team review の Pragmatist BLOCK を解消するためスコープから切り出した Phase B 本体に該当する。

## 🎯 Goals

- `github-issue` が共通契約 §2/§3/§4/§6/§7 を**直リンク参照のみ**で表現（本文複製ゼロ）
- `claude-failed` → `claude-failed-transient` / `claude-failed-permanent` への二分割
- 旧 `claude-failed` を `claude-failed-permanent` の alias として維持（**読み込み時 OR + precedence rule、書き込み時は単一 `gh issue edit` の atomic dual-write + verification**）
- `polling-adapter.md` [NEW] で Label adapter として Interface Table (§3) 全メソッドを網羅実装
- **Retry state は FS 側の state_root に永続化**し、GitHub issue comment への state 埋め込みを廃止（race condition / 信頼境界バイパス回避）
- `commands/github-issue-polling.md` のフラグを `commands/issue-polling.md` と完全一致（フル書き換え、現 stub 状態からの脱却）
- FS adapter (Phase A) ↔ Label adapter (Phase B) の Interface Table 一致を**機械判定可能なチェックリスト**で検証
- plugin.json は **minor bump**（1.13.0 → 1.14.0）。alias 廃止 exit strategy と downgrade 非対応を明記

## 🚫 Out of Scope

- 共通契約 `polling-pattern.md` 自体の変更（Phase A で確定、drift 防止規約 §11 により本 cycle では触らない）
- Phase A の純関数仕様の変更
- `bypass-permissions` でのラルフループ運用検証（FS/Label 両 adapter が揃ってから別 cycle）
- alias 廃止 cycle（別途 issue 化、本 plan では**廃止条件**と downgrade ポリシーの記録のみ）
- 複数ホストからの分散 polling（本 plan は**単一ホスト前提**。複数ホスト対応は Phase C 以降）

## 📐 Design

### Execution Model Assumption (重要)

**本 adapter は単一ホスト・単一プロセスのラルフループ前提**とする。理由:
- Claim は「local lockfile + GitHub label」の混合 consistency domain であり、複数ホスト間で GitHub label だけを根拠にした排他は実現できない（post-verify レースあり）
- Retry state を FS に置く都合で、複数ホストから同 repo を polling すると state 不整合
- 複数ホスト対応が必要な場合は Phase C で「正本を GitHub 側に寄せた再設計」を行う

この前提は `polling-adapter.md` 冒頭 `## Assumptions` と SKILL.md Polling Workflow 前段に明記する。

### Layer Alignment

```
Layer 0: Shared Contract
  skills/shared/references/polling-pattern.md   [unchanged]
    ↑ 章番号付き直リンク参照のみ
Layer 1: State Adapter (Label)
  skills/github-issue/references/
    polling-adapter.md          [NEW]  Label adapter — Interface Table §3 の実装 + FS retry state + claim 3段防御
    label-spec.md               [M]    Labels 表 failed 二分割 + Backward Compat セクション。transition table は §2 直リンク
    cleanup-spec.md             [M]    .STOP / SIGINT trap / orphan recovery の共通仕様を §6 直リンクに置換
    codex-review-loop.md        [M]    normalize_github_error + classify_failure 呼び出し、alias 統合は revert
    config-defaults.md          [M]    §10 重複のみ削除、parallel_worktree_limit は GitHub 固有として保持
Layer 2: Orchestration
  skills/github-issue/SKILL.md  [M]    契約直リンク化、Polling Workflow は adapter method 呼び出しの薄い orchestrator
Layer 3: Command
  commands/github-issue-polling.md [M] stub → issue-polling と完全同形式へフル書き換え
```

### Label Mapping (Phase A 純関数 ↔ GitHub ラベル)

| 共通契約 State (§2) | GitHub ラベル集合 | 備考 |
|---|---|---|
| `ready` | `{claude-auto}` のみ | `claude-running` / `claude-review` / `claude-failed-*` / `claude-failed` 非付与 |
| `running` | `{claude-auto, claude-running}` | 初期 running |
| `running` (substate: review) | `{claude-auto, claude-running, claude-review}` OR `{claude-auto, claude-review}` | **GitHub 固有中間状態**。共通契約 §2 の `running` に subsume される。`is_running(labels) := "claude-running" ∈ labels OR "claude-review" ∈ labels` |
| `done` | （close 済み）| close と同時に全 `claude-*` 削除 |
| `failed/transient` | `{claude-auto, claude-failed-transient}` (+ alias `claude-failed` dual-write) | 次 tick で retry 可 |
| `failed/permanent` | `{claude-auto, claude-failed-permanent}` (+ alias `claude-failed` dual-write) | 人間判断待ち |
| `archives` | — | GitHub は close=archives 相当、ラベル不要 |

> **`claude-review` は共通契約 §2 の state 集合には現れない**。Label adapter 内部の running サブステートとして隔離し、`list_ready()` の client-side filter で `running/review` どちらを含む issue も除外する。**SSOT は `polling-adapter.md §Label Mapping`**（canonical 長期参照先）。本 plan の Label Mapping 表は設計根拠として併記されるが、plan 完了後 archive されるため SSOT とはしない。`label-spec.md` と本 plan は `polling-adapter.md §Label Mapping` への直リンクのみを持つ。

### Backward Compatibility Strategy

#### 読み込み時 (Precedence Rule 付き)

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

#### 書き込み時 (Atomic Dual-Write + Verification + Recovery)

**単一 `gh issue edit` コマンドで新旧ラベルを同時付与**する（API 呼び出し 2 倍化と部分失敗の両方を回避）:

```
mark_failed(slug, kind) -> Result:
  labels_add = ["claude-failed-transient", "claude-failed"] if kind==TRANSIENT
               else ["claude-failed-permanent", "claude-failed"]

  for attempt in [1, 2, 3]:  # 最大 3 回、間隔 0s/1s/2s の backoff
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
  # 重要: 0 ラベル放置禁止。crash-safe ordering で必ず next tick で回収されることを保証
  #
  # Crash-safe ordering invariant (下記順序を守ること):
  #   Step CA-1: recovery marker を FS に write_atomic で永続化（release より先）
  #   Step CA-2: release(slug) で claude-running / assignee を外す
  #
  # この順序で CA-1 と CA-2 の間でクラッシュしても:
  #   - marker は既に FS 上に存在 → next tick の rollback_orphans() step ④ が検出
  #   - claude-running は残ったままだが、次 tick の rollback_orphans() step ③ (48h) または
  #     step ④ (marker 検出で即時 release) で回収可能
  # 逆順 (release → marker) では release 後 marker 書き失敗 → 0 ラベル + marker なしで追跡不能。
  #
  # marker が書けない場合 (FS 障害) は fail-closed で polling abort。claude-running のまま
  # 残るが、次回起動時の rollback_orphans() が 48h 条件で回収する (data loss 0、latency 最大 48h)。
  warn_log(f"[mark_failed] verification failed after 3 attempts: {slug}")
  try:
    record_recovery_marker(slug)   # CA-1: FS marker を write_atomic 永続化
  except FsError:
    fail_closed("cannot write recovery marker — polling abort")
  release(slug)                    # CA-2: GitHub 上のラベル/assignee を外す (best-effort)
  return Err("dual_write_failed")  # 次 tick で rollback_orphans() step ④ が拾う

mark_done(slug):
  # 順序が重要: (1) PR merge → (2) issue close → (3) ラベル掃除
  # 各段階の失敗は次 tick で idempotent に再実行可能
  gh pr merge <PR> --squash --delete-branch
  gh issue close ${N}
  gh issue edit ${N} \
    --remove-label claude-auto \
    --remove-label claude-review \
    --remove-label claude-failed-transient \
    --remove-label claude-failed-permanent \
    --remove-label claude-failed
  # 部分失敗 (例: close 成功 + ラベル掃除失敗) は next tick の
  # rollback_orphans() が "closed issue with claude-* label" として検出し掃除

release(slug):
  gh issue edit ${N} --remove-label claude-running --remove-assignee @me
```

**許容される中間状態**:
- `mark_failed` 付与側: 0 ラベル（全失敗、recovery marker 付き）または 2 ラベル（正常）。1 ラベル状態は verify で検出して再試行。
- `mark_done` 削除側: 5 ラベル全部削除または 0 ラベルが正常。部分削除は precedence rule と next tick 掃除で吸収可能。
- **0 ラベル放置禁止**: `mark_failed` で最終的に verify が通らない場合、`<state_root>/recovery/{issue_number}` マーカーを置いて next tick の `rollback_orphans()` で必ず再評価させる。operator には warn ログで通知。

#### Recovery Marker (FS)

```
<state_root>/recovery/{issue_number}         # 空ファイル、mtime が作成時刻
```

`rollback_orphans(now)` は本ディレクトリをスキャンし、対応 issue が:
- **closed** (`mark_done` 完了済み) → マーカー削除（後片付け不要）
- `claude-auto` **無し** → マーカー削除（既に人間が対処済み）
- `claude-auto` のみ → マーカー削除、次 tick で通常 claim 対象
- `claude-auto + running/review` → `release(slug)` で claude-running/review を外し、その後マーカー削除。次 tick で再評価
- `claude-auto + failed-{transient,permanent}` → マーカー削除（前回試行が遅延して成功していた、または人間が手動で付与）

**マーカー削除の atomicity**: マーカー削除は上記判定後の最後のステップ。削除前にクラッシュしても次 tick で同じ判定が冪等に走るため問題ない。削除後に同 issue が再び dual-write 失敗した場合は新しい marker が作られる。

**マーカーの寿命**: 明示的な TTL は設けない（冪等 cleanup に依存）。ただし rollback_orphans 実行時に mtime が 7 日以上経過した marker は「stale / bug」として warn ログ + 削除する（無限残留防止）。

#### Migration Exit Strategy (廃止条件)

| Phase | バージョン | 状態 |
|---|---|---|
| 導入 | 1.14.0 | dual-write 開始、旧 reader も alias で検知可能 |
| 監視 | 1.14.x | `claude-failed` 単独付与 issue 件数を定期確認（手動） |
| 告知 | 1.15.0 | `label-spec.md` に「1.16.0 で alias 廃止」の告知を追加、同 release note 記載 |
| 廃止 | 1.16.0 以上 | alias 読み込み precedence を削除、旧 reader 非対応 |

**廃止条件**（いずれかを満たすこと、別 cycle の plan で確認）:
1. 全 `claude-failed` 単独 issue を新ラベルに migrate 完了
2. 1.15.0 告知から最低 4 週間経過
3. `require_alias_compat` config が `false` にできる運用体制確立

**Downgrade ポリシー**: 1.14.0 以降から 1.13.x への downgrade は**非対応**。新ラベル付き issue が旧 reader から見えなくなり silent data loss となるため、`plugin.json` release note と `label-spec.md` に明記する。

### Interface Table 実装マッピング (Label adapter)

| Interface (§3) | Label adapter 実装 |
|---|---|
| `list_ready(limit)` | `gh issue list --label claude-auto --state open --json number,title,labels,author --limit {limit}` を**単一呼び出し**。client-side で `claude-running` / `claude-review` / `claude-failed-*` / `claude-failed` (precedence 適用後) を除外。**filter 後の件数が limit 未満でも再 fetch しない**（次 tick で再取得、repeat fetch 禁止。fetch storm 防止。stale state の伝播は `tick_interval_loop_mode = 30s` の範囲内に限定される） |
| `claim(slug)` | 3 段防御は **polling-adapter 内部に隠蔽**。SKILL.md は `claim(slug)` を呼ぶだけ。内部順序: ① `<state_root>/claim/{issue_number}.lock` に flock(2) (non-blocking、失敗なら LockBusy → quiet abort) → ② `gh issue edit --add-assignee @me --add-label claude-running` → ③ `gh issue view` で `assignees` と `labels` を re-verify。失敗は `ClaimFailed{reason}` で quiet abort。lockfile は process 終了時に自動解放、stale は `rollback_orphans()` が 5 分経過条件で削除 |
| `release(slug)` | `gh issue edit --remove-label claude-running --remove-assignee @me` (best-effort)。失敗しても警告ログのみ |
| `mark_done(slug)` | `gh pr merge --squash --delete-branch` → `gh issue close` → `gh issue edit --remove-label claude-auto --remove-label claude-review --remove-label claude-failed-transient --remove-label claude-failed-permanent --remove-label claude-failed` (単一 edit) |
| `mark_failed(slug, kind)` | **単一 `gh issue edit`** で新旧ラベルを atomic dual-write（Backward Compat §書き込み時 参照）+ verification |
| `retry_count(slug)` | **FS state 参照**: `<state_root>/retry/{issue_number}.json` を `write_atomic` と相補の read (fsync なしでよい) で読み `{retry_count, last_failed_at, run_id}` を返す。ファイル無ければ `0` (初回扱い)。**JSON parse 失敗時は warn log + ファイルを `<issue_number>.json.corrupt.{ts}` にリネームして隔離 + `0` (再作成)**。2 回連続で parse 失敗した場合 (隔離後も新 write が再度 parse 失敗) は `fail_closed("retry state corruption")` で polling abort。`run_id` フィールドは UUID v4 形式、read 時に `^[0-9a-f-]{36}$` 正規表現で検証し不一致なら warn + 無視 |
| `increment_retry(slug)` | **FS state 更新**: 上記 `write_atomic` 手順で `.tmp` → fsync → rename → parent fsync。単一プロセス前提で read-modify-write の atomicity は flock で保護。comment 投稿は廃止（race condition + 信頼境界バイパス両方を排除） |
| `kill_file_path()` | `<state_root>/.STOP` / `.STOP.hard`。`state_root` 解決は下記 `### state_root Resolution` を参照 |
| `archive_month_boundary()` | GitHub は close=archive のため **no-op**。ただし `.last_archive_month` キャッシュは更新する（共通契約 §9 の unchanged invariant 維持） |
| `rollback_orphans(now)` | 5 段階で実行 (各段階 early return なし、全部走り切る): ① worktree 孤児 (既存 cleanup-spec.md の 24h + merged 条件) → ② `<state_root>/claim/*.lock` の stale 検出 (5 分超過 + pid dead なら削除) → ③ `claude-running` 付きで 48h 超過（PR 未作成、`issue.created_at` 基準）の issue を `release()`。PR 存在時は `pr.head commit pushed_at` （なければ `pr.created_at`）を基準にさらに 48h 待機。**いずれも `issue.created_at` から 7 日以上経過したら強制 `release()` する hard cap**（`updated_at` はコメントで更新されるため外部ユーザーによる孤児 pinning DoS リスクあり、採用しない） → ④ `<state_root>/recovery/*` マーカーを走査し `mark_failed` 失敗 issue を再評価 (precedence rule で正常化 or 再 `mark_failed` 試行) → ⑤ closed issue に `claude-*` ラベルが残っていれば掃除 (`mark_done` の部分失敗 recover)。**③④ の GitHub API 呼び出しは 1 tick あたり最大 10 件に制限**（`config-defaults.md` の `rollback_gh_fetch_cap`）、超過分は次 tick に持ち越す |
| `sanitize_slug(raw)` | 共通契約 §4 の `sanitize_slug` を呼ぶだけ。Label adapter 固有の `sanitize_repo_slug` は `nameWithOwner → path segment` 変換専用として併存 |

### state_root Resolution (詳細定義)

#### 取得とフォールバック

```python
def state_root(name_with_owner: str) -> Path:
  # 1. XDG fallback chain
  xdg_base = env("XDG_STATE_HOME") or expanduser("~/.local/state")

  # 2. Repo slug (path segment 変換)
  repo_slug = sanitize_repo_slug(name_with_owner)

  # 3. Clone ID: git remote URL を正規化後に SHA-1 16 hex 文字で識別
  git_remote_url = fetch_git_remote_url()        # 下記参照
  normalized = normalize_git_url(git_remote_url) # 下記参照
  clone_id = sha1(normalized).hex[:16]            # 64-bit 空間、birthday bound で 1% 衝突は ~6.1e8 clones
                                                  # 単一マシン上の同一 repo 複数クローンという非常に少数シナリオで十分

  target = path.join(xdg_base, "claude-skills", "github-issue", f"{repo_slug}-{clone_id}")

  # 4. 作成 (idempotent)
  mkdir(target, mode=0o700, parents=True, exist_ok=True)

  # 5. 衝突検知: stored_url が存在するなら mismatch で fail-closed
  #    初回作成時は O_CREAT|O_EXCL で排他作成し TOCTOU を回避
  stored_url_file = target / ".clone_url"
  if stored_url_file.exists():
    if read(stored_url_file) != normalized:
      fail_closed(f"state_root clone_id collision: {target}")
  else:
    # write_atomic 相当の排他作成 (複数プロセス同時初回起動時の race 回避)
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

  return target

def fetch_git_remote_url() -> str:
  # Primary: git remote get-url origin
  try:
    return shell("git remote get-url origin").strip()
  except GitNotFound:
    pass
  # Fallback: gh repo view (確実にリポジトリコンテキストが存在する場合)
  try:
    return shell("gh repo view --json url --jq .url").strip()
  except GhError:
    fail_closed("cannot resolve git remote URL")

def normalize_git_url(url: str) -> str:
  # 正規化ルール (同一 repo の SSH/HTTPS 表記揺れを吸収):
  # 0. 文字集合検証 (path traversal / shell metachar 注入を拒否)
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

#### 作成失敗時の挙動（fail-closed）

| 失敗ケース | 挙動 |
|---|---|
| `permission denied` (mkdir) | warn log + polling abort (fail-closed) |
| `quota exceeded` | 同上 |
| `parent 作成エラー` | 同上 |
| `clone_id collision` (stored_url mismatch) | warn log + polling abort + operator 通知 |
| `git remote 取得失敗` | polling abort (fail-closed) |
| `unsupported FS` (NFS / CIFS / tmpfs / WSL DrvFs 経由) | **warn log + polling abort (fail-closed)**。fsync/rename atomicity が保証されないため silent data corruption を構造的に排除 |
| `ownership 不一致` (`stat.uid != getuid()`) | fail-closed |

本 adapter は **ephemeral fallback を持たない**。state_root が使えない環境では polling 自体を起動させないことで、retry_count 不整合や silent data loss を構造的に防ぐ。ユーザー向けトラブルシューティング (XDG_STATE_HOME 指定方法等) は `commands/github-issue-polling.md` の Troubleshooting 節に記載。

#### `state_root/` 配下の構造と permission 契約

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

#### Platform Assumptions & Durability 契約

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
- **Unsupported / fail-closed**: NFS, CIFS, tmpfs（rename atomicity や fsync 意味論が非標準）、Windows DrvFs 経由の WSL mount（permission mode 不反映）。`statfs(2)` で判定し、検出時は warn log + polling abort（silent data corruption を防ぐため）
- **ownership 検証**: state_root を開いた時に `stat(path).uid != getuid()` なら fail-closed（共有 HOME で他ユーザーが作った state_root に誤って書き込まない）
- **stale lockfile**: `<state_root>/claim/{N}.lock` は pid を書き、flock(2) で保持。プロセス終了時に自動解放。pid が死亡している場合は `rollback_orphans()` が 5 分以上経過を条件に削除

#### `.polling-initialized` Lifecycle

- **作成責務**: `polling-adapter` が**初回 tick 成功後**に自動作成（`write_atomic` 経由）
- **tick 成功の定義**: tick が `halt_reason=None` または `halt_reason="dry_run"` で完了した時点
- **更新**: 一度作成されたら更新しない（mtime は最終初期化時刻として残る）
- **削除**: ユーザーが `rm <state_root>/.polling-initialized` で手動削除すると次 tick が再度 `--dry-run` 強制（意図的な再確認用途）
- **alias 廃止時**: 削除対象ではない（1.16.0 の alias 廃止 cycle でもそのまま残す）

### error_kind Enum (詳細定義)

`mark_failed` / `classify_failure` で使用する `error_kind` は以下の閉じた enum に限定する。未知値は `"unknown"` に正規化し、`classify_failure` は `unknown → Permanent` で fail-closed する:

```
error_kind ∈ {
  # Transient (retry 可能)
  "network",           # Network I/O error, HTTP 5xx, SIGPIPE, broken pipe
  "rate_limit",        # GitHub/Codex API rate limit (HTTP 403 rate, 429)
  "timeout",           # Codex or gh CLI timeout
  "lock",              # lockfile contention (同一マシン内他プロセスが保持)
                       # **SPECIAL**: lock エラーは transient 分類だが `failed_streak`
                       # にはカウントしない (silent skip)。別プロセスが処理中の状況であり
                       # issue 固有の失敗ではないため。tick 全体の失敗扱いにすると
                       # safety brake が誤発動する

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

`classify_failure` 側の分類（純関数）:
- Transient: `{network, rate_limit, timeout, lock}` (4 種)
- Permanent: `{test, compile, abort, lgtm_parse_fail, sanitize_failed, security, not_found, tool_missing, unknown}` (9 種)

**`failed_streak` カウント規約** (共通契約 §6 safety brake への GitHub adapter 固有追加):
- `lock` は「別プロセスが処理中」を意味するため、当該 issue の skip として扱い `failed_streak` をインクリメントしない
- それ以外の error_kind はすべて `failed_streak` をインクリメントする
- この挙動は `polling-adapter.md §error_kind Handling Rules` に明記し、テスト (手動目視) で遵守を確認する

### normalize_github_error Layer (詳細定義)

`classify_failure` は純関数（§4）なので、外部の GitHub/Codex エラーを直接受け取れない。effectful → pure の変換層を `codex-review-loop.md` に定義する:

```
normalize_github_error(raw_exc_or_response) -> error_kind:
  match raw_exc_or_response:
    # Network layer
    case NetworkError | ConnectionRefused | DNSError:            return "network"
    case HTTPStatus(502|503|504):                                 return "network"
    case BrokenPipeError | SIGPIPE:                               return "network"

    # Rate limit
    case RateLimitError:                                          return "rate_limit"
    case HTTPStatus(429):                                         return "rate_limit"
    case HTTPStatus(403) if "rate limit" in body:                 return "rate_limit"
    case HTTPStatus(403):                                         return "security"  # auth 失敗

    # Timeout
    case TimeoutError | SubprocessTimeout:                        return "timeout"

    # Lock
    case LockBusy | FileExistsError(path=lockfile):               return "lock"

    # Resource not found
    case HTTPStatus(404):                                         return "not_found"

    # Tooling
    case FileNotFoundError(filename="gh" | "git"):                return "tool_missing"
    case GhCLIVersionError:                                       return "tool_missing"

    # Codex/Review specific
    case CodexJsonParseError:                                     return "lgtm_parse_fail"
    case SecretScannerHit | AuthDenied:                           return "security"

    # Build/test
    case TestFailure | AssertionError:                            return "test"
    case CompileError | BuildError:                               return "compile"
    case ExplicitAbort:                                           return "abort"
    case SanitizeRejected:                                        return "sanitize_failed"

    # Fallback (未知は必ず permanent 側に倒す)
    case _:                                                       return "unknown"
```

**Exhaustive match guarantee**: `normalize_github_error` は必ずすべての exception path で enum 値を返す（default → `"unknown"`）。`classify_failure` は enum 集合が閉じていることを前提に網羅判定する。新規 exception 型を追加する PR は必ず `normalize_github_error` の case を追加するレビュー規約とする（`codex-review-loop.md` に明記）。

`mark_failed` 呼び出し側は常に `classify_failure(normalize_github_error(exc))` の順で経由する。

### parallel_worktree_limit と max_parallel の関係 (Precedence Rule)

両者の責務は異なるが、同 tick 内で競合する場合は **`min(max_parallel, parallel_worktree_limit)` を実効上限**とする:

- `max_parallel` (共通契約 §10): tick あたり claim 上限。issue 単位の論理的な並行度
- `parallel_worktree_limit` (GitHub 固有): worktree 物理リソース上限。Phase A の `parallel-cycle` skill に渡す並列数

```
effective_parallel = min(max_parallel, parallel_worktree_limit)
list_ready(effective_parallel)  # claim 数自体を物理上限に合わせる
```

これにより claim だけ進んで worktree が wait する状態を防ぐ。`parallel_worktree_limit` の default は 1 のため、明示的に上書きしない限り直列実行となる。`config-defaults.md` に precedence rule を表で明記する。

### Files to Change

```
skills/github-issue/
  SKILL.md                          [M] 契約直リンク化、Polling Workflow を adapter method orchestrator に書き換え（3段防御は adapter に隠蔽）
  references/
    polling-adapter.md              [NEW] Label adapter: Assumptions / Interface Table 実装 / state_root / error_kind enum / FS retry state spec
    label-spec.md                   [M] Labels 表に failed 二分割を追加、Backward Compat セクション。transition table は共通契約 §2 への直リンクに置換（本文複製禁止）
    cleanup-spec.md                 [M] .STOP/SIGINT/orphan recovery の共通仕様記述を削除し §6 直リンク。固有: sanitize_repo_slug / Worktree 命名 / 24h 検出 / Partial Claim Rollback のみ残す
    codex-review-loop.md            [M] normalize_github_error 関数追加 → classify_failure 呼び出し。codex_consecutive_failure_threshold は独立保持（alias 統合 revert）
    config-defaults.md              [M] §10 重複のみ削除。parallel_worktree_limit / min_rate_limit_remaining / max_review_iterations / max_diff_lines / codex_consecutive_failure_threshold / auto_merge_strategy / codex_required_for_merge / require_author_association / enable_base64_scan は GitHub 固有として保持

commands/
  github-issue-polling.md           [M] stub → issue-polling.md と同形式へフル書き換え（frontmatter description 刷新 + Flags + Initial Run Policy + Safety Brakes + References）

CLAUDE.md                           [M] github-issue スキル行を polling 対応として更新、ポーリングパターン段落に FS adapter / Label adapter 併記
.claude-plugin/plugin.json          [M] 1.13.0 → 1.14.0

docs/issues/
  20260408152003_github-issue-polling-unification.md  [M → archives] cycle 完了時に **Issue:** フィールド経由で auto-close
```

**Phase A Invariant** (変更禁止):
- `skills/shared/references/polling-pattern.md` 全体
- `skills/issue/SKILL.md` および `skills/issue/references/` 配下
- 共通契約 §4 純関数 4 つの仕様

### Key Points (design-principles alignment)

- **§1 Compose Small Parts**: `polling-adapter.md` を Interface メソッド単位で節分け、各 5-20 行
- **§2 No Business Logic in Glue**: SKILL.md Polling Workflow は adapter メソッド呼び出しの薄い orchestrator に書き換え、分類ロジックは `classify_failure(normalize_github_error(exc))` に委譲
- **§3 Strict Layer Separation**: 共通契約 → Label adapter → SKILL → Command の単方向依存を守る。claim 3 段防御は adapter 内部実装の詳細として隔離
- **§5 DI**: Label adapter は共通契約の Interface Table を実装するだけ。SKILL.md は interface のみ知る
- **§6 Open-Closed**: Phase A の FS adapter / 純関数 / 契約を一切変更せず adapter のみ追加
- **§9 Security**: atomic dual-write + verification + precedence rule により silent inconsistency を構造的に排除。retry state を FS に置くことで信頼境界バイパス回避
- **Drift 防止 (契約 §11)**: label-spec.md / cleanup-spec.md から共通契約への直リンクを **章番号付き** で貼り、transition table / interface table / 純関数シグネチャを local reference で**再定義しない**

## 🔧 Implementation Steps

1. **polling-adapter.md 新規作成** — `skills/github-issue/references/polling-adapter.md` を作成。**見出しレベル規約: 主要節は H2 (`##`)、Interface メソッド単位のサブ節は H3 (`###`)**。以下を含む:
   - `## Assumptions` 節で「単一ホスト・単一プロセスのラルフループ前提」を冒頭明記
   - `## Interface Table` 節: 共通契約 §3 への直リンク + 上記実装マッピング表の詳細版。11 メソッドを H3 見出しで列挙 (`### list_ready(limit)` 〜 `### sanitize_slug(raw)`)
   - `## state_root Resolution` 節: XDG fallback + multi-clone 対策（SHA-1 16 hex 接尾辞）+ 作成失敗時の fail-closed + `.clone_url` の `O_CREAT|O_EXCL` 排他作成
   - `## FS Retry State` 節: `<state_root>/retry/{issue_number}.json` の schema と atomic rename 手順 + `run_id` (UUID v4) の生成/検証規約 + corrupt file 検出時の隔離リネーム仕様
   - `## error_kind Enum` 節: 13 種 enum + **`### error_kind Handling Rules`** サブ節で `lock` の `failed_streak` 非カウント規約を明記
   - `## Label Mapping` 節: **本節を canonical SSOT として** マッピング表を配置。plan / label-spec.md は本節への直リンクのみ
   - `## claim() 3 段防御` 節: adapter 内部実装の詳細（lockfile → gh edit → re-verify）。`issue_number` は整数であることを事前検証し非整数なら `fail_closed`
   - `## rollback_orphans Sub-Steps` 節: 5 段階を `_check_worktree_orphans()` / `_check_stale_locks()` / `_check_long_running()` / `_check_recovery_markers()` / `_check_closed_with_labels()` のプライベートサブメソッドに分解する設計方針を記載（各段の単体テスト可能性担保）
   - `sanitize_slug` vs `sanitize_repo_slug` の責務分離 canonical 記述は **`cleanup-spec.md` に 1 箇所置き、本ファイルからはリンク参照のみ**（DRY）
   - `archive_month_boundary` は GitHub では no-op である旨を明記

2. **label-spec.md 更新** — Labels 表に以下 2 行を追加:
   - `claude-failed-transient` / `claude-failed-permanent` の意味・付与/削除タイミング
   - 旧 `claude-failed` 行は「DEPRECATED alias (precedence: permanent)」として残す
   - **State × Event transition table の本文を削除**し、共通契約 §2 Transition Table への直リンクに置換（drift 防止 §11 遵守）
   - **`transition()` 擬似コードブロック (```コードフェンス) の本文を削除**し、共通契約 §4 への直リンクのみに置換（残存してないか Tests §Item で機械的に検証する）
   - Label Mapping 表は **`polling-adapter.md §Label Mapping` への直リンクのみ**（SSOT は polling-adapter.md、本ファイルで複製しない）
   - 新規「Backward Compatibility」節: precedence rule / atomic dual-write / invalid state 扱い / Migration Exit Strategy 表 / downgrade 非対応
   - 「alias 廃止予告」節: 1.16.0 で削除予定、条件と告知方法を記載

3. **cleanup-spec.md 整理** — **現状確認**: まず本ファイルを Read して以下記述の有無を確認し、存在するものだけ削除:
   - Kill file 仕様 (`.STOP` / `.STOP.hard`) — 存在すれば共通契約 §6.1 直リンクに置換
   - SIGINT / SIGTERM trap — 存在すれば共通契約 §6.3 直リンクに置換
   - Orphan recovery 純関数部分 — 存在すれば共通契約 §6.4 直リンクに置換
   - **責務分離 canonical 記述**: `sanitize_repo_slug` (path segment 専用) vs 共通契約 `sanitize_slug` (issue/state slug 用) の責務分離を本ファイルに **canonical として 1 箇所のみ** 記述（`polling-adapter.md` からは本ファイルへのリンクのみ）
   - 固有部分として残す: `sanitize_repo_slug()` 実装、Worktree 命名規約、24h 孤児検出条件、Partial Claim Rollback 手順（dual-write label 削除の順序を追記）

4. **codex-review-loop.md 更新** — 以下の変更:
   - **新規節 `## normalize_github_error`**: effectful → pure 変換層を定義（上記 Design セクション参照）
   - Codex failure 分類を `classify_failure(normalize_github_error(exc))` 呼び出しに統一
   - `error_kind` enum に準拠（polling-adapter.md §error_kind に直リンク）
   - **`codex_consecutive_failure_threshold` は独立パラメータとして保持**（`transient_retry_limit` への alias 統合は revert）。理由: 概念が異なる（前者は Codex API の連続失敗カウンタ、後者は issue 単位の retry 累積）。両者が alias だと無限ループの可能性
   - fail-closed `codex_required_for_merge` pre-flight check は現行維持

5. **config-defaults.md 整理** — 共通契約 §10 と重複する項目（`max_parallel` / `max_iter` / `max_wallclock` / `failed_streak_limit` / `transient_retry_limit` / `tick_interval_loop_mode` / `dry_run`）について、**現状確認して重複があれば削除、なければ注記追加のみ**。冒頭に「§10 を SSOT として参照」注記を追加。GitHub 固有値は全て保持 + 新規追加:
   - 既存保持: `max_review_iterations`, `parallel_worktree_limit`, `polling_interval`, `min_rate_limit_remaining`, `max_diff_lines`, `codex_review_timeout`, `codex_consecutive_failure_threshold`, `auto_merge_strategy`, `codex_required_for_merge`, `require_author_association`, `enable_base64_scan`
   - **新規追加**: `rollback_gh_fetch_cap` (default 10): `rollback_orphans()` step ③④ の 1 tick あたり `gh issue view` API 呼び出し上限。超過分は次 tick 持ち越し
   - `effective_parallel = min(max_parallel, parallel_worktree_limit)` precedence rule を表で明記
   - 特に `parallel_worktree_limit` は「worktree 並行数制御」として GitHub 固有の意味を持ち、§10 `max_parallel` とは異なる責務であることを注記

6. **SKILL.md リファクタ** — References 節に `polling-adapter.md` 追加。以下の変更:
   - Polling Workflow 冒頭に「単一ホスト前提」注記
   - Polling Workflow 本体を adapter method orchestrator に書き換え:
     ```
     Common Pre-checks → kill_file_path() check → rollback_orphans(now)
       → archive_month_boundary() (no-op) → list_ready(max_parallel)
       → claim(slug) for each → parallel-cycle 委譲
       → outcome → classify_failure(normalize_github_error(exc)) → mark_failed(slug, kind)
       → TickResult emit
     ```
   - 既存の「atomic claim 3 段防御」「孤児 worktree クリーンアップ」詳細は polling-adapter.md / cleanup-spec.md へ移動（SKILL.md からは削除）
   - 本文中の状態機械・安全ブレーキ記述は共通契約 §2 / §6 への**章番号付き直リンク**に置換
   - Cycle Workflow Step 9 失敗時処理を単一 `gh issue edit` の atomic dual-write + verification に修正
   - **当セクション追加分は 80 行以内**（60 行は厳しすぎる、8 行余裕持たせて 80 行に緩和）、詳細は references へ

7. **github-issue-polling.md コマンドフル書き換え** — 現状 stub からの完全刷新:
   ```markdown
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

   `<state_root>/.polling-initialized` が存在しない場合、`--dry-run` を強制する。state_root は
   `$XDG_STATE_HOME/claude-skills/github-issue/{repo_slug}-{clone_id}/` に解決される。

   ## Safety Brakes

   詳細は共通契約 `skills/shared/references/polling-pattern.md` §6 を参照。要点:
   - Kill file 2 系統: `<state_root>/.STOP` / `<state_root>/.STOP.hard`
   - 3 重ガード: `max_iter` / `max_wallclock` / `failed_streak`
   - 単一ホスト前提: 複数ホストからの分散 polling は非対応

   ## References

   - SKILL.md: `skills/github-issue/SKILL.md` Polling Workflow
   - 共通契約: `skills/shared/references/polling-pattern.md`
   - Label adapter: `skills/github-issue/references/polling-adapter.md`
   ```

8. **CLAUDE.md 更新** — 主要スキル表の `github-issue` 行を「Label adapter として共通契約に準拠、Phase B で polling 対応」と更新。ワークフロー設計パターン内 Polling パターン段落に「FS adapter (`skills/issue/`) と Label adapter (`skills/github-issue/`) の 2 実装がある。単一ホスト前提」を追記。共有リソース表は変更なし（polling-pattern.md は既に記載済み）

9. **plugin.json bump + 整合性チェック** — 1.13.0 → 1.14.0。以下を**チェックリスト形式で手動検証**（Tests セクション参照）:
   - 共通契約 §2 / §3 / §4 / §6 / §7 / §10 からの直リンクがすべて 404 しない（anchor まで確認）
   - polling-adapter.md の Interface メソッド集合が共通契約 §3 の 11 メソッドと完全一致（過不足ゼロ）
   - label-spec.md の transition table が削除され共通契約 §2 直リンクに置換されている
   - SKILL.md / references 間の相互リンクが切れていない
   - Downgrade 非対応の文言が plugin.json release note に記載されている

10. **issue auto-close** — cycle 完了時に `**Issue:** 20260408152003_github-issue-polling-unification` 経由で自動 archive。手動処理不要。plan 冒頭の Issue フィールドで指定済み。

## ✅ Tests (機械判定可能なチェックリスト 12 項目)

markdown-only リポジトリのため実行テストは不可だが、以下は**各項目に明示的な判定基準と検証コマンド例**を設けて目視漏れを防ぐ:

- [ ] **Interface Table 完全一致** — `polling-adapter.md` のメソッド H3 見出し集合 が共通契約 §3 Interface Table の 11 行見出しと**完全一致**。差集合を取って空であることを確認 (`grep '^### ' skills/github-issue/references/polling-adapter.md | head -20` と §3 行を diff)
- [ ] **Transition Table 非複製** — `label-spec.md` に State × Event table の本文が**存在しないこと** (`grep -E '\| *ready *\|' skills/github-issue/references/label-spec.md` がヒットしないこと)。**`transition()` 擬似コードフェンスも残存しないこと** (`grep -c '```' skills/github-issue/references/label-spec.md` が Backward Compat 節のコードブロック数以下)。共通契約 §2 への直リンクが 1 つ以上存在すること (`grep -c 'polling-pattern.md#' skills/github-issue/references/label-spec.md` ≥ 1)
- [ ] **Label Mapping SSOT canonical** — `polling-adapter.md §Label Mapping` が canonical SSOT。`label-spec.md` にはマッピング表の本文が**存在せず**、`polling-adapter.md` への直リンクのみが存在すること。plan にも「SSOT は polling-adapter.md」の注記がある。行数近似チェック: `grep -c '^|' skills/github-issue/references/polling-adapter.md` が適切な行数 (Label Mapping + Interface Table 分)
- [ ] **リンク整合性** — 本 plan で変更/追加した全ファイル間の相対リンク + 共通契約への章リンクが切れていないこと (`grep -oE '\]\([^)]+\)' file.md` で抽出後にファイル/anchor 存在検証)
- [ ] **Dual-write 単一コマンド確認** — `SKILL.md` と `label-spec.md` Backward Compat 節に「単一 `gh issue edit --add-label A --add-label B`」の記述と verification step、3 回 backoff 再試行が存在
- [ ] **Recovery Marker 規約存在** — `label-spec.md` または `polling-adapter.md` に `<state_root>/recovery/{N}` マーカー作成と `rollback_orphans()` 走査の記述
- [ ] **Precedence Rule 明記** — `label-spec.md` Backward Compat 節に `state_of_failure()` precedence 定義と invalid state の fail-closed 扱いが明記
- [ ] **Downgrade 非対応明記** — `label-spec.md` および `plugin.json` release note に「1.14.0 以降から 1.13.x への downgrade 非対応」が明記
- [ ] **Permission Mode 契約明記** — `polling-adapter.md` に dir 0700 / file 0600 / write_atomic (fsync + rename + parent fsync) / unsupported FS 一覧が記載
- [ ] **clone_id 衝突検出明記** — `polling-adapter.md` state_root 節に `.clone_url` mismatch fail-closed と SHA-1 16 hex の記述
- [ ] **error_kind enum 完全列挙** — `polling-adapter.md` に 13 種の enum と Transient/Permanent 分類表が記載 (network, rate_limit, timeout, lock, test, compile, abort, lgtm_parse_fail, sanitize_failed, security, not_found, tool_missing, unknown)
- [ ] **parallel precedence rule 明記** — `config-defaults.md` に `effective_parallel = min(max_parallel, parallel_worktree_limit)` が表記載
- [ ] **lock silent skip 規約明記** — `polling-adapter.md §error_kind Handling Rules` に `lock` が `failed_streak` にカウントされない旨の明記
- [ ] **rollback 7 日 hard cap 明記** — `polling-adapter.md §rollback_orphans` に「`issue.created_at` から 7 日以上経過で強制 release」の hard cap 記述
- [ ] **URL char set 検証明記** — `polling-adapter.md §state_root Resolution` に `normalize_git_url` の許可リスト検証 (`[a-zA-Z0-9._\-/:@]` のみ) と `..` 拒否の記述
- [ ] **`.clone_url` 排他作成明記** — `polling-adapter.md §state_root Resolution` に `.clone_url` 初回作成時の `O_CREAT|O_EXCL` 記述
- [ ] **unsupported FS fail-closed 明記** — `polling-adapter.md §Platform Assumptions` に NFS/CIFS/tmpfs/WSL DrvFs 検出時の polling abort (warn のみではない) 記述
- [ ] **corrupt retry state 隔離明記** — `polling-adapter.md §FS Retry State` に corrupt JSON 検出時の `.corrupt.{ts}` 隔離リネーム + 2 回連続 parse 失敗で fail-closed の記述
- [ ] **`rollback_gh_fetch_cap` 明記** — `config-defaults.md` に default 10、`rollback_orphans` step ③④ の per-tick API 上限記述
- [ ] **`rollback_orphans` サブメソッド分解方針明記** — `polling-adapter.md §rollback_orphans Sub-Steps` に 5 段階のプライベートサブメソッド分解方針記述

> Layer 単位の単体テストは Phase A 同様、本リポジトリでは記述せず契約準拠のみを保証する。

## 🔒 Security

- [ ] **Atomic dual-write + 3 回 backoff verification + Recovery Marker**: `mark_failed` は単一 `gh issue edit` で新旧ラベルを同時付与、書き込み後に label 集合を再取得して verification。不一致時は最大 3 回 backoff 再試行 (0s/1s/2s)。最終失敗時は `<state_root>/recovery/{N}` マーカー + `release(slug)` で次 tick 再評価へ確実に戻す。**0 ラベル放置を構造的に防ぐ**
- [ ] **Precedence rule + invalid state fail-closed**: `state_of_failure()` 関数の実装、両方のラベルが同時に付いた場合は permanent 扱い、warn ログ
- [ ] **Retry state を FS に移動**: GitHub issue comment への `[polling-state]` JSON 投稿を**廃止**。信頼境界バイパス（外部ユーザーによる偽装 comment）と race condition を両方とも排除
- [ ] **state_root 絶対パス解決 + 衝突検知**: `$XDG_STATE_HOME` → `~/.local/state` fallback、`git remote get-url origin` → `gh repo view --json url` の 2 段 fetch、URL 正規化（SSH/HTTPS 統一、trailing slash/.git 除去）、SHA-1 16 hex（64-bit）clone_id、`.clone_url` mismatch 検知で fail-closed
- [ ] **FS state permission 契約**: dir mode 0700 / file mode 0600、`write_atomic` (fsync + rename + parent fsync)、`stat.uid != getuid()` で fail-closed (共有 HOME 対策)、stale lockfile は 5 分 + pid dead 条件で削除
- [ ] **Unsupported FS 明記**: NFS / CIFS / tmpfs / WSL DrvFs は非対応、warn ログ + fail-closed
- [ ] **error_kind enum 制限**: 13 種の閉じた集合、未知値は `"unknown"` に正規化、`classify_failure` は `unknown → Permanent` で fail-closed
- [ ] **`sanitize_repo_slug` と共通契約 `sanitize_slug` の責務分離**: 前者は `owner/repo` → path segment 変換専用、後者は issue slug / state slug 用。混同禁止を polling-adapter.md と cleanup-spec.md の両方に注記
- [ ] **claim 責務境界 + lockfile path**: 3 段防御は polling-adapter 内部実装。lockfile path は `<state_root>/claim/{N}.lock`、flock(2) 非ブロッキング、process 終了で自動解放、stale は orphan recovery が削除。SKILL.md は `claim(slug)` を呼ぶだけ。**単一ホスト前提**を冒頭に明記
- [ ] **Partial Claim Rollback 拡張**: 既存規約に加え、dual-write label 削除順序（`-transient -permanent -claude-failed` の順）を追記
- [ ] **`codex_consecutive_failure_threshold` 独立保持**: `transient_retry_limit` への alias 統合は revert。両者の概念が異なるため
- [ ] **normalize_github_error exhaustive match**: 外部例外 → pure error_kind の変換を `codex-review-loop.md` に詳細定義（network/rate_limit/timeout/lock/test/compile/abort/lgtm_parse_fail/sanitize_failed/security/not_found/tool_missing/unknown の全 case）、新規例外追加時は case 追加を必須化
- [ ] **mark_done multi-step idempotency**: `gh pr merge → gh issue close → gh issue edit (label 掃除)` の 3 段は順序実行、各段の失敗は次 tick の `rollback_orphans()` step ⑤ (closed issue 残ラベル掃除) で recover
- [ ] **`.polling-initialized` lifecycle**: polling-adapter が初回 tick 成功後に `write_atomic` で自動作成 (mode 0600)、ユーザー手動削除で再 dry-run 強制
- [ ] **parallel precedence**: `effective_parallel = min(max_parallel, parallel_worktree_limit)` で claim と worktree の整合
- [ ] **Downgrade 非対応明記**: 1.14.0 以降から 1.13.x への downgrade は silent data loss のため非対応

## 🔍 Review Reflections

### Round 1 (initial review)

- **Reviewed:** 2026-04-08
- **Verdict:** WARN (Max score 74/100, Security)
- **Refined:** 2026-04-08

#### Round 1 主要修正事項

| # | 修正内容 | 指摘者 |
|---|---|---|
| 1 | dual-write を単一 `gh issue edit` コマンド + verification + precedence rule に変更（API 2 倍化と partial failure を両方解消） | Security / Performance / Completeness / Codex (critical) |
| 2 | Retry state を GitHub comment から FS state_root (`<state_root>/retry/{N}.json`) に移動（race condition + 信頼境界バイパス両方排除） | Security / Feasibility / Performance / Completeness / Codex (critical) |
| 3 | label-spec.md の State × Event transition table 本文を削除、共通契約 §2 直リンクに置換（drift 防止 §11 遵守） | Architecture / Feasibility (critical) |
| 4 | `state_root` 解決に XDG fallback + multi-clone SHA-1 接尾辞を追加、作成失敗時は fail-closed | Security / Completeness (critical) |
| 5 | `codex_consecutive_failure_threshold` の alias 統合を revert、独立パラメータとして維持 | Security / Performance |
| 6 | `claude-review` 中間状態を Label adapter 内部 running substate として Label Mapping 表に明示 | Security / Architecture |
| 7 | `list_ready` の early termination を「単一 API 呼び出し、filter 後 limit 未満でも repeat fetch 禁止」に明確化 | Performance |
| 8 | claim 3 段防御を polling-adapter.md 内部実装として隔離、SKILL.md は `claim(slug)` のみ呼ぶ Layer Separation | Architecture |
| 9 | `error_kind` enum を閉じた集合として plan / polling-adapter.md に定義 | Security |
| 10 | `normalize_github_error` effectful→pure 変換層を codex-review-loop.md に追加 | Codex |
| 11 | alias 廃止 exit strategy 表 + downgrade 非対応ポリシーを明記 | Codex / Completeness |
| 12 | Tests を 4 項目 (目視) → 7 項目 (機械判定可能なチェックリスト) に拡張 | Architecture / Codex |
| 13 | `commands/github-issue-polling.md` をフル書き換え（現状 stub → issue-polling.md 同形式） | Completeness |
| 14 | `parallel_worktree_limit` を共通契約 §10 との重複判定から除外、GitHub 固有として保持 | Performance / Architecture |
| 15 | 単一ホスト前提を plan / polling-adapter.md / SKILL.md / command の 4 箇所に明記（Codex claim 一貫性ドメイン指摘） | Codex |
| 16 | SKILL.md Polling Workflow 追加分上限を 60 → 80 行に緩和（実現可能性確保） | Architecture |

### Round 2 (post-refine review)

- **Reviewed:** 2026-04-08
- **Verdict:** Architecture PASS (87), 他次元 WARN (新規 issue 浮上)
- **Refined:** 2026-04-08

#### Round 2 主要修正事項

| # | 修正内容 | 指摘者 |
|---|---|---|
| 17 | dual-write を 3 回 backoff (0/1/2s) + 失敗時 `<state_root>/recovery/{N}` マーカー作成 + `release(slug)` で「0 ラベル放置」を構造的排除 | Codex / Security (critical) |
| 18 | `clone_id` を SHA-1 8 hex → 16 hex (32-bit → 64-bit 空間) に拡張、`.clone_url` mismatch fail-closed を追加 | Codex / Security (critical) |
| 19 | FS state permission 契約: dir 0700 / file 0600 / `write_atomic` (fsync + rename + parent fsync) / ownership 検証 / unsupported FS 一覧 | Codex / Security (critical) |
| 20 | `git_remote_url` 取得手順 (`git remote get-url origin` → `gh repo view --json url` 2 段) と URL 正規化関数 (`normalize_git_url`) を明示 | Codex / Security |
| 21 | claim lockfile path を `<state_root>/claim/{N}.lock` に明示、flock(2) 非ブロッキング、stale 5 分 + pid dead 削除 | Security / Completeness |
| 22 | `.polling-initialized` lifecycle: polling-adapter が初回 tick 成功後に自動作成、手動削除で再 dry-run | Completeness |
| 23 | `error_kind` enum を 10 → 13 種に拡張 (security, not_found, tool_missing 追加)、Transient/Permanent 分類更新 | Feasibility / Completeness |
| 24 | `normalize_github_error` exhaustive match table を詳細化 (HTTP 5xx, 429, 403 rate vs auth, SIGPIPE, FileNotFound, GhCLIVersionError 等) | Feasibility |
| 25 | `mark_done` 3 段順序 (PR merge → close → label 掃除) と部分失敗時の next tick recover (rollback_orphans step ⑤) | Security |
| 26 | `parallel_worktree_limit` と `max_parallel` の precedence rule: `effective_parallel = min(...)` | Feasibility / Performance |
| 27 | `rollback_orphans()` を 5 段階 (worktree / stale lock / running 48h / recovery marker / closed 残ラベル) に拡張 | Performance / Security |
| 28 | Tests を 7 → 12 項目に拡張、各項目に検証コマンド例を追加 | Feasibility / Completeness |

### Round 3 追加修正 (Codex NEEDS_REVISION 対応)

| # | 修正内容 | 指摘者 |
|---|---|---|
| 29 | `mark_failed` の compensating action に **crash-safe ordering invariant** を明記: marker write (CA-1) → release (CA-2) の順序。逆順では release 後 marker 書き失敗で追跡不能になる | Codex (NEEDS_REVISION) |
| 30 | marker write 失敗時は fail-closed で polling abort、claude-running 残存は次回起動時 48h rollback_orphans で回収 (data loss 0, latency 最大 48h) | Codex |
| 31 | Recovery Marker 削除条件を 5 ケースに拡張（closed / no claude-auto / claude-auto only / running+review / failed-* 付き）と stale marker 7 日 TTL 追加 | Codex |
| 32 | Platform Assumptions 節を追加: 純 POSIX 準拠ではなく **Linux/macOS local FS 前提**を明記。flock(2) は BSD 拡張、FS 種別判定は OS 依存 API | Codex |

### Round 4 (team-cycle AgenticTeam review)

- **Reviewed:** 2026-04-08
- **Verdict:** APPROVED WITH CONCERNS（BLOCK 0、WARN のみで早期収束）
- **Reviewers:** 4/4 (Security / Performance / Architect / Pragmatist)
- **Discussion rounds:** 1 (early convergence — 全論点 WARN 以下)

| # | 修正内容 | 指摘者 |
|---|---|---|
| 33 | `normalize_git_url` に URL 文字集合許可リスト検証 (`[a-zA-Z0-9._\-/:@]` のみ、`..` 拒否) を追加。パスインジェクション耐性強化 | Security |
| 34 | `.clone_url` 初回作成を `O_CREAT|O_EXCL` 排他作成に変更。複数プロセス同時初回起動時の TOCTOU を排除 | Security |
| 35 | `rollback_orphans` step ③ の 48h 基準を `updated_at` → `created_at` / PR は `head commit pushed_at` に変更。更に **`issue.created_at` から 7 日超過で強制 release の hard cap** を追加（外部ユーザーコメントによる孤児 pinning DoS 対策） | Security |
| 36 | Label Mapping SSOT を **`polling-adapter.md §Label Mapping` に一本化**（plan archive 後の SSOT 消失対策）。`label-spec.md` は直リンクのみ | Architect |
| 37 | `sanitize_slug` vs `sanitize_repo_slug` の責務分離 canonical 記述を **`cleanup-spec.md` に 1 箇所のみ** 配置（DRY 違反解消） | Architect |
| 38 | `label-spec.md` の `transition()` 擬似コードフェンスも Tests チェックリストで残存確認するよう追加 | Architect |
| 39 | `error_kind = "lock"` を `failed_streak` 非カウント（silent skip）として明記。別プロセス処理中の誤 brake 発動防止 | Performance |
| 40 | Corrupt retry state JSON の扱いを明確化: `.corrupt.{ts}` 隔離リネーム + 2 回連続 parse 失敗で fail-closed | Performance |
| 41 | Unsupported FS (NFS/CIFS/tmpfs/WSL DrvFs) 検出時を warn → **fail-closed (polling abort)** に格上げ。silent data corruption を構造的排除 | Performance |
| 42 | `rollback_gh_fetch_cap` (default 10) を `config-defaults.md` に新規追加。`rollback_orphans` step ③④ の per-tick API 呼び出し上限 | Performance |
| 43 | `polling-adapter.md` の見出しレベル規約 (H2 主要節、H3 Interface メソッド) を Step 1 に明示。Tests Item 1 の grep パターンを整合 | Pragmatist |
| 44 | Step 3 (cleanup-spec.md) / Step 5 (config-defaults.md) に「現状確認してから削除」の条件分岐を明文化 | Pragmatist |
| 45 | `run_id` フィールドを UUID v4 形式に固定、read 時に正規表現検証 (`^[0-9a-f-]{36}$`)、不一致は warn + 無視 | Security (INFO) |
| 46 | `rollback_orphans` 5 段階を内部プライベートサブメソッド (`_check_*`) に分解する設計方針を Step 1 に追記。各段の単体テスト可能性担保 | Architect (INFO) |
| 47 | `issue_number` の整数事前検証 + 非整数時 `fail_closed` を `polling-adapter.md §claim` に追記 | Security (INFO) |
| 48 | Tests を 12 → 18 項目に拡張 (Round 4 追加分: lock silent skip / 7 日 hard cap / URL char set / `.clone_url` 排他作成 / unsupported FS fail-closed / corrupt retry 隔離 / `rollback_gh_fetch_cap` / サブメソッド分解) | — |

## 🔍 Team Review Results

**Reviewed:** 2026-04-08
**Verdict:** APPROVED WITH CONCERNS
**Reviewers:** 4/4 (Security / Performance / Architect / Pragmatist)
**Discussion rounds:** 1 (early convergence)
**Issues resolved:** 16 WARN / INFO (Round 4 修正 #33〜#48)
**Remaining concerns:** 0 (all WARN/INFO 反映済み)

### 修正事項

- `normalize_git_url` URL 文字集合許可リスト検証（指摘者: Security）
- `.clone_url` TOCTOU 排他作成（指摘者: Security）
- `rollback_orphans` 7 日 hard cap + created_at 基準（指摘者: Security）
- Label Mapping SSOT を polling-adapter.md に一本化（指摘者: Architect）
- `sanitize_*` 責務分離 DRY 化（指摘者: Architect）
- `transition()` 擬似コードフェンス残存チェック追加（指摘者: Architect）
- `lock` エラー `failed_streak` 非カウント（指摘者: Performance）
- Corrupt retry JSON 隔離リネーム（指摘者: Performance）
- Unsupported FS fail-closed 格上げ（指摘者: Performance）
- `rollback_gh_fetch_cap` 新規追加（指摘者: Performance）
- 見出しレベル規約 H2/H3 明示（指摘者: Pragmatist）
- cleanup-spec.md / config-defaults.md 現状確認条件分岐（指摘者: Pragmatist）
- `run_id` UUID v4 検証（指摘者: Security INFO）
- `rollback_orphans` サブメソッド分解（指摘者: Architect INFO）
- `issue_number` 整数検証（指摘者: Security INFO）
- Tests 12 → 18 項目に拡張

### 残存リスク

- なし。全 WARN/INFO が計画に反映済み。BLOCK 指摘は Round 1〜3 で既に解消。

### 議論ハイライト

- Round 4 は BLOCK ゼロで早期収束（全論点 WARN 以下）。Round 1〜3 の精緻化が効いている
- SSOT 設計が特に議論に値する論点で、plan archive 後の長期保守性を考慮し polling-adapter.md への一本化を採用
- `rollback_orphans` updated_at ベースの DoS ベクタ（外部コメントによる孤児 pinning）は見落とされがちな攻撃経路で、Security が的確に指摘
- `lock` エラーの failed_streak 非カウントは共通契約 §6 への GitHub adapter 固有の例外規約として明記

## 📊 Progress

| Step | Status |
|------|--------|
| Step 1: polling-adapter.md [NEW] | 🟢 |
| Step 2: label-spec.md refactor | 🟢 |
| Step 3: cleanup-spec.md sanitize責務分離 | 🟢 |
| Step 4: codex-review-loop.md normalize_github_error | 🟢 |
| Step 5: config-defaults.md §10 dedupe + rollback_gh_fetch_cap | 🟢 |
| Step 6: SKILL.md adapter orchestrator化 | 🟢 |
| Step 7: github-issue-polling.md full rewrite | 🟢 |
| Step 8: CLAUDE.md update | 🟢 |
| Step 9: plugin.json 1.13.0 → 1.14.0 | 🟢 |
| Step 10: Tests verification (17/18 grep) | 🟢 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

## 📝 Implementation Summary

- **実装ステップ**: 10/10
- **変更ファイル数**: 8 (modified) + 1 (new) = 9
- **新規ファイル**: `skills/github-issue/references/polling-adapter.md` (約 460 行)
- **Tests 18 項目検証**: 17/18 (grep で機械的に verify)、残り 1 項目 (リンク整合性) は目視 + glob 存在確認で代替
- **Key invariants 確認**:
  - label-spec.md の transition table 本文 / `transition()` 擬似コードフェンス削除 ✅
  - Label Mapping SSOT は polling-adapter.md に一本化 ✅
  - sanitize_slug vs sanitize_repo_slug canonical は cleanup-spec.md 1 箇所のみ ✅
  - `error_kind = "lock"` failed_streak 非カウント明記 ✅
  - `rollback_orphans` 7 日 hard cap + created_at 基準 ✅
  - `.clone_url` O_CREAT|O_EXCL 排他作成 ✅
  - `normalize_git_url` URL 文字集合検証 + `..` 拒否 ✅
  - unsupported FS fail-closed (polling abort) ✅
  - corrupt retry JSON `.corrupt.{ts}` 隔離 + 2 回連続 fail-closed ✅
  - `run_id` UUID v4 正規表現検証 ✅
  - `issue_number` 整数事前検証 ✅
  - `rollback_orphans` 5 段階 private subroutine 分解 ✅
  - `rollback_gh_fetch_cap` (default 10) config 追加 ✅
  - `polling-adapter.md` H2/H3 見出しレベル規約 ✅

---

**Next:** `/claude-skills:plan-review` で再レビュー（refine loop 次イテレーション）、または `/claude-skills:cycle` / `/claude-skills:team-cycle` で実装へ 🚀
