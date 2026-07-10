---
name: team-cycle
description: AgenticTeam によるチーム議論型レビュー → 自動実装の全サイクルを実行する。複数の専門レビュワー（Security / Performance / Architect / Pragmatist）がチームとして議論しながら計画をレビューし、合意形成後に自動実装へ進む。「team cycle」「チームサイクル」「チームレビュー付きcycle」で起動。
---

# Team Cycle

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

AgenticTeam を使った複数レビュワーによるチーム議論型レビュー + 自動実装サイクル。

## Flow Overview

```
team-cycle コマンド
  │
  ├─ Phase 0: 準備（計画ファイル特定・検証・環境チェック）
  │
  ├─ Phase 1: チームレビュー（AgenticTeam）
  │    ├─ チーム作成 → メンバー spawn × 4 → 議論 → 合意形成 → 計画修正
  │    └─ チーム解散（必ず実行）
  │
  ├─ Phase 2: 実装（既存の plan-implement を Agent 委譲）
  │
  ├─ Phase 2.5: コードレビュー（Agent spawn × 2: Security + Architect）
  │    ├─ git diff で変更差分を取得
  │    ├─ 並行レビュー → 判定（PASS / PASS WITH NOTES / NEEDS FIX）

  │    └─ NEEDS FIX 時は修正 → 再レビュー（最大1回リトライ）
  │
  └─ Phase 3: 完了処理
       ├─ 結果ファイル生成
       ├─ status.md / session-history.md 更新
       ├─ commit
       └─ issue close（該当時）
```

## パラメータ

- `$ARGUMENTS` の最初の引数: 計画ファイルパス（省略時は `.agents/artifacts/plans/` 内の最新を自動選択）
- `--interactive`: ユーザーコメント受付を有効にする（デフォルト: headless）

## Phase 0: 準備

### Step 0.1: 環境変数チェック

**重要**: Phase 1 のチーム作成を使用するには、実験的機能フラグが必要。

以下のコマンドで環境変数を確認する:

```bash
echo "${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS:-not_set}"
```

未設定（`not_set`）の場合:

```
⛔ TEAM-CYCLE ABORTED: AgenticTeam feature not enabled

Set the environment variable before running:
  export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

Then retry: /claude-skills:team-cycle
```

cycle を中断する。

### Step 0.2: 計画ファイル特定

1. 引数にパスがあればそれを使用
2. なければ: `ls -t .agents/artifacts/plans/*.md 2>/dev/null | head -1`

### Step 0.3: パス検証

計画ファイルのパスが `.agents/artifacts/plans/` 配下であることを確認する。

パスが `.agents/artifacts/plans/*.md` に一致しない場合:

```
⛔ TEAM-CYCLE ABORTED: Plan file is not in .agents/artifacts/plans/
Found: {actual_path}
Expected: .agents/artifacts/plans/*.md

Plan files must be located in .agents/artifacts/plans/.
```

cycle を中断する。

### Step 0.4: 計画読み込み

1. 計画ファイルを読み込み、概要を把握する（Feature名、ステップ数、現在の進捗）
2. サイクル開始を表示:

```
══════════════════════════════════════
TEAM-CYCLE START
Plan: {plan_file_path}
Feature: {feature_name}
Steps: {step_count}
Mode: AgenticTeam Review
══════════════════════════════════════
```

## Phase 1: チームレビュー（AgenticTeam）

**重要**: Phase 1 の全処理は **チーム解散を保証する try-finally パターン** で実装する。チーム作成成功後、以降のどの段階でエラーが発生してもチーム解散を必ず実行する。

### Step 1.1: コンテキスト収集

レビュワーに渡すコンテキストを収集する:

```bash
# CLAUDE.md
cat CLAUDE.md 2>/dev/null || echo ""

# review-rules.md（存在する場合のみ）
cat .claude/review-rules.md 2>/dev/null || echo ""
```

計画ファイルの全文は既に Step 0.4 で読み込み済み。

### Step 1.2: チーム作成

レビューチームを作成する:

- **team_name**: `plan-review-team`

### Step 1.2.5: Optional Specialist Detection

Step 1.2（チーム作成）完了後、Step 1.3（レビュワー spawn）の前に実行する。

計画内容を plan-reviewer Step 2.5 と同じキーワード検出ロジックでスキャンする。

**Strong signals (any one triggers):**
- Keywords: "UI", "UX", "component", "screen", "page", "button", "form", "modal", "frontend", "ユーザー確認", "accessibility", "a11y"
- File extensions in affected files: `.tsx`, `.jsx`, `.vue`, `.svelte`, `.css`, `.scss`, `.html`

**Weak signals (2+ required to trigger):**
- Keywords: "display", "layout", "style", "output", "format", "message", "error message", "progress"

**Override:** If `.claude/review-rules.md` contains `ui_ux_review: always`, always include. If `ui_ux_review: never`, always skip. Invalid values fall back to default `auto`.

If UI/UX signals detected:
- Step 1.3 で UX Advisor を5人目として追加 spawn する
- Phase 1 の全議論ラウンドに UX Advisor を含める
- Phase 1 表示を `Reviewers: {active_count}/{total}` に動的化

If not detected:
- 標準4人構成で続行

**spawn 失敗時の扱い:**
- UX Advisor（optional specialist）の spawn 失敗は WARNING のみ。コア4ロール（Security/Performance/Architect/Pragmatist）のうち2名以上成功すれば続行可能。
- Phase 2.5（コードレビュー）には UX Advisor は参加しない。

### Step 1.3: レビュワー spawn（並行）

[skills/shared/references/team-config.md](../shared/references/team-config.md) に定義された4つのロール（+ Step 1.2.5 で検出された場合は UX Advisor）を **並行で** サブエージェントとして起動する。

各メンバーのプロンプトは以下の構成:

1. ロール説明とレビュー指示（team-config.md のロール固有プロンプト）
2. チーム情報（`team_name: plan-review-team`、メッセージで Lead に報告する指示）
3. コンテキスト（計画ファイル全文、CLAUDE.md、review-rules.md）

**並行 spawn の実行:**

4つのサブエージェントを同時に起動する。各メンバーのプロンプト:

```
あなたは {role_name} としてチームレビューに参加しています。
チーム名: plan-review-team

{role_specific_prompt_from_team_config}

## コンテキスト

### 計画ファイル
{plan_content}

### プロジェクトルール (CLAUDE.md)
{claude_md_content}

### レビュールール (.claude/review-rules.md)
{review_rules_content}

レビューが完了したら、以下のようにメッセージで Lead に報告してください:
- team_name: "plan-review-team"
- recipient: "lead"
- メッセージ: レビュー結果の全文
```

**spawn 失敗時の処理:**

- 成功したメンバーが 2 名以上 → 続行
- 成功したメンバーが 1 名以下 → チーム解散して cycle 中断:

```
⛔ TEAM-CYCLE ABORTED: Insufficient reviewers (need >= 2, got {count})
Team disbanded.
```

### Step 1.4: 論点整理（Lead）

[references/review-flow.md](references/review-flow.md) の Step 2 に従い、各レビュワーの報告を整理する。

1. 全レビュワーからのメッセージを受け取る
2. 報告を3カテゴリに分類:
   - **共通問題**: 複数レビュワーが指摘した同一の問題
   - **トレードオフ論点**: レビュワー間で意見が対立する論点
   - **軽微な問題**: 単独の指摘で影響が小さい
3. トレードオフ論点がなければ Step 1.6 にスキップ

### Step 1.5: チーム議論

[references/review-flow.md](references/review-flow.md) の Step 3 に従い、トレードオフ論点について議論する。

1. 全メンバーにメッセージでトレードオフ論点を共有:

```
team_name: "plan-review-team"
recipient: 各メンバー名
```

2. 各メンバーの意見をメッセージで受け取る
3. **各ラウンド終了時にサマリーを出力する**: ユーザーに途中経過を可視化する（フォーマットは review-flow.md 参照）
4. **早期収束チェック**: 全論点が WARN 以下なら残りラウンドをスキップ
5. 最大 3 ラウンドで収束させる
6. 合意に至らない場合は Lead が判断（理由を明記）

### Step 1.6: 合意形成と判定

[references/review-flow.md](references/review-flow.md) の Step 4 に従い、合意を形成する。

**判定ロジック:**

| 判定 | 条件 | 次のアクション |
|------|------|---------------|
| APPROVED | BLOCK 指摘なし。全問題が解消済み | Phase 2 へ |
| APPROVED WITH CONCERNS | BLOCK なし。WARN レベルの残存リスクあり | 残存リスクを記録して Phase 2 へ |
| REJECTED | BLOCK が解消不可。根本的な設計変更が必要 | cycle 中断 |

### Step 1.7: 計画修正

APPROVED / APPROVED WITH CONCERNS の場合:

1. 計画ファイルに `## 🔍 Team Review Results` セクションを追加する
2. 問題のあったステップを修正する
3. 注意事項・エッジケースを追記する

追加セクションのフォーマット:

```markdown
## 🔍 Team Review Results

**Reviewed:** {datetime}
**Verdict:** {APPROVED / APPROVED WITH CONCERNS}

### 修正事項
- {修正内容}（指摘者: {role}）

### 残存リスク
- {リスク}（許容理由: {reason}）

### 議論ハイライト
- {論点}: {合意内容の要約}
```

### Step 1.7.5: ユーザーコメント受付（--interactive 時のみ）

**`--interactive` フラグが指定されている場合のみ実行する。** headless（デフォルト）ではスキップ。

1. レビュー結果をユーザーに表示:

```
══════════════════════════════════════
TEAM REVIEW COMPLETE — Awaiting Your Input
Verdict: {verdict}

議論結果を確認してください。
コメントがあれば入力してください（チームが再議論します）。
問題なければ「続行」と入力してください。
══════════════════════════════════════
```

2. ユーザーの入力を待つ（Claude Code の通常の対話フロー）
3. ユーザー入力の判定:
   - 「続行」「OK」「問題なし」等 → Phase 2 へ進む
   - それ以外のテキスト → コメントとして扱い、チーム再議論へ

#### コメント時の再議論（最大1ラウンド）

Lead がコメント内容に応じて対応を分岐する:

| コメントの性質 | 対応 |
|---------------|------|
| **軽微**（スタイル、命名等） | Lead が単独で計画修正（チーム不要） |
| **専門的**（セキュリティ懸念等） | 該当1名のみに意見を求める（メッセージ送信） |
| **根本的**（設計変更） | フルメンバー再議論（最大1回） |

再議論の手順:
1. ユーザーコメントを対象メンバーにメッセージ送信
2. 各メンバーが意見を Lead に報告
3. Lead が合意を更新
4. 計画ファイルを修正

### Step 1.8: チーム解散

**必ず実行する。** 正常完了・エラー・REJECTED のいずれの場合も。

`--interactive` 時は Step 1.7.5（ユーザーコメント受付後）の完了後に実行する。

チームを解散:

- **team_name**: `plan-review-team`

### Step 1.9: REJECTED 時の処理

REJECTED 判定の場合:

1. 計画ファイルの Status を `🔴 Rejected` に更新
2. REJECTED 理由のサマリーを表示:

```
══════════════════════════════════════
TEAM-CYCLE REJECTED
Feature: {feature_name}
Reason: {rejection_summary}

The plan requires fundamental design changes.
Please revise the plan and retry.
══════════════════════════════════════
```

3. Phase 2 には進まず cycle 中断

### Phase 1 表示

```
── Phase 1: Team Review ── {APPROVED|APPROVED WITH CONCERNS|REJECTED}
Reviewers: {active_count}/{total} (total = 4 or 5 depending on UX Advisor)
Discussion rounds: {round_count}
Issues resolved: {resolved_count}
Remaining concerns: {concern_count}
```

## Phase 2: 実装（自動実装）

**既存の `claude-skills:plan-implement` をそのままサブエージェント委譲で使用する。**

### Step 2.0: base commit キャプチャ

実装開始直前に現在のコミットを記録する:

```bash
base_commit=$(git rev-parse HEAD)
```

この `base_commit` は Phase 2.5 のコードレビューで使用する。

### Step 2.1: 実装実行

1. サブエージェントで実装エージェントを起動する:

   プロンプト:
   ```
   `claude-skills:plan-implement` スキルを実行してください。計画ファイル {plan_file_path} の全ステップを実装してください。各ステップ完了ごとにコミットし、ステータスを更新してください。完了したら実装サマリー（変更ファイル数、テスト数、コミット数）を報告してください。
   ```

2. 結果を受け取る

表示:

```
── Phase 2: Implement ── DONE
Files changed: {N}
Tests added: {N}
Commits: {N}
```

## Phase 2.5: コードレビュー

**実装後のコードを Security と Architect が並行レビューする。**

[references/code-review-flow.md](references/code-review-flow.md) に従い、実装コードのレビューを行う。

### Step 2.5.1: diff 取得

```bash
git diff {base_commit}..HEAD
```

diff が 500 行を超える場合はファイル単位で分割して各レビュワーに配分する。

### Step 2.5.2: レビュワー spawn（並行）

2名のサブエージェントを **並行で** 起動する:

- **Security Verifier**: [team-config.md](../shared/references/team-config.md) の「スポーンプロンプト（コードレビュー時）」を使用
- **Architecture Verifier**: 同上

**注意**: チーム作成は使わない。サブエージェント2本の並行起動のみ。

各レビュワーのプロンプト:

```
あなたは {role_name} としてコードレビューに参加しています。
チーム名: {team_name}

{code_review_prompt_from_team_config}

## レビュー対象（git diff）
{diff_content}

## プロジェクトルール (CLAUDE.md)
{claude_md_content}

レビューが完了したら、結果を Lead にメッセージで報告してください。
```

### Step 2.5.3: 判定

[severity-and-verdicts.md](../shared/references/severity-and-verdicts.md) の「コードレビュー判定」に従う。

| 判定 | 条件 | アクション |
|------|------|-----------|
| PASS | 問題なし、または INFO のみ | Phase 3 へ |
| PASS WITH NOTES | WARN レベルの指摘あり | 指摘を記録して Phase 3 へ |
| NEEDS FIX | BLOCK レベルの問題あり | 修正 → 再レビュー |

### Step 2.5.4: NEEDS FIX 時の処理

- **通常モード**: 修正指示をサブエージェントに渡して再実装 → 再レビュー（最大1回リトライ）
- **headless モード**: ユーザーにレビュー結果を出力し処理を中断:

```
⚠️ CODE REVIEW: NEEDS FIX
Feature: {feature_name}

{review_findings}

コードレビューで BLOCK レベルの問題が検出されました。
修正後に再度 team-cycle を実行してください。
```

### Phase 2.5 表示

```
── Phase 2.5: Code Review ── {PASS|PASS WITH NOTES|NEEDS FIX}
Reviewers: Security, Architect
Findings: {block_count} BLOCK, {warn_count} WARN, {info_count} INFO
```

## Phase 3: 完了処理

### Step 3.1: 結果ファイル生成

`.agents/artifacts/plans/results/{plan_basename}_result.md` に出力（ディレクトリがなければ `mkdir -p` で作成）。

```markdown
# Cycle Result: {feature_name}

**Plan:** {plan_file_path}
**Executed:** {datetime}
**Mode:** AgenticTeam Review

## Team Review
- Verdict: {APPROVED / APPROVED WITH CONCERNS}
- Reviewers: {active_count}/{total} ({role_names})
- Discussion rounds: {round_count}
- Issues resolved: {resolved_count}
- Remaining concerns: {concern_count}

### Review Highlights
{議論のハイライト要約}

## Implementation
- Steps completed: {N}/{total}
- Files changed: {N}
- Tests added: {N}
- Commits: {N}

## Code Review
- Verdict: {PASS / PASS WITH NOTES / NEEDS FIX}
- Reviewers: Security, Architect
- Findings: {block_count} BLOCK, {warn_count} WARN, {info_count} INFO

## Commits
{git log --oneline のコミット一覧}

## Notes
{特記事項があれば}
```

### Step 3.2: status.md 更新

**ガード条件**: `.agents/artifacts/status.md` の Current Session が既に空（`_No active session`）または Completed の場合はこのステップをスキップする。

`skills/plan/references/status-update-guide.md` の **Case 2（In Progress → Completed）** の手順に従う:

1. **Step 2a**: session-history.md にアーカイブ
2. **Step 2b**: Session History セクションをクリア
3. **Step 2c**: Current Session をクリア

### Step 3.3: コミット

`claude-skills:commit` スキルを実行する。

コミット対象がなければスキップする。

### Step 3.4: Issue 自動 close

計画ファイルを読み、`**Issue:**` 行が存在するか確認する。

- `**Issue:**` 行がある場合: issue slug を抽出し、`claude-skills:issue` スキルを `close {slug}` 引数で実行する
  - close が失敗した場合は警告メッセージを表示するのみで、cycle 自体は成功扱いとする
- `**Issue:**` 行がない場合: このステップをスキップする

### Step 3.5: 最終表示

```
══════════════════════════════════════
TEAM-CYCLE COMPLETE
Feature: {feature_name}
Review: {verdict} ({round_count} rounds, {active_count}/{total} reviewers)
Implement: {steps_done}/{steps_total} steps
Commits: {N}
Result: {result_file_path}
══════════════════════════════════════
```

## エラーハンドリング

### Phase 0 のエラー

- **環境変数未設定**: エラーメッセージを表示して中断
- **計画ファイルが見つからない**: エラーメッセージを表示して中断
- **パス検証失敗**: エラーメッセージを表示して中断

### Phase 1 のエラー

- **チーム作成失敗**: エラーメッセージを表示して中断（チーム解散不要）
- **メンバー起動失敗（2名以上成功）**: 成功したメンバーで続行
- **メンバー起動失敗（1名以下）**: チーム解散 → 中断
- **REJECTED 判定**: チーム解散 → Status 更新 → 中断
- **予期しないエラー**: チーム解散 → エラーメッセージ表示 → 中断

### Phase 2 のエラー

- **実装エージェントエラー**: エラー内容を表示し、どのステップまで完了したかを記録して中断

## 重要なルール

- **チーム解散は必ず実行する**: チーム作成以降のどの段階でエラーが発生しても、チーム解散を必ず実行する
- **ヘッドレス実行**: ユーザーへの確認プロンプトは出さない
- **既存との互換性**: 結果ファイル、status.md、session-history.md は既存 cycle と同じフォーマット
- **Phase 2 は既存スキルを再利用**: `claude-skills:plan-implement` をそのまま使う
- **REJECTED は絶対に無視しない**: BLOCK が解消不可なら実装に進まない
- 問題の根本原因が不明な場合は、team-cycle 実行前に `/claude-skills:investigate` で読み取り専用の事前調査を推奨する

## References

- チーム構成: [skills/shared/references/team-config.md](../shared/references/team-config.md)
- レビュー議論フロー: [references/review-flow.md](references/review-flow.md)
- コードレビューフロー: [references/code-review-flow.md](references/code-review-flow.md)
- 重大度・判定基準: [skills/shared/references/severity-and-verdicts.md](../shared/references/severity-and-verdicts.md)
