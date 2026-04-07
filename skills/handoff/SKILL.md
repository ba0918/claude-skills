---
name: handoff
description: セッション間でコンテキストを引き継ぐためのスキル。コンテキストが圧迫されてきた時に save で現在の会話状態をLLMファーストな構造化テキストとして docs/handoff/ に保存し、次セッションで restore で読み込んで作業を継続する。「handoff」「引き継ぎ」「次セッションに移動」「コンテキスト圧迫」「セッション切り替え」「/clear 前に保存」で起動。
---

# Handoff — Session Context Relay

コンテキスト圧迫時に、次セッションへ作業状態を LLM ファーストに引き継ぐためのスキル。

## Workflows

引数で動作モードが決まる：

- `save` (デフォルト) — 現在のコンテキストをダンプして `docs/handoff/` に保存
- `restore` — 最新の handoff ファイルを読み込み、読み終わったら削除
- `restore <path>` — パス指定で復元
- `list` — 既存の handoff ファイル一覧

## Save Workflow

### Phase 1: Sanity Check

1. `docs/handoff/` が存在しなければ作成する
2. 現在のブランチ・git status をサッと把握（`git status --short`, `git branch --show-current`）

### Phase 2: Context Extraction

現在のセッションを振り返り、以下を漏れなく抽出する。ユーザーへの質問はしない — 会話履歴から自律的に書き起こすこと。

抽出観点：

1. **そもそもの目的** — ユーザーが何を達成したかったか
2. **これまでの流れ** — 主要な意思決定・試したこと・却下した案
3. **現在の状態** — 何がどこまで終わっていて、何が途中なのか
4. **関連ファイル** — 読んだ/編集したファイルの絶対パスと役割
5. **決定事項・制約** — ユーザーの指示・好み・採用した方針（feedback系も含む）
6. **未解決の課題** — 残タスク、疑問点、ブロッカー
7. **次のアクション** — 次セッション冒頭で何をすべきか（具体的に）
8. **注意点** — ハマりポイント、やってはいけないこと

### Phase 3: File Write

ファイル名: `docs/handoff/{YYYYMMDD_HHMMSS}_{slug}.md`

- slug は作業内容を表す 3-5 単語の kebab-case（例: `handoff-skill-creation`, `auth-refactor-debug`）
- タイムスタンプは `date +%Y%m%d_%H%M%S` で取得

テンプレート:

```markdown
---
created: {ISO8601}
branch: {current-branch}
status: {in-progress | blocked | reviewing}
---

# Handoff: {一行サマリ}

## TL;DR
{3-5行。次セッションの Claude が最初に読む部分。目的と現在地を一発で掴ませる}

## 目的 / Why
{ユーザーが達成したいゴールと、その背景}

## これまでの流れ
- {時系列の主要イベント}
- {決定事項と却下した案 + なぜ}

## 現在の状態
### 完了
- {done items}
### 進行中
- {in-progress with具体的にどこまで}
### 未着手
- {todo}

## 関連ファイル
- `absolute/path/to/file.md` — {役割・なぜ関連するか}

## 決定事項 / 制約
- {ユーザーの指示・好み・採用方針}

## 未解決の課題
- {open questions, blockers}

## 次のアクション
1. {具体的なステップ}
2. {...}

## 注意点
- {ハマりポイント、やってはいけないこと}
```

### Phase 4: Report

保存先パスをユーザーに表示し、次セッションでの復元方法を案内：

```
保存したよ: docs/handoff/{filename}
次セッションで `/handoff-restore` 叩けばそのまま続きからいけるよ！
```

## Restore Workflow

### Phase 1: File Discovery

- 引数でパスが指定されていればそれを使う
- なければ `docs/handoff/` 配下で最新（mtime 降順）のファイルを選ぶ
- 該当ファイルがなければ「handoff ファイルが見つからないよ」と報告して終了

### Phase 2: Load & Internalize

1. ファイルを Read で読み込む
2. 内容を咀嚼して、ユーザーに**短いサマリ**を提示する：
   - 何を引き継いだか（目的・現在地）
   - 次のアクション（3点以内）
3. ユーザーが即座に作業再開できる状態にする

### Phase 3: Cleanup

**自動削除**：復元が成功したら即座に該当ファイルを削除する（Bash `rm`）。ユーザーへの確認は不要。

削除後、「引き継ぎ完了！`{filename}` は削除したよ」と一行報告する。

## List Workflow

`docs/handoff/` 配下のファイルを mtime 降順で一覧表示。各ファイルの frontmatter から `status` と `TL;DR` の1行目を抜き出して併記。

## Design Principles

- **LLM ファースト**: 人間向けのナラティブより、次 Claude が最小読解で作業再開できる構造化情報を優先
- **自律抽出**: save 時にユーザーに質問しない。会話履歴から書き起こす
- **使い捨て**: restore したら即削除。docs/handoff/ にゴミを残さない
- **絶対パス**: ファイル参照は絶対パスで。次セッションの CWD を仮定しない
