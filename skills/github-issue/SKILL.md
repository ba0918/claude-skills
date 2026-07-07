---
name: github-issue
description: GitHub issue を起点に Claude が自走し、polling → 並列 cycle → draft PR → Codex レビュー → 修正ループ → auto merge + close まで完全自動化する。`create` / `list` / `polling` / `cycle` の 4 ワークフローを提供する。「github issue」「gh issue」「issue polling」「auto merge」「自走」で起動。
---

# github-issue Skill

GitHub issue を信頼境界とした自走型ワークフロー。ラベルベース状態機械で並行安全に実行制御し、`/loop` 連携で headless に動作する。

> **Scope:** このスキルは GitHub 上の issue/PR を扱う。ローカル `docs/issues/` を扱う `issue` スキルとは独立。

## Workflow Selection

引数の最初のキーワードでワークフローを分岐する。

| Keyword | Workflow | 用途 |
|---------|----------|------|
| `create` | Create Workflow | 新規 issue 作成（対話） |
| `list` | List Workflow | `claude-auto` 付き open issue 一覧 |
| `polling` | Polling Workflow | `/loop` から呼ばれる headless tick |
| `cycle` | Cycle Workflow | 単一 issue を draft PR → Codex レビュー → auto merge まで実行 |

> **Note:** `plan` / `close` は cycle 内部のサブステップとして実装する（外向きコマンドからは廃止）。

## Common Pre-checks

すべてのワークフロー冒頭で実行する。

1. **gh CLI 確認**: `gh --version` が成功すること。失敗時は「gh CLI が必要です。https://cli.github.com/ からインストールしてください」で終了。
2. **gh 認証確認**: `gh auth status` が成功すること。失敗時は「gh CLI 未認証です。`gh auth login` を実行してください」で終了。
3. **リポジトリ確認**: `gh repo view --json nameWithOwner` でカレントディレクトリが GitHub リポジトリ配下か確認。失敗時は `fetch_git_remote_url()`（[`references/polling-adapter.md §state_root Resolution`](references/polling-adapter.md#state_root-resolution)）と同順 — `git remote get-url origin` を primary、`gh repo view` を fallback — で取得してよい。両者を同順に揃えることで、リポジトリ確認と state_root 解決の間の取得経路が食い違わないことを保証する。
4. **設定値**: `references/config-defaults.md` のデフォルト値を読み込む。引数で上書きされた値があれば優先する。

> **Polling との関係（fail-closed）**: 上記 pre-check の失敗は fail-closed であり、polling tick を起動しない（`fail_closed` と同経路、`error_kind` は [`tool_missing`](references/polling-adapter.md#error_kind-enum) 相当として扱う）。ただし GitHub アクセスを要しない確認（kill file 停止確認等）をユーザーが明示的に指示した場合に限り、pre-check 失敗を記録した上で該当確認のみ継続してよい。

## References

各ワークフローの詳細は以下の references を参照すること。Polling の共通契約は [`../shared/references/polling-pattern.md`](../shared/references/polling-pattern.md) を直リンクで参照する（drift 防止 §11 遵守）。

- [`references/polling-adapter.md`](references/polling-adapter.md) — Label state adapter 実装仕様（Interface Table / state_root / error_kind / claim 3 段防御 / rollback sub-steps）
- [`references/label-spec.md`](references/label-spec.md) — ラベル定義 + Backward Compatibility + Migration Exit Strategy
- [`references/codex-review-loop.md`](references/codex-review-loop.md) — Codex PR レビュー委譲プロンプト + normalize_github_error + fail-closed オーバーライド
- [`references/config-defaults.md`](references/config-defaults.md) — GitHub 固有設定値表（共通契約 §10 重複は SSOT 直リンク）
- [`references/secret-scanner.md`](references/secret-scanner.md) — 秘密情報検出正規表現セット
- [`references/gh-commands.md`](references/gh-commands.md) — gh CLI 意味論的ラッパー一覧
- [`references/cleanup-spec.md`](references/cleanup-spec.md) — worktree / ブランチ孤児クリーンアップ規則 + sanitize 責務分離

---

## Create Workflow

ユーザーから自然言語で issue 内容を受け取り、適切なラベルを推論して `gh issue create` を実行する。

### Steps

1. Common Pre-checks を実行
2. ユーザー引数（タイトル + 本文 + 任意のヒント）を解析
3. `gh label list --json name,description,color` でリポジトリの既存ラベル一覧を取得
4. LLM が issue 内容と既存ラベルから以下を推論する:
   - 適用すべきラベル（`bug` / `feature` / `docs` / `enhancement` 等）
   - `claude-auto` 付与の可否（自走可能な明確な acceptance criteria を持つか）
   - タイトル候補（不足している場合）
5. **AskUserQuestion でユーザー確認**:
   - 表示: タイトル / 本文 / 推論ラベル / `claude-auto` 付与の可否 / 理由
   - オプション: 「作成」「修正」「キャンセル」
6. 承認されたら `gh issue create --title ... --body ... --label ...` で作成
7. 結果（issue URL）を表示

> **非対話経路では Create を呼ばない**: polling 等の headless 経路から本ワークフローを呼び出すことは禁止。

---

## List Workflow

`claude-auto` ラベルが付いた open issue を一覧表示する。

### Steps

1. Common Pre-checks を実行
2. `gh issue list --label claude-auto --state open --json number,title,labels,assignees,author,authorAssociation --limit 100` を実行
3. client-side で以下を分類して表示（precedence rule は [`references/polling-adapter.md §state_of_failure Precedence Rule`](references/polling-adapter.md#state_of_failure-precedence-rule) 参照）:
   - **Ready**: `claude-running` も `claude-review` も failed 系ラベルも付いていない
   - **Running**: `claude-running` 付き
   - **In Review**: `claude-review` 付き
   - **Failed (Transient)**: `state_of_failure(labels) == TRANSIENT`
   - **Failed (Permanent)**: `state_of_failure(labels) == PERMANENT`（legacy `claude-failed` 単独も含む）
4. 0 件なら `No claude-auto issues found.` を出力して終了

---

## Polling Workflow

`/loop github-issue-polling` から定期的に呼ばれる headless tick。複数 issue 検出時は parallel-cycle に委譲する。

> **単一ホスト前提**: 本 workflow は単一ホスト・単一プロセスのラルフループ前提で設計されている。複数ホストからの分散 polling は非対応（理由は [`references/polling-adapter.md §Assumptions`](references/polling-adapter.md#assumptions) 参照）。

> **Safety brake の永続化（`--stateless`）**: `/loop` や cron からの呼び出しは 1 invocation = 1 tick でプロセスが毎回死ぬため、
> `max_iter` / `max_wallclock` / `failed_streak` のカウンタはプロセスメモリでは維持できない。定期起動で運用する場合は
> `--stateless` を付け、共通契約 [`§6.5 Tick Session`](../shared/references/polling-pattern.md#65-tick-session-ステートレス実行の-safety-brake-永続化) に従って
> `<state_root>/session.json` にカウンタを永続化すること（`failed_streak` halt は sticky — `session.json` を削除するまで再開しない）。

### Workflow 構造

本 workflow は **共通契約 [`../shared/references/polling-pattern.md §5 Tick Orchestration`](../shared/references/polling-pattern.md#5-tick-orchestration-pseudocode-型宣言レベル) の tick() 擬似コードに準拠した薄い orchestrator**。状態機械（§2）・純関数（§4）・Safety brake（§6）・Tick Schema（§7）の詳細は共通契約を参照し、本ファイルでは adapter method の呼び出し順のみ記述する。

claim 3 段防御 / state_root 解決 / error_kind 分類 / rollback 5 段階などの Label adapter 実装詳細は [`references/polling-adapter.md`](references/polling-adapter.md) に隠蔽されている（SKILL.md は `claim(slug)` を呼ぶだけ）。

### Steps

1. **Common Pre-checks** を実行
2. **Adapter 初期化**: Label adapter インスタンスを取得。`state_root` 解決時に XDG fallback + `.clone_url` 排他作成 + `unsupported FS fail-closed` が走る（詳細は [`references/polling-adapter.md §state_root Resolution`](references/polling-adapter.md#state_root-resolution)）
3. **Kill file check**: `adapter.kill_file_path()` で `.STOP.hard` → `.STOP` の順に確認。存在すれば即 halt（共通契約 §6.1 参照）
   - `--stateless` の場合はこの直後に `adapter.load_session()` → `session_resume_action(prev, now, config)` を評価し、`Halt{reason}` なら claim せず即 `TickResult(halt_reason=reason)` で終了（共通契約 §6.5）
4. **Orphan recovery**: `adapter.rollback_orphans(now)` で 5 段階の回収を実行（共通契約 §6.4 + [`references/polling-adapter.md §rollback_orphans Sub-Steps`](references/polling-adapter.md#rollback_orphans-sub-steps)）
5. **Archive**: `adapter.archive_month_boundary()`（GitHub では no-op、キャッシュ更新のみ）
6. **Rate limit pre-check**: `gh api rate_limit --jq '.rate.remaining'` ≥ `min_rate_limit_remaining`。未満なら quiet skip
7. **List ready**: `effective_parallel = min(max_parallel, parallel_worktree_limit)` で `adapter.list_ready(effective_parallel)` を呼び出し（precedence rule は [`references/config-defaults.md`](references/config-defaults.md) 参照）。単一 API 呼び出し、client-side filter 後 limit 未満でも再 fetch しない
8. **Atomic claim**: 各 slug について `adapter.claim(slug)` を呼ぶ。失敗は quiet skip（claim 3 段防御の詳細は adapter 内部）。`authorAssociation` フィルタは `adapter.list_ready()` 側で既に適用済み（[`references/polling-adapter.md §list_ready(limit)`](references/polling-adapter.md#list_readylimit) 参照）、orchestrator 側では再実行しない
9. **Dry run 判定**: `config.dry_run` または `<state_root>/.polling-initialized` が存在しない場合は claim 済みを `release()` して `halt_reason="dry_run"` を返す
10. **Parallel-cycle 委譲**: claim 済み issue から plan を作成して `claude-skills:parallel-cycle` に委譲。**parallel-cycle 内では再 claim を行わない**（claim 責任は Polling 側に一元化）
11. **Classify & persist**: 各 outcome について `classify_failure(normalize_github_error(exc))` を呼ぶ。
    - **Success**: `adapter.mark_done(slug)`
    - **Transient failure**: `n = adapter.increment_retry(slug)` → `kind = should_promote_to_permanent(n, config.transient_retry_limit) ? Permanent : Transient` → `adapter.mark_failed(slug, kind)` （共通契約 §5 Classify & persist ブロック準拠）
    - **Permanent failure**: `adapter.mark_failed(slug, Permanent)` （`increment_retry` はスキップ、共通契約 §4 `classify_failure` 純関数を直接適用）
    - `mark_failed` は単一 `gh issue edit` の atomic dual-write + verification（詳細は [`references/polling-adapter.md §mark_failed(slug, kind)`](references/polling-adapter.md#mark_failedslug-kind)）
    - `error_kind = "lock"` は `failed_streak` にカウントしない（silent skip、[`references/polling-adapter.md §error_kind Handling Rules`](references/polling-adapter.md#error_kind-handling-rules) 参照）
12. **TickResult emit**: 共通契約 §7 Tick Schema に準拠した構造化カウンタ `{run_id, tick_started_at, claimed, done, failed_transient, failed_permanent, halt_reason?}` を返す。`run_id` / `tick_started_at` を含む全 7 フィールドは不変（共通契約 §7 参照）
13. **初回 tick 成功時**: `<state_root>/.polling-initialized` を `write_atomic` で作成（次 tick から dry-run 強制解除）
14. **Session persist（`--stateless` のみ）**: `next_session_state(session, tick_result)` でカウンタ更新 + halt 判定を計算し、`adapter.save_session()` で永続化（共通契約 §6.5）
15. **Measurement event append**: TickResult のカウンタを計測イベントとして追記する（[measurement-identity.md §4](../shared/references/measurement-identity.md#4-既存系の写像表)）: `python3 skills/shared/scripts/measurement_identity.py emit --system polling-label --event tick --skill github-issue --repo-root {repo_root} --run-id {run_id} --outcome '{TickResult カウンタ JSON}'`。失敗しても warn のみで tick をブロックしない

### スナップショット境界

本 tick のスナップショット以外を扱わない。途中追加された issue は次 tick で拾う。

---

## Cycle Workflow

単一 issue を最後まで自走させる中核ワークフロー。

### Pre-condition

- `claude-skills:cycle` はカレントブランチで commit のみ行う前提。**branch 操作 / push / PR 作成は本ワークフロー側の責務**。

### Steps

#### 1. Pre-check

1. Common Pre-checks
2. `gh api rate_limit --jq '.rate.remaining'` ≥ `min_rate_limit_remaining`
3. 引数で issue 番号 N が指定されているか確認。**N は `^[1-9][0-9]*$` にマッチすること**（`0` および zero-padded を拒否）。マッチしない場合は即 fail with `"invalid issue number"`（コマンドインジェクション/誤呼び出し防止）
4. **`codex_required_for_merge` は強制 `true`**: ユーザーによる `--config` 上書きを無視し、`references/codex-review-loop.md` の pre-flight check で警告ログ後に `true` にリセットする

#### 2. Atomic Claim

adapter への委譲: `adapter.claim(slug)` を呼ぶだけ。失敗時は `ClaimFailed{reason}` で quiet abort（リトライしない）。

3 段防御（lockfile + gh edit + re-verify）の詳細は [`references/polling-adapter.md §claim() 3 段防御`](references/polling-adapter.md#claim-3-段防御) に隠蔽されている。SKILL.md は interface のみを知り、内部実装には依存しない（共通契約 §3 + Layer Separation 遵守）。

- lockfile path: `<state_root>/claim/{N}.lock`（`flock(2)` 非ブロッキング）
- 失敗理由: `LockBusy` / `gh edit failed` / `post-claim verify failed` のいずれか
- `issue_number` は整数事前検証（adapter が `^[1-9][0-9]*$` にマッチすることを verify）

#### 3. Plan 作成（内部サブステップ）

1. `gh issue view ${N} --json number,title,body,labels` で issue 内容を取得
2. issue 本文と acceptance criteria から `claude-skills:plan` を Skill ツール経由で呼び出して plan を作成
3. plan 先頭に `**GitHubIssue:** #${N}` を追記

#### 4. Cycle 実行

1. 新規ブランチを作成: `git switch -c gh-issue-${N}-$(date +%Y%m%d%H%M%S)`
2. `claude-skills:cycle` を Skill ツール経由で実行（plan ファイルを引数に渡す）。cycle はこのブランチ上で commit を積む。

#### 5. Draft PR 作成

```bash
git push -u origin <branch>
gh pr create --draft --title "<plan title>" --body "Closes #${N}\n\n<plan summary>"
```

**必ず `--draft` を付ける**（auto merge ゲートを通過するまで draft 解除しない）。

#### 6. ラベル遷移

`claude-running` を削除し `claude-review` を付与:

```bash
gh issue edit ${N} --remove-label claude-running --add-label claude-review
```

#### 7. Codex レビューループ

詳細は [`references/codex-review-loop.md`](references/codex-review-loop.md) を参照。

概要:

1. **事前フィルタ**:
   - `gh pr diff <PR>` の行数が `max_diff_lines` 超過 → Codex に渡さず即 Step 9 へ（claude-failed）
   - `references/secret-scanner.md` の正規表現で diff をスキャン。検出時は同様に claude-failed
2. **プロンプトインジェクション対策**: issue 本文を `<untrusted_user_content>...</untrusted_user_content>` で囲む
3. **差分レビュー**: 2 回目以降は前回指摘 → 対応状況を Codex に明示し、LGTM 済みファイルの再レビューをスキップ
4. **Codex 呼び出し**: [`shared/references/codex-integration.md`](../shared/references/codex-integration.md) で定義された subagent パターンに従う（具体的な subagent 名は `references/codex-review-loop.md` に集約）。diff + plan + acceptance criteria を渡し、`{"verdict": "LGTM"|"NEEDS_CHANGES", "findings": [...]}` を強制
5. **判定**:
   - `LGTM` → ループ脱出して Step 8 へ
   - `NEEDS_CHANGES` → `findings` を `claude-skills:iterate` に渡して修正 → `git push` → 次イテレーション
6. **回数制限**: `max_review_iterations`（デフォルト 3）到達で claude-failed
7. **Codex 一時/恒久区別**: network/rate limit 等の一時障害は次 tick で再試行扱い、`codex_consecutive_failure_threshold`（デフォルト 3）回連続失敗で恒久 failed

#### 8. Auto Merge ゲート（AND 条件 4 項目）

以下を**すべて**満たした場合にのみマージする。

1. Codex `LGTM`
2. `gh pr checks <PR>` がすべて pass
3. secret-scanner 検出ゼロ
4. 変更ファイルに `.env` / `*.key` / `*.pem` / `credentials.*` を含まない

通過時:

```bash
gh pr ready <PR>                       # draft 解除
gh pr merge <PR> --squash --delete-branch
gh issue close ${N}
gh issue edit ${N} --remove-label claude-auto --remove-label claude-review
```

> `--auto` フラグは使わない。明示的に ready → merge の順で実行して順序を保証する。

#### 9. 失敗時処理

- PR は draft のまま保持
- エラー詳細は **FS retry state** (`<state_root>/retry/{N}.json`) に構造化保存（retry_count / last_failed_at / run_id のみ、自由文エラーは保存禁止 — 共通契約 §3 遵守）
- `claude-running` / `claude-review` を削除し、`mark_failed(slug, kind)` で **atomic dual-write** を実行:
  - `classify_failure(normalize_github_error(exc))` で kind (TRANSIENT / PERMANENT) を決定
  - 単一 `gh issue edit --add-label claude-failed-{transient,permanent} --add-label claude-failed` で新旧ラベル同時付与
  - 付与後 `gh issue view` で verification、不一致は 3 回 backoff (0s/1s/2s) で再試行
  - 最終失敗時は `<state_root>/recovery/{N}` マーカー（crash-safe ordering: marker write → release の順）+ `release(slug)` で次 tick 再評価へ
  - 詳細は [`references/polling-adapter.md §mark_failed(slug, kind)`](references/polling-adapter.md#mark_failedslug-kind) + [`references/label-spec.md §Backward Compatibility`](references/label-spec.md#backward-compatibility)
- lockfile 解放（プロセス終了で自動、`flock(2)` が kernel レベルで解放）

#### 10. べき等性

- すべてのワークフローはラベル状態を見て再実行安全
- worktree が残っていれば `git worktree list` で検出して再利用 or `references/cleanup-spec.md` に従いクリーンアップ

---

## Configuration Override

設定値は引数 `--config key=value` で上書き可能。すべての設定値は [`references/config-defaults.md`](references/config-defaults.md) に表で定義されている。

例:
```
github-issue cycle 42 --config max_review_iterations=5 --config parallel_worktree_limit=2
```

---

## Codex Review

Cycle Workflow Step 7（Codex レビューループ）における Codex 呼び出しの集約ポイント。具体的な subagent 名・プロンプト・JSON 契約・反復ロジックは [`references/codex-review-loop.md`](references/codex-review-loop.md) に集約されている。本スキル内で Codex に関するエントリポイントは Step 7 と本セクションのみであり、他の references からはこのセクションへリンクすること。
