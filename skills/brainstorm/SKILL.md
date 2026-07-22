---
name: brainstorm
description: アイデアの壁打ちに特化したスキル。発散→収束→plan化の導線を提供する。壁打ち中はファイル編集を一切行わず議論に集中する。「壁打ち」「brainstorm」「アイデア」で起動。
---

# Brainstorm

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

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

#### 禁止操作（いかなる状況でも禁止）

- ファイルの編集・作成・上書き禁止
- ノートブック編集禁止

#### 禁止行為

- コード生成・実装提案禁止（擬似コードでの概念説明は可）
- 「じゃあ実装しますね」「コードを書きます」は絶対に言わない

#### 許可操作

- ファイルの読み取り（コードベース調査用）
- パターン検索（コードベース調査用）
- ファイル一覧取得（コードベース調査用）
- シェルコマンド（**読み取り専用のみ**: `git log`, `git diff`, `ls`, `cat` 等）
- Codex セカンドオピニオンの取得（サブエージェント経由）
- ユーザーとの対話（選択肢を提示して確認）

### フロー

1. テーマを $ARGUMENTS から取得（なければユーザーに聞く）
2. **Codex 接続状態を初期化**: `codex_available = true`
3. **行き詰まり提案済みフラグを初期化**: `stuck_hint_shown = false`
4. 壁打ち対話ループに入る:
   a. ユーザーの発言を受け取る
   b. **行き詰まり検出**（`stuck_hint_shown == false` の場合のみ）:
      - ユーザー発言に以下のトリガーキーワード（部分一致、大文字小文字無視）が含まれるか判定:
        - 日本語: 「行き詰ま」「わからない」「どうすれば」「手詰まり」「煮詰ま」「堂々巡り」「進まない」
        - 英語: "stuck", "no idea", "don't know", "dead end", "going in circles"
      - キーワード検出時、以下のブロックを**ステップ d で生成する Claude 応答本文の冒頭**に配置し、`stuck_hint_shown = true` に設定（誘導ブロック → 通常応答本文 → `💡 Codex の視点:` セクション、の順で出力する）:
        ```
        💡 行き詰まった時は `/claude-skills:problem-solving` で思考ツールを試せます:
        - `simplify` — 「全ては〇〇の特殊ケース」を見つける
        - `invert` — 前提を反転させてみる
        - `collide` — 無関係な概念を衝突させる
        - `scale` — 極端なスケールでテストする
        - `pattern` — 他ドメインのパターンから学ぶ
        ```
      - 2回目以降のキーワード検出では表示を抑制する（`stuck_hint_shown == true` なのでスキップ）
   c. **Codex セカンドオピニオン取得**（`codex_available == true` の場合のみ）:
      - Codex セカンドオピニオン用のサブエージェントでユーザーの発言 + 壁打ちテーマ + これまでの議論の要約を送信
      - プロンプト: 「以下の壁打ちテーマとユーザーの発言に対して、異なる視点・反論・見落とし・関連するアイデアを提供してください。テーマ: {theme}。ユーザーの発言: {user_message}。これまでの議論: {summary}」
        - **`{summary}` の扱い**: 初回ターン（履歴なし）の場合は `（最初のターン、履歴なし）` という文字列を代入する。2ターン目以降は過去ターンの議論要約（1〜3 文程度）を代入する
      - セキュリティ制約: 会話テキストのみを渡す（ファイル読み取り結果は渡さない）
      - **成功時**: Codex の意見を保持して次のステップへ
      - **失敗時**: 以下のいずれかに該当する場合は失敗として扱う:
        - サブエージェント呼び出しがエラーを返した
        - サブエージェントがタイムアウトした
        - Codex セカンドオピニオンが環境に存在しない / 呼び出し不可
        - Codex の応答が空、または指定フォーマットを満たさない
      - 失敗時の処理: 初回のみ `⚠️ Codex unavailable — proceeding with Claude only` を表示し、`codex_available = false` に設定。以降のターンでは Codex 呼び出しをスキップ
   d. Claude が応答を生成する（Codex の意見があればそれを統合）:
      - ユーザーのアイデアに対して質問・深掘り・反論・別視点を提供
      - Codex の意見がある場合、応答末尾に以下のセクションを追記:
        ```
        💡 Codex の視点:
        {Codex の意見の要約}
        ```
   e. 必要に応じて既存のコードベースをファイル読み取り・パターン検索で調査（読み取り専用）
   f. ユーザーに次の入力を求める
   g. ユーザーが「wrap」「まとめて」「終わり」等と言ったらループ終了
5. ループ終了時に Wrap Workflow への誘導メッセージを表示:
   ```
   壁打ちを終了します。
   `/claude-skills:brainstorm-wrap` でアイデアをメモに整理できます。
   ```

**Note**: Claude の応答生成とサブエージェント呼び出しは並行実行できないため、Codex 呼び出し → Claude 応答生成の順で逐次実行する。

共通パターンの詳細: [../shared/references/codex-integration.md](../shared/references/codex-integration.md)

### 壁打ち中の振る舞い

- 質問で深掘りする（Why? What if? How about?）
- 反論や懸念を率直に出す（「それだと〇〇が問題になりそう」）
- 別のアプローチを提案する（「こういう手もあるけど」）
- 過去の議論を要約して整理する（「ここまでの論点をまとめると」）
- 技術的実現可能性をコードベース調査で裏付ける（読み取り専用）
- 議論が特定の技術や手段に収束しかけたら技術の引力を確認する（「その技術を使わないとしたら、何を解決しようとしてる？」「技術名を抜いても問題を説明できる？」）— ブロックではなく問いかけとして

---

## Wrap Workflow（整理・サマリー生成）

### 前提チェック

- 現在の会話に壁打ちセッションの内容がない場合（単独で `/claude-skills:brainstorm-wrap` が呼ばれた場合）、「壁打ちセッションが見つかりません。先に `/claude-skills:brainstorm テーマ` で壁打ちを行ってください」と表示して終了

### Steps

1. 現在の会話から壁打ちの内容を整理する
2. ユーザーにタイトルとサマリーを確認
3. `.agents/artifacts/ideas/` ディレクトリを作成（なければ `mkdir -p`）
4. slug を生成: `yyyymmddhhmmss_{kebab-title}` (date +%Y%m%d%H%M%S)
5. [references/idea-template.md](references/idea-template.md) をもとにメモファイルを生成: `.agents/artifacts/ideas/{slug}.md`
6. `.agents/artifacts/ideas/idea-status.md` を更新（なければ以下のテンプレートで作成）:
   ```markdown
   # Idea Status

   **Last Updated:** YYYY-MM-DD HH:MM:SS

   | Idea | Tags | Created | Status | Summary |
   |------|------|---------|--------|---------|
   ```
7. テーブルの末尾に行を追加。リンクテキストはメモファイルの `#` 見出しタイトル（Step 2 で確認した人間可読タイトル）を使う — idea-status.md は導出インデックスであり、rebuild-index が各エントリの `#` 見出しから行を再生成するため、kebab-title を使うと再生成のたびに表記が変わってしまう:
   ```
   | [{アイデアの # 見出しタイトル}]({slug}.md) | `{tags}` | {YYYY-MM-DD HH:MM:SS} | 💡 Idea | {summary} |
   ```
8. **Last Updated** を今日の日付に更新
9. 完了メッセージ表示。冒頭に [ヒューマンリーダブル要約契約](../shared/references/human-readable-summary.md) に従う
   要約ブロックを置く（summary-first）。保存したアイデアの核を 1〜2 行のかみ砕いた言葉で述べ、
   壁打ちで残った未決定点を明示する（なければ「未決定点: なし」）。逐語再掲・網羅列挙はしない:
   ```
   📝 つまり: {保存したアイデアが「つまり何なのか」を、メモを読んでいない人にも
      伝わる平易な 1〜2 行で}。未決定点: {残った論点、なければ「なし」}

   ✅ アイデアを保存しました!
   📄 File: .agents/artifacts/ideas/{slug}.md
   📋 Index: .agents/artifacts/ideas/idea-status.md
   ```

### セキュリティ

壁打ち内容に機密情報が含まれる場合、メモファイルに書き出す前にユーザーに確認する。
要約ブロックにも機密値（トークン・鍵・個人情報）を含めない（契約の縮退規定に従い省略またはカテゴリ名に置換）。

---

## List Workflow

### Steps

1. `.agents/artifacts/ideas/idea-status.md` を読む
   - なければ「まだアイデアがありません」と表示して終了
2. テーブル内容をそのまま表示
3. 件数サマリーを表示:
   ```
   📊 アイデア数: {N}
   ```

---

## Plan Workflow

### Steps

1. `.agents/artifacts/ideas/idea-status.md` を読む
   - なければ「まだアイデアがありません」と表示して終了
2. ユーザーに対象アイデアを選択してもらう（エントリが 1 件のみでも省略せず明示的に選択プロセスを実行する）
3. アイデアファイルを読み込む
   - **Title の出典**: `idea-status.md` のテーブルの最初のカラムのリンクテキスト（= アイデアファイルの `#` 見出しタイトル。Wrap Workflow が保存し、rebuild-index も同じ値で再生成する）を使用する
   - **Summary の出典**: アイデアファイル本文の `## Summary` セクションの内容
4. `claude-skills:plan-create` スキルを実行（引数フォーマット: `{Title}: {Summary from idea file}` — plan-create は $ARGUMENTS をそのまま What & Why の種として使う）
   - **plan-create の出力**: 実行後、plan-create は `.agents/artifacts/plans/{new_timestamp}_{kebab-title}.md` を新規生成する（`new_timestamp` は plan-create 起動時の `date +%Y%m%d%H%M%S`）。このパスを「生成された plan ファイルパス」として保持し、Step 4.5 の引数に渡す
4.5. Optional cycle execution:
   - If `--team-cycle` is present in the original `$ARGUMENTS`: Remove the flag, then execute `claude-skills:team-cycle` via the Skill tool with the created plan file path (from Step 4) as the argument. Skip Step 7 entirely (do not output any completion message — team-cycle produces its own completion log).
   - Else if `--cycle` is present in the original `$ARGUMENTS`: Remove the flag, then execute `claude-skills:cycle` via the Skill tool with the created plan file path (from Step 4) as the argument. Skip Step 7 entirely (do not output any completion message — cycle produces its own completion log).
   - Otherwise: Continue to Step 5 (no cycle execution, show the completion message with Next Steps in Step 7 as usual).
   - Note: If both `--team-cycle` and `--cycle` are specified, `--team-cycle` takes priority.
5. アーカイブ処理を実行（Status 更新前にファイルを移動する）:
   - `.agents/artifacts/ideas/archives/` ディレクトリを作成（なければ `mkdir -p`）
   - `.agents/artifacts/ideas/{slug}.md` を `.agents/artifacts/ideas/archives/{slug}.md` に移動
   - `idea-status.md` のテーブルから該当エントリを削除し、`Last Updated` を今日の日付に更新
6. アーカイブされたアイデアファイル内の Status 欄を更新（移動後のファイルが対象）:
   - `.agents/artifacts/ideas/archives/{slug}.md` 内の `**Status:** 💡 Idea` を `**Status:** 📋 Planned` に書き換える
7. 完了メッセージ表示:
   ```
   ✅ アイデアから plan を作成しました!
   📄 Plan: .agents/artifacts/plans/{timestamp}_{slug}.md
   📦 Archived: .agents/artifacts/ideas/archives/{slug}.md

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
- ファイルの編集・作成・上書き・ノートブック編集禁止
- コード生成・実装提案禁止

### Steps

1. `resume` キーワード以降の $ARGUMENTS から slug を取得
   - slug がなければ `.agents/artifacts/ideas/idea-status.md` を読んでテーブルを表示し、ユーザーに対象アイデアを選択してもらう
   - `idea-status.md` が存在しなければ「まだアイデアがありません」と表示して終了
2. `.agents/artifacts/ideas/{slug}.md` を読み込む
   - ファイルが存在しなければ `.agents/artifacts/ideas/` のファイル一覧を表示してエラー終了
3. メモの内容を要約して表示し、壁打ち対話ループに入る:
   ```
   📄 アイデア "{title}" を読み込みました。

   ## 前回のまとめ
   {Summary セクションの内容}

   ## 未解決の疑問
   {Open Questions セクションの内容}

   ここから壁打ちを再開します！
   ```
4. Session Workflow と同じ対話ループを実行（Codex セカンドオピニオン付き — Session Workflow のステップ 4a-4g と同一）
   - 前回の Open Questions を優先的に議論の起点とする
   - 各ターンで Codex のセカンドオピニオンを取得し、`💡 Codex の視点:` として追記
   - Codex 接続失敗時は `⚠️ Codex unavailable — proceeding with Claude only` を表示し以降スキップ
5. ユーザーが「wrap」「まとめて」「終わり」等と言ったらループ終了
6. ループ終了時に Wrap Workflow（上書き更新モード）への誘導メッセージを表示:
   ```
   壁打ちを終了します。
   `/claude-skills:brainstorm-wrap` でアイデアメモを更新できます。
   ```

### Wrap での上書き更新

Resume 後に Wrap Workflow が実行された場合:
- 既存の `.agents/artifacts/ideas/{slug}.md` を**上書き更新**する（新規作成ではない）
- slug は元のメモのものをそのまま使用する
- idea-status.md のテーブル行は更新不要（slug が変わらないため）
- **Last Updated** のみ今日の日付に更新する

---

## File Structure (generated in the project using this skill)

```
.agents/artifacts/ideas/
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
