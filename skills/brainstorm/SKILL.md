---
name: brainstorm
description: アイデアの壁打ちに特化したスキル。発散→収束→plan化の導線を提供する。壁打ち中はファイル編集を一切行わず議論に集中する。「壁打ち」「brainstorm」「アイデア」で起動。
---

# Brainstorm

アイデアの壁打ちに特化したスキル。議論だけを行い、LLMが勝手に実装に走らない壁打ちセッションを提供する。
壁打ちの成果をメモファイルとして永続化し、後から参照できるようにする。

## Workflow Selection

$ARGUMENTS の先頭キーワードでワークフローを決定する:

- `wrap` → **Wrap Workflow**（整理・サマリー生成）
- `list` → **List Workflow**（一覧表示）
- `plan` → **Plan Workflow**（plan に変換）
- `resume` → **Resume Workflow**（既存メモを元に壁打ち再開）
- (なし or テーマ文字列) → **Session Workflow**（壁打ちセッション）

---

## Session Workflow（壁打ちセッション）

### 絶対的な制約

#### 禁止ツール（いかなる状況でも使用禁止）

- **Edit** ツール — ファイル編集禁止
- **Write** ツール — ファイル作成・上書き禁止
- **NotebookEdit** ツール — ノートブック編集禁止

#### 禁止行為

- コード生成・実装提案禁止（擬似コードでの概念説明は可）
- 「じゃあ実装しますね」「コードを書きます」は絶対に言わない

#### 許可ツール

- **Read** — ファイルの読み取り（コードベース調査用）
- **Grep** — パターン検索（コードベース調査用）
- **Glob** — ファイル検索（コードベース調査用）
- **Bash** — **読み取り専用コマンドのみ**（`git log`, `git diff`, `ls`, `cat` 等）
- **AskUserQuestion** — ユーザーとの対話

### フロー

1. テーマを $ARGUMENTS から取得（なければ AskUserQuestion で聞く）
2. 壁打ち対話ループに入る:
   - ユーザーのアイデアに対して質問・深掘り・反論・別視点を提供
   - 必要に応じて既存のコードベースを Read/Grep で調査（読み取り専用）
   - AskUserQuestion で次の入力を求める
   - ユーザーが「wrap」「まとめて」「終わり」等と言ったらループ終了
3. ループ終了時に Wrap Workflow への誘導メッセージを表示:
   ```
   壁打ちを終了します。
   `/claude-skills:brainstorm-wrap` でアイデアをメモに整理できます。
   ```

### 壁打ち中の振る舞い

- 質問で深掘りする（Why? What if? How about?）
- 反論や懸念を率直に出す（「それだと〇〇が問題になりそう」）
- 別のアプローチを提案する（「こういう手もあるけど」）
- 過去の議論を要約して整理する（「ここまでの論点をまとめると」）
- 技術的実現可能性をコードベース調査で裏付ける（読み取り専用）

---

## Wrap Workflow（整理・サマリー生成）

### 前提チェック

- 現在の会話に壁打ちセッションの内容がない場合（単独で `/claude-skills:brainstorm-wrap` が呼ばれた場合）、「壁打ちセッションが見つかりません。先に `/claude-skills:brainstorm テーマ` で壁打ちを行ってください」と表示して終了

### Steps

1. 現在の会話から壁打ちの内容を整理する
2. AskUserQuestion でタイトルとサマリーを確認
3. `docs/ideas/` ディレクトリを作成（なければ `mkdir -p`）
4. slug を生成: `yyyymmddhhmmss_{kebab-title}` (date +%Y%m%d%H%M%S)
5. [references/idea-template.md](references/idea-template.md) をもとにメモファイルを生成: `docs/ideas/{slug}.md`
6. `docs/ideas/idea-status.md` を更新（なければ以下のテンプレートで作成）:
   ```markdown
   # Idea Status

   **Last Updated:** YYYY-MM-DD HH:MM:SS

   | Idea | Tags | Created | Status | Summary |
   |------|------|---------|--------|---------|
   ```
7. テーブルの末尾に行を追加:
   ```
   | [{kebab-title}]({slug}.md) | `{tags}` | {YYYY-MM-DD HH:MM:SS} | 💡 Idea | {summary} |
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
4.5. Optional cycle execution:
   - If `--team-cycle` is present in the original `$ARGUMENTS`: Remove the flag, then execute `claude-skills:team-cycle` via the Skill tool with the created plan. Skip Step 7 (Next Steps display).
   - Else if `--cycle` is present in the original `$ARGUMENTS`: Remove the flag, then execute `claude-skills:cycle` via the Skill tool with the created plan. Skip Step 7 (Next Steps display).
   - Otherwise: Continue to Step 5 (no cycle execution, show Next Steps as usual).
   - Note: If both `--team-cycle` and `--cycle` are specified, `--team-cycle` takes priority.
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
   3. `/claude-skills:team-cycle` でチームレビュー付きサイクル実行
   ```

---

## Resume Workflow（既存メモを元に壁打ち再開）

既存のアイデアメモを読み込み、その内容をコンテキストとして壁打ちセッションを再開する。

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
3. メモの内容を要約して表示し、壁打ち対話ループに入る:
   ```
   📄 アイデア "{title}" を読み込みました。

   ## 前回のまとめ
   {Summary セクションの内容}

   ## 未解決の疑問
   {Open Questions セクションの内容}

   ここから壁打ちを再開します！
   ```
4. Session Workflow と同じ対話ループを実行（質問・深掘り・反論・別視点の提供）
   - 前回の Open Questions を優先的に議論の起点とする
5. ユーザーが「wrap」「まとめて」「終わり」等と言ったらループ終了
6. ループ終了時に Wrap Workflow（上書き更新モード）への誘導メッセージを表示:
   ```
   壁打ちを終了します。
   `/claude-skills:brainstorm-wrap` でアイデアメモを更新できます。
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
  idea-status.md             - インデックスファイル
  yyyymmddhhmmss_{slug}.md   - 個別アイデアメモ
  archives/                  - 完了・破棄したアイデアの保管先
```

## Status Types

| ステータス | 意味 |
|-----------|------|
| 💡 Idea | 壁打ち済み、まだ plan 化していない |
| 📋 Planned | plan に変換済み |
| 🗑️ Dropped | 見送り・破棄 |

## Template

- **アイデアメモ:** [references/idea-template.md](references/idea-template.md)

## Notes

- idea-status.md がインデックス。このファイルだけ読めば全体の状況が分かる
- Plan / Drop 時はアーカイブ処理（archives/ への移動 + テーブルからの行削除）を自動実行する
- 壁打ち内容に機密情報を含めないこと
