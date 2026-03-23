---
name: team-brainstorm
description: チーム議論型のブレインストーミング。4つの異なる思考スタイル（Challenger/Explorer/Connector/Grounded）で多角的にアイデアを発散させる。「team brainstorm」「チーム壁打ち」「チームブレスト」で起動。
---

# Team Brainstorm

AgenticTeam を使った複数の思考スタイルによるチーム議論型ブレインストーミング。
1人の Claude では視点が偏りがちな発散フェーズを、4つの異なるロール（Challenger/Explorer/Connector/Grounded）で多角化し、アイデアの質と多様性を向上させる。

> **合意形成を目指さない**: team-plan/team-cycle とは根本的に異なり、矛盾・対立を可視化して記録する。

## Workflow Selection

$ARGUMENTS の先頭キーワードでワークフローを決定する:

- `wrap` → **Wrap Workflow**（整理・サマリー生成）
- `list` → **List Workflow**（一覧表示）
- `plan` → **Plan Workflow**（plan に変換）
- `resume` → **Resume Workflow**（既存メモを元に壁打ち再開）
- (なし or テーマ文字列) → **Session Workflow**（チーム壁打ちセッション）

---

## Session Workflow（チーム壁打ちセッション）

### 絶対的な制約

#### 禁止ツール（いかなる状況でも使用禁止）

- **Edit** ツール — ファイル編集禁止
- **Write** ツール — ファイル作成・上書き禁止
- **NotebookEdit** ツール — ノートブック編集禁止

> Session 中はアイデアの発散に集中する。ファイル操作は Wrap Workflow で行う。

#### 禁止行為

- コード生成・実装提案禁止（擬似コードでの概念説明は可）
- 「じゃあ実装しますね」「コードを書きます」は絶対に言わない

#### 許可ツール

- **Read** — ファイルの読み取り（コードベース調査用）
- **Grep** — パターン検索（コードベース調査用）
- **Glob** — ファイル検索（コードベース調査用）
- **Bash** — **読み取り専用コマンドのみ**（`git log`, `git diff`, `ls`, `cat` 等）
- **AskUserQuestion** — ユーザーとの対話
- **TeamCreate** — チーム作成
- **TeamDelete** — チーム解散
- **SendMessage** — チームメンバーとの通信
- **Agent** — サブエージェント起動（チームメンバー spawn 用）

### Flow Overview

```
Session Workflow
  │
  ├─ Phase 0: 準備
  │    ├─ 環境変数チェック
  │    ├─ テーマ取得
  │    └─ Domain Expert 参加の有無を確認
  │
  ├─ Phase 1: チーム壁打ち（try-finally で TeamDelete 保証）
  │    ├─ TeamCreate → Agent spawn × 4 (+ optional Domain Expert)
  │    ├─ 発散ループ（brainstorm-flow.md 準拠）
  │    └─ TeamDelete（必ず実行）
  │
  └─ Wrap への誘導
```

### Phase 0: 準備

#### Step 0.1: 環境変数チェック

**重要**: TeamCreate を使用するには、実験的機能フラグが必要。

以下のコマンドで環境変数を確認する:

```bash
echo "${CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS:-not_set}"
```

未設定（`not_set`）の場合:

```
⛔ TEAM-BRAINSTORM ABORTED: AgenticTeam feature not enabled

Set the environment variable before running:
  export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

Then retry: /claude-skills:team-brainstorm
```

中断する。

#### Step 0.2: テーマ取得

1. `$ARGUMENTS` からテーマを取得する
   - 空の場合は AskUserQuestion で「何について壁打ちしたいですか？」と聞く
2. テーマが得られたらコードベースを調査し、関連ファイルの構造・既存実装を把握する

#### Step 0.3: Domain Expert 確認

AskUserQuestion でユーザーに確認する:

```
テーマ: {theme}

特定のドメイン専門家を追加しますか？
例: 「金融ドメイン」「医療ドメイン」「ゲームデザイン」等

不要な場合は「なし」「いらない」「スキップ」等で続行できます。
```

- ユーザーがドメインを指定 → Domain Expert を追加（5ロール体制）
- 「なし」等 → 4ロール体制で続行

### Phase 1: チーム壁打ち（AgenticTeam）

**重要**: Phase 1 の全処理は **TeamDelete を保証する try-finally パターン** で実装する。TeamCreate 成功後、以降のどの段階でエラーが発生しても TeamDelete を必ず実行する。

#### Step 1.1: コンテキスト収集

メンバーに渡すコンテキストを収集する:

```bash
# CLAUDE.md
cat CLAUDE.md 2>/dev/null || echo ""
```

#### Step 1.2: チーム作成

TeamCreate ツールでチームを作成する:

- **team_name**: `team-brainstorm-{timestamp}`（timestamp は現在時刻）

#### Step 1.3: メンバー spawn（並行）

[references/brainstorm-roles.md](references/brainstorm-roles.md) に定義されたロールを **並行で** Agent spawn する（Explore サブエージェント型）。

**基本4ロール（必須）:**
- Challenger（挑戦者）
- Explorer（探索者）
- Connector（接続者）
- Grounded（地に足）

**追加ロール（optional）:**
- Domain Expert（Step 0.3 でユーザーが指定した場合のみ）

各 Agent のプロンプトは [brainstorm-roles.md](references/brainstorm-roles.md) のスポーンプロンプトを使用する。プレースホルダーを以下で置換:

- `{team_name}` → `team-brainstorm-{timestamp}`
- `{theme}` → ユーザーのテーマ
- `{context}` → コードベース調査結果 + CLAUDE.md
- `{domain_name}` → ユーザー指定のドメイン名（Domain Expert の場合）
- `{domain_description}` → ドメインの説明（Domain Expert の場合）

**spawn 失敗時の処理:**

- 成功した Agent が 2 名以上 → 続行
- 成功した Agent が 1 名以下 → TeamDelete して中断:

```
⛔ TEAM-BRAINSTORM ABORTED: Insufficient team members (need >= 2, got {count})
Team disbanded.
```

#### Step 1.4: 発散ループ

[references/brainstorm-flow.md](references/brainstorm-flow.md) に従い、発散ループを実行する。

各ラウンドは3つのフェーズで構成される:

1. **Phase 1 — 開放的発散**: 各ロールに SendMessage でテーマを共有 → 並行で独立にアイデアを3-5個生成 → SendMessage で Lead に報告
2. **Phase 2 — 論争メモリ分類**: Lead が全アイデアを Accepted / Controversial / Frontier に分類
3. **Phase 3 — ユーザーフィードバック + 深掘り**: 分類結果をユーザーに表示 → AskUserQuestion でフィードバック → チームに深掘りを指示

**ラウンドサマリー表示（各ラウンド終了時）:**

```
── Round {N} ──
Accepted: {count}件
Controversial: {count}件（{対立の概要}）
Frontier: {count}件
Total ideas explored: {cumulative_count}
```

**ループ継続条件:**
- ユーザーが「もっと」「続き」「深掘り」等 → 次ラウンドへ
- ユーザーが「wrap」「まとめて」「終わり」等 → ループ終了

**Round 2 以降の特別ルール:**
- 前ラウンドの Controversial と Frontier を追加コンテキストとして含め、深掘りを優先する
- 新しいアイデアも歓迎する

#### Step 1.5: TeamDelete

**必ず実行する。** 正常完了・エラー・ユーザー中断のいずれの場合も。

TeamDelete ツールでチームを解散:

- **team_name**: `team-brainstorm-{timestamp}`

#### 一時ファイルのクリーンアップ

Session 中に `.claude/tmp/` 配下に一時ファイルを作成した場合は、TeamDelete の直後（Session 終了時）に削除する。

```bash
rm -f .claude/tmp/team-brainstorm-*.json 2>/dev/null
```

### Session 終了表示

```
壁打ちを終了します。

── Session Summary ──
Rounds: {total_rounds}
Accepted: {count}件
Controversial: {count}件
Frontier: {count}件
Total ideas explored: {total_count}

`/claude-skills:team-brainstorm-wrap` でアイデアをメモに整理できます。
```

---

## Wrap Workflow（整理・サマリー生成）

### 前提チェック

- 現在の会話にチーム壁打ちセッションの内容がない場合（単独で呼ばれた場合）、「壁打ちセッションが見つかりません。先に `/claude-skills:team-brainstorm テーマ` で壁打ちを行ってください」と表示して終了

### Steps

1. 現在の会話から壁打ちの内容を整理する（論争メモリを含む）
2. AskUserQuestion でタイトルとサマリーを確認
3. `docs/ideas/` ディレクトリを作成（なければ `mkdir -p`）
4. slug を生成: `YYYY-MM-DD_{kebab-title}`
5. [references/session-template.md](references/session-template.md) をもとにメモファイルを生成: `docs/ideas/{slug}.md`
   - 論争メモリ（Accepted / Controversial / Frontier）のセクションを含める
   - Round History を含める
6. `docs/ideas/idea-status.md` を更新（なければ以下のテンプレートで作成）:
   ```markdown
   # Idea Status

   **Last Updated:** YYYY-MM-DD

   | Idea | Tags | Created | Status | Summary |
   |------|------|---------|--------|---------|
   ```
7. テーブルの末尾に行を追加:
   ```
   | [{kebab-title}]({slug}.md) | `{tags}` | {YYYY-MM-DD} | 💡 Idea | {summary} |
   ```
8. **Last Updated** を今日の日付に更新
9. 完了メッセージ表示:
   ```
   ✅ アイデアを保存しました!
   📄 File: docs/ideas/{slug}.md
   📋 Index: docs/ideas/idea-status.md
   ```

### セキュリティ

壁打ち内容に機密情報が含まれる場合、メモファイルに書き出す前に AskUserQuestion で確認する。

---

## List Workflow

### Steps

1. `docs/ideas/idea-status.md` を読む
   - なければ「まだアイデアがありません」と表示して終了
2. テーブル内容をそのまま表示
3. 件数サマリーを表示:
   ```
   📊 アイデア数: {N}
   ```

---

## Plan Workflow

### Steps

1. `docs/ideas/idea-status.md` を読む
   - なければ「まだアイデアがありません」と表示して終了
2. AskUserQuestion で対象アイデアを選択
3. アイデアファイルを読み込む
4. Skill ツールで `claude-skills:plan-create` を実行（引数フォーマット: `{Title}: {Summary from idea file}` — plan-create は $ARGUMENTS をそのまま What & Why の種として使う）
5. アイデアの Status を `💡 Idea` → `📋 Planned` に更新
6. アーカイブ処理を実行:
   - `docs/ideas/archives/` ディレクトリを作成（なければ `mkdir -p`）
   - `docs/ideas/{slug}.md` を `docs/ideas/archives/{slug}.md` に移動
   - `idea-status.md` のテーブルから該当エントリを削除
7. 完了メッセージ表示:
   ```
   ✅ アイデアから plan を作成しました!
   📄 Plan: docs/cycles/{timestamp}_{slug}.md
   📦 Archived: docs/ideas/archives/{slug}.md

   ## Next Steps
   1. `/plan-review` で計画をレビュー
   2. `/claude-skills:cycle` でサイクル実行
   ```

---

## Resume Workflow（既存メモを元に壁打ち再開）

既存のアイデアメモを読み込み、その内容をコンテキストとしてチーム壁打ちセッションを再開する。

### 絶対的な制約

Session Workflow と同一の制約が適用される:
- **Edit / Write / NotebookEdit** ツール使用禁止
- コード生成・実装提案禁止

### Steps

1. `resume` キーワード以降の $ARGUMENTS から slug を取得
   - slug がなければ `docs/ideas/idea-status.md` を読んでテーブルを表示し、AskUserQuestion で対象アイデアを選択
   - `idea-status.md` が存在しなければ「まだアイデアがありません」と表示して終了
2. `docs/ideas/{slug}.md` を読み込む
   - ファイルが存在しなければ `docs/ideas/` のファイル一覧を表示してエラー終了
3. メモの内容を要約して表示し、Session Workflow の Phase 0 から開始する（テーマはメモのタイトルを使用）:
   ```
   📄 アイデア "{title}" を読み込みました。

   ## 前回のまとめ
   {Summary セクションの内容}

   ## 論争メモリ
   Accepted: {count}件
   Controversial: {count}件
   Frontier: {count}件

   ## 未解決の疑問
   {Open Questions セクションの内容}

   ここからチーム壁打ちを再開します！
   ```
4. Session Workflow と同じフローを実行（Phase 0.1 の環境変数チェックから）
   - 前回の論争メモリを初期コンテキストとしてチームに共有する
   - 前回の Open Questions を優先的に議論の起点とする
5. ユーザーが「wrap」「まとめて」「終わり」等と言ったらループ終了
6. ループ終了時に Wrap Workflow（上書き更新モード）への誘導メッセージを表示:
   ```
   壁打ちを終了します。
   `/claude-skills:team-brainstorm-wrap` でアイデアメモを更新できます。
   ```

### Wrap での上書き更新

Resume 後に Wrap Workflow が実行された場合:
- 既存の `docs/ideas/{slug}.md` を**上書き更新**する（新規作成ではない）
- slug は元のメモのものをそのまま使用する
- idea-status.md のテーブル行は更新不要（slug が変わらないため）
- **Last Updated** のみ今日の日付に更新する

---

## File Structure (generated in the project using this skill)

```
docs/ideas/
  idea-status.md             - インデックスファイル（既存 brainstorm と共有）
  YYYY-MM-DD_{slug}.md       - 個別アイデアメモ（論争メモリ含む）
  archives/                  - 完了・破棄したアイデアの保管先
```

## Status Types

| ステータス | 意味 |
|-----------|------|
| 💡 Idea | 壁打ち済み、まだ plan 化していない |
| 📋 Planned | plan に変換済み |
| 🗑️ Dropped | 見送り・破棄 |

## Template

- **セッション記録:** [references/session-template.md](references/session-template.md)
- **ロール定義:** [references/brainstorm-roles.md](references/brainstorm-roles.md)
- **発散フロー:** [references/brainstorm-flow.md](references/brainstorm-flow.md)

## Notes

- idea-status.md は既存 brainstorm スキルと共有する。どちらのスキルで作られたアイデアも同じインデックスに表示される
- list / plan のコマンドは既存 brainstorm のコマンドを共用する（idea-status.md が共通なので）
- 壁打ち内容に機密情報を含めないこと
- Session 中のファイル編集は一切禁止。アイデアの記録は Wrap Workflow でのみ行う
- `.claude/tmp/` 配下の一時ファイルは Session 終了時（TeamDelete 直後）にクリーンアップする

## References

- ロール定義: [references/brainstorm-roles.md](references/brainstorm-roles.md)
- 発散フロー: [references/brainstorm-flow.md](references/brainstorm-flow.md)
- セッションテンプレート: [references/session-template.md](references/session-template.md)
- チーム共有設定: [skills/shared/references/team-config.md](../shared/references/team-config.md)
