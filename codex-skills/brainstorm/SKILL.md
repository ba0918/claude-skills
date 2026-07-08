---
name: brainstorm
description: アイデアの壁打ちに特化したスキル。発散→収束→plan化の導線を提供する。壁打ち中はファイル編集を一切行わず議論に集中する。「壁打ち」「brainstorm」「アイデア」で起動。
---

# Brainstorm — Idea Sparring (Codex Edition)

アイデアの壁打ちに特化したスキル。議論だけを行い、LLMが勝手に実装に走らない壁打ちセッションを提供する。
壁打ちの成果をメモファイルとして永続化し、後から参照できるようにする。

## Codex CLI ツールの使い分け

- **shell** — コードベース調査用の読み取り専用コマンド（`cat`, `rg`, `find`, `git log`, `git diff`, `ls` 等）。Wrap / Plan ワークフローでは `mkdir -p` / `mv` も使用する
- **apply_patch** — Wrap / Plan ワークフローでのメモ・インデックスファイルの作成・更新**のみ**。Session / Resume の壁打ち中は使用禁止
- **会話ターンでの対話** — ユーザーとの壁打ちは会話ターンで平文の質問（選択肢があれば列挙し番号/短文で回答を促す）として行う。**Codex の `request_user_input` は Plan mode 限定（default/exec 不可）のため使わない。** 壁打ちが本質のスキルなので対話ループは維持する（headless 化しない）。応答チャネルが無い headless/exec 文脈では安全側デフォルトを勝手に確定せず、対話不能を報告して中断（no-op）する
- **`$skill` メンション** — `$plan` / `$cycle` / `$team-cycle` の呼び出し

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

- **apply_patch** ツール — ファイル作成・編集禁止
- **shell リダイレクトでのファイル書き込み** — `>`, `>>`, `tee`, heredoc（`cat <<EOF > file`）等によるファイル作成・上書き禁止

#### 禁止行為

- コード生成・実装提案禁止（擬似コードでの概念説明は可）
- 「じゃあ実装しますね」「コードを書きます」は絶対に言わない

#### 許可ツール

- **shell** — **読み取り専用コマンドのみ**（`cat` / `rg` / `find` によるコードベース調査、`git log`, `git diff`, `ls` 等）
- **会話ターンでの対話** — ユーザーとの対話は会話ターンで行う（`request_user_input` は Plan mode 限定のため使わない）

### フロー

1. テーマを $ARGUMENTS から取得（なければ会話ターンで聞く）
2. **行き詰まり提案済みフラグを初期化**: `stuck_hint_shown = false`
3. 壁打ち対話ループに入る:
   a. ユーザーの発言を受け取る
   b. **行き詰まり検出**（`stuck_hint_shown == false` の場合のみ）:
      - ユーザー発言に以下のトリガーキーワード（部分一致、大文字小文字無視）が含まれるか判定:
        - 日本語: 「行き詰ま」「わからない」「どうすれば」「手詰まり」「煮詰ま」「堂々巡り」「進まない」
        - 英語: "stuck", "no idea", "don't know", "dead end", "going in circles"
      - キーワード検出時、以下のブロックを**ステップ c で生成する応答本文の冒頭**に配置し、`stuck_hint_shown = true` に設定（誘導ブロック → 通常応答本文、の順で出力する）:
        ```
        💡 行き詰まった時は `$problem-solving` で思考ツールを試せます:
        - `simplify` — 「全ては〇〇の特殊ケース」を見つける
        - `invert` — 前提を反転させてみる
        - `collide` — 無関係な概念を衝突させる
        - `scale` — 極端なスケールでテストする
        - `pattern` — 他ドメインのパターンから学ぶ
        ```
      - 2回目以降のキーワード検出では表示を抑制する（`stuck_hint_shown == true` なのでスキップ）
   c. 応答を生成する:
      - ユーザーのアイデアに対して質問・深掘り・反論・別視点を提供
   d. 必要に応じて既存のコードベースを shell（`cat` / `rg` / `find`）で調査（読み取り専用）
   e. 会話ターンで次の入力を求める
   f. ユーザーが「wrap」「まとめて」「終わり」等と言ったらループ終了
4. ループ終了時に Wrap Workflow への誘導メッセージを表示:
   ```
   壁打ちを終了します。
   `$brainstorm wrap` でアイデアをメモに整理できます。
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

- 現在の会話に壁打ちセッションの内容がない場合（単独で `$brainstorm wrap` が呼ばれた場合）、「壁打ちセッションが見つかりません。先に `$brainstorm テーマ` で壁打ちを行ってください」と表示して終了

### Steps

1. 現在の会話から壁打ちの内容を整理する
2. 会話ターンでタイトルとサマリーを確認
3. `docs/ideas/` ディレクトリを作成（なければ shell で `mkdir -p`）
4. slug を生成: `yyyymmddhhmmss_{kebab-title}` (date +%Y%m%d%H%M%S)
5. [references/idea-template.md](references/idea-template.md) をもとにメモファイルを生成: `docs/ideas/{slug}.md`
   - ファイル作成は **`apply_patch` ツールで実行**（`shell` の `cat <<EOF` や `tee` は使わない）
6. `docs/ideas/idea-status.md` を更新（なければ以下のテンプレートで apply_patch により作成）:
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

壁打ち内容に機密情報が含まれる場合、メモファイルに書き出す前に会話ターンで確認する。

---

## List Workflow

### Steps

1. `docs/ideas/idea-status.md` を shell（`cat`）で読む
   - なければ「まだアイデアがありません」と表示して終了
2. テーブル内容をそのまま表示
3. 件数サマリーを表示:
   ```
   📊 アイデア数: {N}
   ```

---

## Plan Workflow

### Steps

1. `docs/ideas/idea-status.md` を shell（`cat`）で読む
   - なければ「まだアイデアがありません」と表示して終了
2. 会話ターンで対象アイデアを選択（エントリが 1 件のみでも省略せず明示的に選択プロセスを実行する）
3. アイデアファイルを読み込む
   - **Title の出典**: `idea-status.md` のテーブルの最初のカラムのリンクテキスト（= Wrap Workflow で保存した `kebab-title`）を使用する
   - **Summary の出典**: アイデアファイル本文の `## Summary` セクションの内容
4. `$plan` メンションで plan 作成を実行（引数フォーマット: `{Title}: {Summary from idea file}` — plan は $ARGUMENTS をそのまま What & Why の種として使う）
   - **plan の出力**: 実行後、plan は `docs/plans/{new_timestamp}_{kebab-title}.md` を新規生成する（`new_timestamp` は plan 起動時の `date +%Y%m%d%H%M%S`）。このパスを「生成された plan ファイルパス」として保持し、Step 4.5 の引数に渡す
4.5. Optional cycle execution:
   - If `--team-cycle` is present in the original `$ARGUMENTS`: Remove the flag, then execute `$team-cycle` with the created plan file path (from Step 4) as the argument. Skip Step 7 entirely (do not output any completion message — team-cycle produces its own completion log).
   - Else if `--cycle` is present in the original `$ARGUMENTS`: Remove the flag, then execute `$cycle` with the created plan file path (from Step 4) as the argument. Skip Step 7 entirely (do not output any completion message — cycle produces its own completion log).
   - Otherwise: Continue to Step 5 (no cycle execution, show the completion message with Next Steps in Step 7 as usual).
   - Note: If both `--team-cycle` and `--cycle` are specified, `--team-cycle` takes priority.
5. アーカイブ処理を実行（Status 更新前にファイルを移動する）:
   - `docs/ideas/archives/` ディレクトリを作成（なければ shell で `mkdir -p`）
   - `docs/ideas/{slug}.md` を shell（`mv`）で `docs/ideas/archives/{slug}.md` に移動
   - `idea-status.md` のテーブルから該当エントリを apply_patch で削除し、`Last Updated` を今日の日付に更新
6. アーカイブされたアイデアファイル内の Status 欄を apply_patch で更新（移動後のファイルが対象）:
   - `docs/ideas/archives/{slug}.md` 内の `**Status:** 💡 Idea` を `**Status:** 📋 Planned` に書き換える
7. 完了メッセージ表示:
   ```
   ✅ アイデアから plan を作成しました!
   📄 Plan: docs/plans/{timestamp}_{slug}.md
   📦 Archived: docs/ideas/archives/{slug}.md

   ## Next Steps
   1. `$plan-reviewer` で計画をレビュー
   2. `$cycle` でサイクル実行
   3. `$team-cycle` でチームレビュー付きサイクル実行
   ```

---

## Resume Workflow（既存メモを元に壁打ち再開）

既存のアイデアメモを読み込み、その内容をコンテキストとして壁打ちセッションを再開する。

### 絶対的な制約

Session Workflow と同一の制約が適用される:
- **apply_patch** ツール使用禁止、shell リダイレクト（`>`, `tee`, heredoc）でのファイル書き込み禁止
- コード生成・実装提案禁止

### Steps

1. `resume` キーワード以降の $ARGUMENTS から slug を取得
   - slug がなければ `docs/ideas/idea-status.md` を読んでテーブルを表示し、会話ターンで対象アイデアを選択
   - `idea-status.md` が存在しなければ「まだアイデアがありません」と表示して終了
2. `docs/ideas/{slug}.md` を shell（`cat`）で読み込む
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
4. Session Workflow と同じ対話ループを実行（Session Workflow のステップ 3a-3f と同一）
   - 前回の Open Questions を優先的に議論の起点とする
5. ユーザーが「wrap」「まとめて」「終わり」等と言ったらループ終了
6. ループ終了時に Wrap Workflow（上書き更新モード）への誘導メッセージを表示:
   ```
   壁打ちを終了します。
   `$brainstorm wrap` でアイデアメモを更新できます。
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
