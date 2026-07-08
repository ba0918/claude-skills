---
name: doc-write
description: LLMとのやり取り・調査結果・Web調査をリーダブルなドキュメントに昇華するスキル。Mermaid図付きの構造化ドキュメントを生成する。「ドキュメント書いて」「まとめてドキュメントに」「doc-write」で起動。
---

# Doc Write (Codex Edition)

LLM とのやり取り・調査結果・Web 調査をリーダブルなドキュメントに昇華するスキル。
想定読者に応じた粒度調整、テンプレート自動選択、Mermaid 図生成、フィードバックループによる品質向上を特徴とする。

## Codex CLI ツールの使い分け

- **会話ターンでの要件ディスカバリー** — 想定読者・テーマ・入力ソース・テンプレート選択・フィードバックなど、ユーザーへの確認はすべて会話ターンで平文の質問として尋ねる（選択肢は列挙して番号/短文で回答を促す）。doc-write は対話ディスカバリーが本質のスキルなので、この Q&A ループを維持する（default mode で成立）。**Codex の `request_user_input` は Plan mode 限定（default/exec 不可）のため使わない。** 応答が得られない headless 文脈では、収集済み情報で書けるところまで書き、未確定箇所を `TODO` として残して安全側に降格する
- **apply_patch** — ドキュメント生成・更新でのファイル作成・改変はすべて apply_patch で行う（shell リダイレクトでのファイル書き込みは禁止）
- **shell** — 調査・情報収集用の読み取り専用コマンド（`cat` / `rg` / `find` による既存ファイル・コンテキストの読み込み、`ls` でのファイル一覧、`date +%Y%m%d%H%M%S` での slug 生成、`mkdir -p` での出力ディレクトリ作成）。Web 調査は Codex CLI で利用可能な取得手段があればそれを使う

## 既存スキルとの住み分け

| スキル | 役割 | 出力 |
|--------|------|------|
| `brainstorm-wrap` | 壁打ちの軽量メモ | `docs/ideas/` |
| `investigate` | 問題の調査レポート | 会話上に出力 |
| **`doc-write`** | **知見のリーダブルなドキュメント化** | **`docs/writings/`** |

investigate の出力を doc-write の入力にする関係も想定。

## Workflow Selection

$ARGUMENTS の先頭キーワードでワークフローを決定する:

- `resume` → **Resume Workflow**（既存ドキュメントの再編集）
- (なし or テーマ文字列) → **Write Workflow**（メインワークフロー）

---

## Write Workflow（メインワークフロー）

### Phase 1: 要件確認

1. **想定読者の確認**（必須質問）
   - 会話ターンで必ず確認する: 「このドキュメントの想定読者は誰ですか？（例: 自分用メモ / チームメンバー / 外部発表）」
   - 読者に応じて粒度・用語の説明レベルを調整する

2. **テーマの特定**
   - $ARGUMENTS にテーマがあればそれを使用
   - なければ現在のコンテキスト（会話内容）からテーマを推測
   - 推測できなければ会話ターンで確認する

3. **入力ソースの判定**
   以下の3パターンから判定する:
   - **(a) 現在のコンテキスト**: 会話中の議論・調査結果をまとめる場合
   - **(b) 既存ファイル**: 過去のメモ・レポートを統合する場合（ファイルパスを $ARGUMENTS または会話ターンで取得し、`shell` の `cat` / `rg` で読み込む）
   - **(c) Web 調査**: テーマ指定で Web 調査してドキュメント化する場合
     - Codex CLI で利用可能な Web 取得手段があればそれを使う。標準の Web 取得ツールが無い環境では (c) Web 調査は成立しないため、(a) コンテキスト / (b) 既存ファイル / 手動入力へ降格する（降格時は使用したソースをレポートに明記）
     - Web 調査の深さは文脈判断:
       - 「調べて」「まとめて」→ ライト調査（主要な情報源を数件）
       - 「徹底的に調べて」「深く調査して」→ ディープ調査（複数情報源を網羅的に）
     - **Web 調査手段が無い / 失敗した場合**: ユーザーに通知し、手動入力への切替を提案する

4. **テンプレート自動選択**
   内容に応じて以下から自動選択する:
   - **テックノート**: 技術的な知見・手順・解説 → [references/tech-note-template.md](references/tech-note-template.md)
   - **ADR (Architecture Decision Record)**: 意思決定の記録 → [references/adr-template.md](references/adr-template.md)
   - **ディスカッションサマリー**: 議論のまとめ → [references/discussion-summary-template.md](references/discussion-summary-template.md)
   - テンプレート選択が曖昧な場合は会話ターンでユーザーに確認する

### Phase 2: ドキュメント生成

1. テンプレートを `shell` の `cat` で読み込む
2. 入力ソースから情報を収集・整理する
3. 以下のルールに従ってドキュメントを生成:
   - 想定読者に応じた粒度で記述
   - 適切な箇所に Mermaid 図を挿入（[references/mermaid-guidelines.md](references/mermaid-guidelines.md) に従う）
   - Mermaid 図は必須ではない — 図が有効な場合のみ挿入する
   - frontmatter にメタデータを埋め込む（title, audience, template, created, updated）
4. slug を生成: `yyyymmddhhmmss_{kebab-title}`（`shell` で `date +%Y%m%d%H%M%S`）
5. 出力先: `docs/writings/{slug}.md`（apply_patch で生成）
   - `docs/writings/` ディレクトリがなければ `shell` の `mkdir -p` で作成

### Phase 3: フィードバックループ

1. 生成したドキュメントの概要を表示:
   ```
   📄 ドキュメントを生成しました: docs/writings/{slug}.md

   ## 構成
   {見出し一覧}

   修正・追加したい点はありますか？（「OK」で確定）
   ```
2. 会話ターンでフィードバックを受ける
3. フィードバックがあれば apply_patch で修正して再度確認（ループ）
4. 「OK」「問題ない」「大丈夫」等でループ終了
5. 完了メッセージ:
   ```
   ✅ ドキュメントを保存しました!
   📄 File: docs/writings/{slug}.md
   ```

### エラーハンドリング

- **空入力**: 会話ターンで再入力を要求
- **Web 調査失敗 / 手段なし**: ユーザーに通知し、手動での情報入力に切替を提案
- **テンプレート選択曖昧**: 会話ターンで確認

---

## Resume Workflow（既存ドキュメントの再編集）

### Steps

1. `resume` キーワード以降の $ARGUMENTS から対象を特定
   - ファイルパス指定: そのファイルを `shell` の `cat` で読み込む
   - slug 指定: `docs/writings/{slug}.md` を読み込む
   - 指定なし: `docs/writings/` のファイル一覧（`shell` の `ls`）を表示し、会話ターンで選択してもらう
   - `docs/writings/` が存在しない、またはファイルがない場合: 「まだドキュメントがありません」と表示して終了
   - 指定されたファイルが存在しない場合: `docs/writings/` のファイル一覧を表示してエラー終了

2. ファイルの frontmatter からメタデータを読み取る（audience, template 等）

3. ドキュメントの内容を要約して表示:
   ```
   📄 ドキュメント "{title}" を読み込みました。
   👥 想定読者: {audience}
   📝 テンプレート: {template}

   何を修正・追加しますか？
   ```

4. 会話ターンでユーザーの修正指示を受ける

5. 指示に基づいてドキュメントを apply_patch で修正
   - frontmatter の `updated` を今日の日付に更新
   - 必要に応じて Mermaid 図の追加・修正（ガイドラインに従う）

6. フィードバックループ（Write Workflow の Phase 3 と同じ）

---

## File Structure (generated in the project using this skill)

```
docs/writings/
  yyyymmddhhmmss_{slug}.md  - 個別ドキュメント
```

## Templates

- **テックノート:** [references/tech-note-template.md](references/tech-note-template.md)
- **ADR:** [references/adr-template.md](references/adr-template.md)
- **ディスカッションサマリー:** [references/discussion-summary-template.md](references/discussion-summary-template.md)

## Mermaid 図ガイドライン

- [references/mermaid-guidelines.md](references/mermaid-guidelines.md)

## Notes

- テンプレートは 3 型で開始し、必要に応じて追加する
- Mermaid ガイドラインは最低限で開始し、使いながら育てる方針
- investigate の出力を入力ソースとして使える
- frontmatter がドキュメントのメタデータを保持する（想定読者、テンプレート型、更新日）
