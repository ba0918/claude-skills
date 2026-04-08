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
3. **リポジトリ確認**: `gh repo view --json nameWithOwner` でカレントディレクトリが GitHub リポジトリ配下か確認。
4. **設定値**: `references/config-defaults.md` のデフォルト値を読み込む。引数で上書きされた値があれば優先する。

## References

各ワークフローの詳細は以下の references を参照すること。

- [`references/label-spec.md`](references/label-spec.md) — ラベル定義 + 状態×イベント遷移表
- [`references/codex-review-loop.md`](references/codex-review-loop.md) — Codex PR レビュー委譲プロンプト + 修正ループ + fail-closed オーバーライド
- [`references/config-defaults.md`](references/config-defaults.md) — デフォルト設定値表
- [`references/secret-scanner.md`](references/secret-scanner.md) — 秘密情報検出正規表現セット
- [`references/gh-commands.md`](references/gh-commands.md) — gh CLI 意味論的ラッパー一覧
- [`references/cleanup-spec.md`](references/cleanup-spec.md) — worktree / ブランチ孤児クリーンアップ規則

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
3. client-side で以下を分類して表示:
   - **Ready**: `claude-running` も `claude-review` も `claude-failed` も付いていない
   - **Running**: `claude-running` 付き
   - **In Review**: `claude-review` 付き
   - **Failed**: `claude-failed` 付き
4. 0 件なら `No claude-auto issues found.` を出力して終了

---

## Polling Workflow

`/loop github-issue-polling` から定期的に呼ばれる headless tick。複数 issue 検出時は parallel-cycle に委譲する。

### Steps

1. Common Pre-checks を実行
2. **Polling lockfile 取得**:
   ```bash
   # SLUG = sanitize_repo_slug($(gh repo view --json nameWithOwner -q .nameWithOwner))
   # see references/cleanup-spec.md → sanitize_repo_slug() for the whitelist rule
   SLUG=$(gh repo view --json nameWithOwner -q .nameWithOwner \
     | python3 -c "import sys,re; v=re.sub(r'[^a-zA-Z0-9._-]', '_', sys.stdin.read().strip()); print(v.replace('..', '__'))")
   exec 9>/tmp/github-issue-polling-${SLUG}.lock
   flock -n 9 || { echo "Another polling tick in progress, skip."; exit 0; }
   ```
   取得失敗なら quiet skip（同一マシン上の `/loop` 並走防止）。
3. **Rate limit pre-check**: `gh api rate_limit --jq '.rate.remaining'` で残量を取得。`min_rate_limit_remaining` 未満なら quiet skip。
4. **孤児 worktree クリーンアップ**: `references/cleanup-spec.md` に従い、24h 以上経過 & merged ブランチに対応する worktree を削除。
5. **対象 issue snapshot 取得**:
   ```bash
   gh issue list --label claude-auto --state open \
     --json number,title,body,labels,author,authorAssociation \
     --limit 100
   ```
   `--search` は使わない（30 req/min 制限回避）。
6. **client-side フィルタ**:
   - `claude-running` / `claude-review` / `claude-failed` のいずれかを持つ issue を除外
   - `authorAssociation` が `require_author_association` リストに含まれない issue を除外
7. **対象件数で分岐**:
   - **0 件**: quiet exit
   - **1 件**: そのまま `cycle` ワークフロー（同一プロセス内）を呼び出す
   - **複数件**: 委譲前に Polling 側で**順次** Cycle Workflow Step 2（atomic claim 3 段防御）を完了させる。claim に失敗した issue はリストから除外し、claim 済みの issue だけを対象に各 issue から plan を作成（Cycle Workflow Step 3 と同じ手順）し、plan ファイルパスのリストを構築 → `claude-skills:parallel-cycle` に委譲。**parallel-cycle のサブプロセス内では再 claim を行わない**（claim 責任は Polling 側に一元化し、二重 claim による排他誤動作を防ぐ）。`parallel_worktree_limit` のデフォルトは 1 のため、明示的に並列指定がない限り順次実行になる。
8. **このスナップショット以外を扱わない**: 途中追加された issue は次 tick で拾う

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

#### 2. Atomic Claim（多重防御）

以下の 3 段防御を**この順序で**実行する。1 つでも失敗したら quiet abort（リトライしない）。

1. **ローカル lockfile**:
   ```bash
   # SLUG = sanitize_repo_slug($(gh repo view --json nameWithOwner -q .nameWithOwner))
   exec 8>/tmp/github-issue-claim-${SLUG}-${N}.lock
   flock -n 8 || abort "lockfile busy"
   ```
2. **assignee 排他**:
   ```bash
   gh issue edit ${N} --add-assignee @me
   gh issue edit ${N} --add-label claude-running
   ```
3. **post-claim re-verify**:
   ```bash
   gh issue view ${N} --json assignees,labels
   ```
   `assignees` に自分（`@me`）が含まれること、かつ `labels` に `claude-running` が含まれることを確認。否なら abort。

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
- issue にエラー詳細とレビュー履歴を `gh issue comment` で投稿
- `claude-running` / `claude-review` を削除し `claude-failed` を付与
- lockfile 解放（プロセス終了で自動）

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
