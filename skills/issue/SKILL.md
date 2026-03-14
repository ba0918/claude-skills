---
name: issue
description: Issue management for tracking out-of-scope problems discovered during plan execution. Supports create, list, cycle, and close workflows. Use when user wants to record issues, view issue list, convert issues to plan/cycle, or close resolved issues.
---

# Issue Management

plan 実行中に発見したスコープ外の問題を `docs/issues/` にローカルファイルとして記録し、後から plan → cycle に繋げるフローを提供する。

## ワークフロー選択

引数の最初のキーワードでワークフローを決定する:

- `create` → **Create ワークフロー**
- `list` → **List ワークフロー**
- `cycle` → **Cycle ワークフロー**
- `close` → **Close ワークフロー**

キーワード以降のテキストが各ワークフローへの引数となる。

---

## Create ワークフロー

新しい issue を記録する。

### 引数

- タイトル（必須）
- 概要（任意 — 省略時はタイトルと同じ）
- タグ（任意 — カンマ区切り）
- source（任意 — 発見元の計画ファイルパス等）

### 手順

1. 引数からタイトル・概要・タグ・source を解析する
2. `docs/issues/` ディレクトリを作成する（なければ `mkdir -p`）
3. `docs/issues/issue-status.md` が存在しなければ、以下のテンプレートで新規作成する:
   ```markdown
   # Issue Status

   **Last Updated:** {YYYY-MM-DD}

   | Issue | Tags | Created | Summary |
   |-------|------|---------|---------|
   ```
4. slug を生成する:
   - 日付: `YYYY-MM-DD` 形式
   - タイトルからスラッシュ(`/`)、ドット2連続(`..`)、バックスラッシュ(`\`)等のパス区切り文字・特殊文字を除去する
   - 残りの文字をケバブケースに変換する（スペース→ハイフン、小文字化、英数字とハイフンのみ残す）
   - 最終 slug: `{YYYY-MM-DD}_{kebab-title}`
5. [references/issue-template.md](references/issue-template.md) を読み込み、プレースホルダーを置換して `docs/issues/{slug}.md` に書き出す
6. `docs/issues/issue-status.md` のテーブル末尾に行を追加する:
   ```
   | [{kebab-title}]({slug}.md) | `{tags}` | {YYYY-MM-DD} | {概要} |
   ```
7. **Last Updated** を今日の日付に更新する
8. 作成結果を表示する:
   ```
   ✅ Issue created!
   📄 File: docs/issues/{slug}.md
   📋 Index: docs/issues/issue-status.md
   ```

---

## List ワークフロー

未解決 issue の一覧を表示する。

### 手順

1. `docs/issues/issue-status.md` を読み込む
   - 存在しない場合: 「issue がまだ登録されていません」と表示して終了
2. テーブル内容をそのまま表示する
3. テーブル行数をカウントし、件数サマリーを表示する:
   ```
   📊 Open issues: {N} 件
   ```

---

## Cycle ワークフロー

issue を plan → cycle に繋げて解決する。

### 手順

1. `docs/issues/issue-status.md` を読み込む
   - 存在しない場合: 「issue がまだ登録されていません」と表示して終了
2. AskUserQuestion で対象 issue を選択させる（テーブルの内容を提示し、slug を入力してもらう）
3. 選択された issue ファイル (`docs/issues/{slug}.md`) を読み込む
4. issue の内容（タイトル・概要）を基に Skill ツールで `plan-create` を実行する
   - 引数: issue のタイトルと概要を渡す
5. 作成された plan で Skill ツールで `cycle` を実行する
6. `plan-create` または `cycle` が失敗した場合はエラー内容を表示し、issue は open のまま保持して終了する
7. cycle 完了後、Skill ツールで `issue` を `close {slug}` 引数で実行する

---

## Close ワークフロー

issue をクローズ（アーカイブ）する。

### 引数

- issue slug（必須 — 省略時は AskUserQuestion で確認）

### 手順

1. 引数から issue slug を取得する（省略時は AskUserQuestion で確認）
2. issue ファイル `docs/issues/{slug}.md` の存在を確認する
   - 見つからない場合: `docs/issues/` 内のファイル一覧を表示し、エラーメッセージを出して終了
3. `docs/issues/archives/` ディレクトリを作成する（なければ `mkdir -p`）
4. issue ファイルを `docs/issues/archives/` に移動する（`mv` コマンド）
5. `docs/issues/issue-status.md` から該当 slug を含む行を Edit ツールで削除する
6. **Last Updated** を今日の日付に更新する
7. 結果を表示する:
   ```
   ✅ Issue closed!
   📦 Archived: docs/issues/archives/{slug}.md
   📋 Index updated: docs/issues/issue-status.md
   ```

---

## ファイル構成（スキル利用先プロジェクトに生成される）

```
docs/issues/
  issue-status.md             - インデックスファイル（LLM はまずこれを読む）
  YYYY-MM-DD_<slug>.md        - 個別 issue ファイル
  archives/                   - close 済み issue の保管場所
```

## issue-status.md のフォーマット

```markdown
# Issue Status

**Last Updated:** YYYY-MM-DD

| Issue | Tags | Created | Summary |
|-------|------|---------|---------|
| [slug](YYYY-MM-DD_slug.md) | `tag` | YYYY-MM-DD | 概要 |
```

## テンプレート

- **個別 issue:** [references/issue-template.md](references/issue-template.md)

## Notes

- issue-status.md がインデックスとして機能する。LLM は全 issue を開かず、このファイルだけ読めば状況を把握できる
- close = アーカイブ。close したら即 `archives/` に移動 + `issue-status.md` から行削除
- センシティブ情報を issue に記載しないこと
