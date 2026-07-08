---
name: handoff
description: セッション間でコンテキストを引き継ぐためのスキル。コンテキストが圧迫されてきた時に save で現在の会話状態を LLM ファーストな構造化テキストとして docs/handoff/ に保存し、次セッションで restore で読み込んで作業を継続する。引数で動作モードを切り替え: `save`（デフォルト）/ `restore [path]` / `list`。「handoff」「引き継ぎ」「次セッションに移動」「コンテキスト圧迫」「セッション切り替え」で起動。
---

# Handoff — Session Context Relay (Codex Edition)

コンテキスト圧迫時に、次セッションへ作業状態を LLM ファーストに引き継ぐためのスキル。

## Codex CLI ツールの使い分け

- **shell** — `git status`, `ls`, `cat`, `date`, `mkdir`, `rm` など読み書き系コマンド
- **apply_patch** — handoff ファイルの新規作成
- **codex_file_search** — `docs/handoff/` 配下の検索（一覧取得）
- **send_message** — ユーザーへの報告

ユーザー確認は行わない（headless 実行）。save / restore は一発で完走する。

## Workflows

引数（`$ARGUMENTS`）で動作モードが決まる:

| 引数 | モード | 動作 |
|---|---|---|
| `save` または空 | Save | 現セッションを `docs/handoff/` に保存 |
| `restore` | Restore (latest) | 最新 mtime の handoff を読み込み → 即削除 |
| `restore <path>` | Restore (specific) | パス指定で復元 → 削除 |
| `list` | List | 既存 handoff の一覧表示 |

## Save Workflow

### Phase 1: Sanity Check

```bash
# shell で並列実行
test -d docs/handoff || mkdir -p docs/handoff
git status --short 2>/dev/null
git branch --show-current 2>/dev/null
date '+%Y%m%d_%H%M%S'
date -Iseconds
```

- git リポジトリでない / ブランチ取得に失敗した場合は frontmatter の `branch` に `(none)` を設定。**エラーで中断しない**
- `docs/handoff/` が無ければ作成

### Phase 2: Context Extraction

現在のセッションを振り返り、以下を漏れなく抽出する。**ユーザーへの質問はしない** — 会話履歴から自律的に書き起こす。

抽出観点:

1. **そもそもの目的** — ユーザーが何を達成したかったか
2. **これまでの流れ** — 主要な意思決定・試したこと・却下した案
3. **現在の状態** — 何がどこまで終わっていて、何が途中なのか
4. **関連ファイル** — 読んだ/編集したファイルの絶対パスと役割
5. **決定事項・制約** — ユーザーの指示・好み・採用した方針（feedback 系も含む）
6. **未解決の課題** — 残タスク、疑問点、ブロッカー
7. **次のアクション** — 次セッション冒頭で何をすべきか（具体的に）
8. **注意点** — ハマりポイント、やってはいけないこと

### Phase 3: File Write

ファイル名: `docs/handoff/{YYYYMMDD_HHMMSS}_{slug}.md`

- slug は作業内容を表す 3-5 単語の kebab-case（例: `handoff-skill-creation`, `auth-refactor-debug`）
- タイムスタンプは `date +%Y%m%d_%H%M%S` の出力を使用
- ファイル作成は **`apply_patch` ツールで実行**（`shell` の `cat <<EOF` や `tee` は使わない — Codex のポリシー上 apply_patch が正規ルート）

`status` は以下 3 値から厳密に選ぶ:
- `in-progress` — 作業継続中（一時中断含む、進捗があれば全て）
- `blocked` — 外部要因で進行不能（他者の回答待ち、本番データ不足など）
- `reviewing` — 実装は一段落し、レビュー・検証フェーズ

迷ったら `in-progress`。新しい値は追加しない。

テンプレート:

```markdown
---
created: {ISO8601}
branch: {current-branch}
status: {in-progress | blocked | reviewing}
---

# Handoff: {一行サマリ}

## TL;DR
{3-5 行。次セッションの Codex が最初に読む部分。目的と現在地を一発で掴ませる}

## 目的 / Why
{ユーザーが達成したいゴールと、その背景}

## これまでの流れ
- {時系列の主要イベント}
- {決定事項と却下した案 + なぜ}

## 現在の状態
### 完了
- {done items}
### 進行中
- {in-progress with 具体的にどこまで}
### 未着手
- {todo}

## 関連ファイル
- `/home/user/projects/myapp/src/auth.ts` — {役割・なぜ関連するか}  # 必ず絶対パス（`/` 始まり）。`src/auth.ts` のような相対パスは NG

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

`send_message` で保存先パスと復元方法を 1 ブロックで報告:

```
保存したよ: docs/handoff/{filename}
次セッションで `$handoff restore` 叩けばそのまま続きからいけるよ！
```

## Restore Workflow

### Phase 1: File Discovery

- 引数でパスが指定されていればそれを使う
- なければ `codex_file_search` または `shell ls -t docs/handoff/*.md | head -1` で最新（mtime 降順）のファイルを選ぶ
- mtime が同一で順序が決まらない場合は、ファイル名先頭のタイムスタンプ（`YYYYMMDD_HHMMSS`）の降順をタイブレークとして使う
- 該当ファイルがなければ「handoff ファイルが見つからないよ」と送信して終了（削除も何もしない）

### Phase 2: Load & Internalize

1. 対象ファイルを `shell cat` で読み込む
2. 内容を咀嚼して、ユーザーに**短いサマリ**を提示する。フォーマットは以下の Markdown 固定:

```markdown
## 引き継ぎ内容
- 目的: {1 行}
- 現在地: {branch / status / どこまで進んだか 1-2 行}
- 次のアクション:
  1. {1 行}
  2. {1 行}
  3. {1 行（最大 3 つまで、少なくて OK）}
```

3. ユーザーが即座に作業再開できる状態にする。余計な装飾・注意点の再掲はしない（必要なら元ファイルを参照）

### Phase 3: Cleanup

**自動削除**: 復元が成功したら即座に `shell rm docs/handoff/{filename}` を実行する。ユーザーへの確認は不要。

削除後、「引き継ぎ完了！`{basename}` は削除したよ」と一行報告する。
- `{basename}` はファイル名のみ（例: `20260421_230133_search-api.md`）。フルパスは使わない

`rm` が失敗した場合は理由を 1 行報告して終了（復元自体は成功しているのでロールバックは不要）。

## List Workflow

`docs/handoff/` 配下のファイルを mtime 降順（最新が上）で一覧表示する。mtime が同一で順序が決まらない場合は、ファイル名先頭のタイムスタンプ（`YYYYMMDD_HHMMSS`）の降順をタイブレークとして使う。

```bash
# shell で取得
ls -t docs/handoff/*.md 2>/dev/null
```

各ファイルを `shell cat`（または `head -30`）で読み、frontmatter と TL;DR の 1 行目を抽出。`send_message` で以下のフォーマットで提示:

```markdown
## Handoff 一覧（{件数} 件）

1. **`{filename}`** ({YYYY-MM-DD HH:MM})
   - status: `{status}`
   - TL;DR: {TL;DR 1 行目}
2. **`{filename}`** (...)
   - ...
```

抽出ルール:
- `{TL;DR 1 行目}` = frontmatter 後の `## TL;DR` セクションの **最初の非空行**（Markdown の行単位で 1 行目。句読点で区切らない）。**原文そのまま転記**（句読点・記号を削らない、末尾 `。` も保持）
- `{YYYY-MM-DD HH:MM}` はファイルの mtime。`ls -lt --time-style='+%Y-%m-%d %H:%M'` などで取得。タイムゾーン表記は付けない、年はファイル名の先頭 4 桁から取る
- 対象ファイルが 0 件なら「handoff ファイルはまだないよ」と一行報告して終了
- 末尾に restore 方法の案内行は**付けない**（ユーザーが聞かれたら答える方針）

## Prohibited Actions

- **ユーザーへの確認プロンプト** — save / restore / list 全て headless で完走
- **`apply_patch` 以外でのファイル作成** — `shell` の `tee` / `cat <<EOF > file` / リダイレクトは使わない
- **handoff ファイル以外の編集** — save / restore / list のいずれも `docs/handoff/` 配下以外のファイルを書き換えない
- **`docs/handoff/` 配下の勝手な一括削除** — restore ワークフロー以外で `rm` を叩かない

## Design Principles

- **LLM ファースト**: 人間向けのナラティブより、次 Codex が最小読解で作業再開できる構造化情報を優先
- **自律抽出**: save 時にユーザーに質問しない。会話履歴から書き起こす
- **使い捨て**: restore したら即削除。`docs/handoff/` にゴミを残さない
- **絶対パス**: ファイル参照は絶対パスで。次セッションの CWD を仮定しない
