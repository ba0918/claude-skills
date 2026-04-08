# Polling Pattern — Shared Contract

> **⚠️ Warning:** 本契約の変更は、これを参照する全 state adapter 実装（`skills/issue/`、将来の `skills/github-issue/` 等）に影響する。状態・遷移・interface・純関数シグネチャを変更する場合は、全 adapter の references と SKILL.md を同期更新すること。
>
> **Drift Prevention Rule:** 各 adapter の `SKILL.md` と `references/polling-*.md` は、本契約の章見出しに**直リンク**し、固有部分（FS 構造、Label 名、rollback 手順等）のみを local references で記述する。共通仕様を local references に複製してはならない。

---

## 1. Overview

本契約は「単一プロセスが kill されるまで ready キューを延々消化し続ける」ラルフループ型 polling の共通仕様を定義する。責務境界は以下:

| Layer | 責務 | 純関数? |
|---|---|---|
| Pure Functions | 状態遷移・分類・判定 | ✅ |
| State Adapter | I/O を伴う永続化（FS / Label / DB）| ❌ |
| Tick Orchestrator | adapter と純関数を合成して 1 tick を実行 | ❌ |
| Loop Controller | `--loop` 時の繰り返し・safety brake 監視 | ❌ |
| Command | フラグ解析 + orchestrator 起動 | ❌ |

**tick は純関数ではない**。真の純関数は §4 の 4 つのみ。

---

## 2. Lifecycle State Machine

### States

| State | 意味 |
|---|---|
| `ready` | claim 可能 |
| `running` | claim 済み、cycle 実行中 |
| `done` | cycle 成功、archive 待機 |
| `failed/transient` | 一時エラー（retry 可能） |
| `failed/permanent` | 恒久エラー（人間判断待ち） |
| `archives` | 月次アーカイブ済み |

### Transition Table

| Current \ Event | `claim` | `cycle_success` | `cycle_fail_transient` | `cycle_fail_permanent` | `sigint` | `retry_under_limit` | `retry_over_limit` | `month_boundary` |
|---|---|---|---|---|---|---|---|---|
| `ready` | `running` | — | — | — | — | — | — | — |
| `running` | ❌ | `done` | `failed/transient` | `failed/permanent` | `ready` (rollback) | — | — | — |
| `done` | — | — | — | — | — | — | — | `archives` |
| `failed/transient` | — | — | — | — | — | `ready` | `failed/permanent` | — |
| `failed/permanent` | — | — | — | — | — | — | — | — |
| `archives` | — | — | — | — | — | — | — | — |

**未定義のセルは `InvalidTransition` エラーを返す**。`—` は「到達しえない」遷移、`❌` は「契約違反」。

---

## 3. Interface Table (State Adapter 契約)

全 state adapter は以下のメソッドを実装しなければならない。戻り値型は宣言レベル。

| Method | Signature | 備考 |
|---|---|---|
| `list_ready(limit)` | `(int) -> list[Slug]` | **early termination 必須**。全件スキャン禁止、`limit` 件見つかり次第返す |
| `claim(slug)` | `(Slug) -> ClaimResult` | atomic。失敗は `ClaimFailed{reason}` |
| `release(slug)` | `(Slug) -> None` | running → ready rollback |
| `mark_done(slug)` | `(Slug) -> None` | running → done |
| `mark_failed(slug, kind)` | `(Slug, FailureKind) -> None` | kind ∈ {transient, permanent} |
| `retry_count(slug)` | `(Slug) -> int` | transient retry カウンタ取得 |
| `increment_retry(slug)` | `(Slug) -> int` | 新しいカウント値を返す |
| `kill_file_path()` | `() -> (AbsPath, AbsPath)` | `(.STOP, .STOP.hard)` の絶対パス |
| `archive_month_boundary()` | `() -> ArchivedCount` | キャッシュ経由で O(1) チェック、境界跨ぎのみ移動実行 |
| `rollback_orphans(now)` | `(Timestamp) -> list[Slug]` | `running/{slug}/.claim` の pid 死活確認 → ready 戻し |
| `sanitize_slug(raw)` | `(str) -> Slug` | §5 の純関数（adapter が純関数を呼ぶだけ） |

---

## 4. Pure Function Signatures

本契約で「真に純粋」な関数は以下 4 つのみ。全て副作用なし、time / random / I/O 不使用（`now` は引数注入）。

| Function | Signature |
|---|---|
| `transition(state, event) -> NextState \| InvalidTransition` | §2 の Transition Table に基づく match |
| `classify_failure(error_kind) -> Transient \| Permanent` | network/timeout/lock/rate_limit → Transient、test/compile/abort → Permanent |
| `should_promote_to_permanent(retry_count, limit) -> bool` | `retry_count >= limit` |
| `month_boundary_crossed(now, last_check) -> bool` | 年月比較のみ |

**補助純関数（adapter 間で共有）:**

| Function | Signature | 備考 |
|---|---|---|
| `sanitize_slug(raw) -> Slug` | `(str) -> str` | ホワイトリスト `[a-zA-Z0-9._-]` 以外は `_`、`..` は `__`、空文字拒否、シンボリックリンク示唆文字列拒否 |

---

## 5. Tick Orchestration Pseudocode (型宣言レベル)

```
tick(adapter: StateAdapter, config: Config, now: Timestamp) -> TickResult:
    # 1. Safety brakes (kill file 最優先)
    (stop, stop_hard) = adapter.kill_file_path()
    if exists(stop_hard): return TickResult(halt_reason="stop.hard")
    if exists(stop):      return TickResult(halt_reason="stop.graceful")

    # 2. Orphan recovery (クラッシュ復旧)
    adapter.rollback_orphans(now)

    # 3. Archive (month boundary キャッシュ経由 O(1))
    adapter.archive_month_boundary()

    # 4. List ready (limit = max_parallel, early termination)
    ready_slugs = adapter.list_ready(config.max_parallel)
    if empty(ready_slugs): return TickResult()

    # 5. Atomic claim (失敗分はスキップ)
    claimed = [s for s in ready_slugs if adapter.claim(s).ok]

    # 6. Dry run: cycle を呼ばず claim だけ返す
    if config.dry_run:
        for s in claimed: adapter.release(s)
        return TickResult(claimed=len(claimed), halt_reason="dry_run")

    # 7. Delegate to parallel-cycle (worktree 並行)
    results = parallel_cycle_delegate(claimed)

    # 8. Classify & persist
    counter = {done:0, failed_transient:0, failed_permanent:0}
    for (slug, outcome) in results:
        kind = classify_failure(outcome.error_kind) if outcome.failed else None
        if outcome.success:
            adapter.mark_done(slug); counter.done += 1
        elif kind == Transient:
            n = adapter.increment_retry(slug)
            if should_promote_to_permanent(n, config.transient_retry_limit):
                adapter.mark_failed(slug, Permanent); counter.failed_permanent += 1
            else:
                adapter.mark_failed(slug, Transient); counter.failed_transient += 1
        else:
            adapter.mark_failed(slug, Permanent); counter.failed_permanent += 1

    return TickResult(claimed=len(claimed), **counter)
```

**`tick` は I/O を行うため純関数ではない**。`transition` / `classify_failure` / `should_promote_to_permanent` / `month_boundary_crossed` のみが純関数。

---

## 6. Safety Brakes

### 6.1 Kill File (2 ファイル方式)

| File | 挙動 | 用途 |
|---|---|---|
| `<state_root>/.STOP` | graceful: 新規 claim のみ停止、実行中 cycle は完走 | 通常の停止要求 |
| `<state_root>/.STOP.hard` | hard: 実行中 cycle にも SIGTERM を送り、claim を rollback | 緊急停止 |

- パスは **`<state_root>` 絶対パス解決必須**（cwd 依存禁止）
- tick の最初に `.STOP.hard` → `.STOP` の順でチェック

### 6.2 Bounded Execution (3 重ガード)

| Config | Default | 意味 |
|---|---|---|
| `max_iter` | 10 | `--loop` 時の tick 回数上限 |
| `max_wallclock` | 1h | loop 全体の経過時間上限 |
| `failed_streak` | 3 | 連続失敗の上限。超えたら halt |

### 6.3 SIGINT / SIGTERM Trap

- Loop controller が trap を設定し、現在の claim を adapter.release で rollback してから exit
- Trap 不発時（SIGKILL / crash）は次回 tick 冒頭の `rollback_orphans(now)` で回収

### 6.4 Orphan Recovery

- adapter は `running/{slug}/.claim`（FS）または claim metadata（Label 等）に **pid + started_at** を記録
- `rollback_orphans(now)` は死亡 pid を検出し該当 slug を ready に戻す

---

## 7. Tick Result Schema

**構造化カウンタのみ**。自由文・ログ・詳細メッセージは禁止（context 膨張防止）。

```
TickResult {
  claimed:            int   # 今 tick で claim 成功した数
  done:               int   # 成功した数
  failed_transient:   int   # transient に分類された数
  failed_permanent:   int   # permanent に分類された数
  halt_reason?:       "stop.graceful" | "stop.hard" | "max_iter" | "max_wallclock" | "failed_streak" | "dry_run"
}
```

Loop controller はこのカウンタのみを集計し、人間向けサマリは最終出力時に組み立てる。

---

## 8. Retry Policy

| Failure Kind | Policy |
|---|---|
| `transient` (general) | **固定 30s** 後に次 tick で ready 再投入 |
| `transient` (rate_limit) | **Exponential backoff** (30s → 60s → 120s → cap 10 min) |
| `permanent` | Retry しない。人間判断待ち |

`retry_count >= transient_retry_limit` で `failed/permanent` に昇格（§4 `should_promote_to_permanent`）。

---

## 9. Cleanup / Archive

- `done/{slug}` は月末跨ぎで `archives/YYYY-MM/{slug}` に移動
- 月跨ぎ判定は `month_boundary_crossed(now, last_check)` 純関数
- adapter は `<state_root>/.last_archive_month` (または同等) に `YYYY-MM` をキャッシュし、同月内の tick では **O(1)** で早期 return
- 境界跨ぎ時のみ `done/` をスキャンして移動

---

## 10. Default Config (保守的初期値)

```yaml
max_parallel: 4
max_iter: 10
max_wallclock: 1h
failed_streak_limit: 3
transient_retry_limit: 3
tick_interval_loop_mode: 30s
rate_limit_backoff: exponential  # 30s, 60s, 120s, cap=10m
dry_run: false                    # 初回起動時は強制 true
```

**初回起動ポリシー**: `<state_root>/.polling-initialized` が存在しない場合、`--dry-run` を強制する（ユーザーが 1 度 polling パターンを理解してから実運用に入るため）。

---

## 11. Drift Prevention Rules

1. 各 adapter の SKILL.md は本ファイル § 番号を**直リンク参照**する（本文複製禁止）
2. Transition Table / Interface Table / 純関数シグネチャを local references で**再定義してはならない**
3. 固有部分のみ local references に記述:
   - FS: ディレクトリレイアウト、atomic rename 手順、sanitize の実装詳細
   - Label: ラベル名、GraphQL クエリ、3 段防御
4. 本契約を変更する PR は、全 adapter references の同期更新を同一 PR に含めること
