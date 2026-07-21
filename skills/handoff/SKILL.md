---
name: handoff
description: セッション間でコンテキストを引き継ぐためのスキル。コンテキストが圧迫されてきた時に save で現在の会話状態をLLMファーストな構造化テキストとして .agents/artifacts/handoff/ に保存し、次セッションで restore で読み込んで作業を継続する。引数で動作モードを切り替え。`save`（デフォルト）/ `restore [path]` / `list`。「handoff」「引き継ぎ」「次セッションに移動」「コンテキスト圧迫」「セッション切り替え」「/clear 前に保存」で起動。
---

# Handoff — Session Context Relay

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

コンテキスト圧迫時に、次セッションへ作業状態を LLM ファーストに引き継ぐためのスキル。

## Workflows

引数で動作モードが決まる：

- `save` (デフォルト) — 現在のコンテキストをダンプして `.agents/artifacts/handoff/` に保存
- `restore` — 最新の handoff ファイルを読み込み、読み終わったら削除
- `restore <path>` — パス指定で復元
- `list` — 既存の handoff ファイル一覧

## Save Workflow

### Phase 1: Sanity Check

1. `.agents/artifacts/handoff/` が存在しなければ作成する
2. 現在のブランチ・git status をサッと把握（`git status --short`, `git branch --show-current`）
   - git リポジトリでない / ブランチ取得に失敗した場合は frontmatter の `branch` に `(none)` を設定。エラーで中断しない

3. **Execution-state checkpoint（dirty のまま終わるときの主トリガー）**

   handoff save は checkpoint 書き出しの**主トリガー**である。共有契約
   [../shared/references/checkpoint-pattern.md](../shared/references/checkpoint-pattern.md)
   に従い、以下を判定する:

   - `.agents/artifacts/status.md` の Current Session に **active plan（cycle_id）** があり、かつ
     `git status --porcelain=v1` が**非空**なら、checkpoint 骨格を生成する:
     `python3 {checkpoint.py のパス} skeleton --repo {プロジェクトルート} --cycle-id {cycle_id} --owner manual-session --written-at $(date -Iseconds) --output`
     （パスと `--repo` の書き方は契約「CLI 呼び出し規約」— 本リポジトリでは
     `skills/shared/scripts/checkpoint.py` + `--repo .`）
   - **実行タイミング**: 判定（active plan + dirty）は Phase 1 で行うが、skeleton の実行と叙述埋めは
     **Phase 3 の handoff ファイル書き出しが終わった後**に行う — checkpoint 生成は**セッション最後の
     書き込み**にする。生成後にファイル（handoff 本体を含む）を書くと fingerprint が即 stale になる
     （checkpoints/ 配下だけが除外対象）。
   - 骨格生成後、叙述だけを埋める（`## decision` 逸脱判断 1 文 / `## next` 次の一手 1 個 /
     `## evidence` は観測コマンド + タイムスタンプ必須）。機械フィールドは手で書かない。
   - active plan がない / clean（porcelain 空）なら checkpoint は**書かない**。
   - checkpoint と handoff は独立（境界表は契約参照）。checkpoint はここで削除・上書き競合時は
     契約どおり conflict 扱い（自分が読んだ時点と written_at / fingerprint が違えば上書きせず人間照会）。
   - これは handoff ファイル本体の保存（Phase 2〜3）とは別処理。両方行ってよい。

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

ファイル名: `.agents/artifacts/handoff/{YYYYMMDD_HHMMSS}_{slug}.md`

- slug は作業内容を表す 3-5 単語の kebab-case（例: `handoff-skill-creation`, `auth-refactor-debug`）
- タイムスタンプは `date +%Y%m%d_%H%M%S` で取得

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

保存先パスの前に、[ヒューマンリーダブル要約契約](../shared/references/human-readable-summary.md) に従う
要約ブロックを summary-first で置く。「ゴール / 現在地 / 次の一手」を各 1 行のかみ砕いた言葉で述べる
（次セッション復元の質に直結するため要約価値が最も高い）。埋められない項目は「未決定」と明示し、
機密値は要約に含めない（handoff-save 既存の機密規約に従属し、省略またはカテゴリ名に置換）：

```
📝 つまり:
   ゴール: {何を目指しているか — 1 行}
   現在地: {今どこまで進んだか — 1 行}
   次の一手: {次セッションで最初にやること — 1 行}

保存したよ: .agents/artifacts/handoff/{filename}
次セッションで `/handoff-restore` 叩けばそのまま続きからいけるよ！
```

## Restore Workflow

### Phase 1: File Discovery

- 引数でパスが指定されていればそれを使う
- なければ `.agents/artifacts/handoff/` 配下で最新（mtime 降順）のファイルを選ぶ
  - mtime が同一で順序が決まらない場合は、ファイル名先頭のタイムスタンプ（`YYYYMMDD_HHMMSS`）の降順をタイブレークとして使う
- 該当ファイルがなければ、**終了する前に execution-state checkpoint fallback を試みる**（下記）

#### Checkpoint fallback（handoff ファイルが 0 件のときのみ）

handoff ファイルが 1 件でも在る場合の挙動は**不変**（この fallback は走らせない）。0 件のときだけ:

共有契約 [../shared/references/checkpoint-pattern.md](../shared/references/checkpoint-pattern.md)
に従う。ここでは checkpoint が**唯一の情報源**なので、呼び出し側非対称により
`conflict` は人間照会で**停止**する（plan resume の「無視して続行」とは異なる）:

- `.agents/artifacts/status.md` の Current Session に active plan（cycle_id）があり、かつ
  `.agents/artifacts/plans/checkpoints/{cycle_id}.md` が存在すれば、
  `python3 {checkpoint.py のパス} classify --repo {プロジェクトルート} --file .agents/artifacts/plans/checkpoints/{cycle_id}.md`
  を実行し、verdict で分岐する（パスと `--repo` の書き方は契約「CLI 呼び出し規約」— 本リポジトリでは
  `skills/shared/scripts/checkpoint.py` + `--repo .`）:
  - `valid` / `stale` / `degraded`: checkpoint の叙述を提示して復元起点にする
    （`evidence` は historical ラベル、`verify_on_restore` は表示のみ・自動実行しない）。
  - `superseded`: HEAD 前進済み。削除を**提案**（自動削除しない）。classify 出力に `dirty_overlap:`
    行があれば併記（行が無ければ重なりなし）。叙述（decision / next）は「履歴・参考」ラベルで
    提示してよい（コミットが正である旨を明示した上で、文脈を黙って捨てない）。
  - `conflict`（parse / semantic）: **人間照会で停止**（自動判断しない）。
- **fallback 時の提示フォーマット**: Phase 2 の固定テンプレート（handoff ファイル向け）に拘束されない。
  「checkpoint 由来である旨 + verdict + 次のアクション」を先頭に置いた簡潔な構成でよい。
- checkpoint は fallback で読んでも**削除しない**（handoff の読了後削除セマンティクスを波及させない）。
- active plan も checkpoint もなければ「handoff ファイルが見つからないよ」と報告して終了。

### Phase 2: Load & Internalize

1. ファイルを読み込む
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

**自動削除**：復元が成功したら即座に該当ファイルを削除する（`rm` コマンド）。ユーザーへの確認は不要。

削除後、「引き継ぎ完了！`{basename}` は削除したよ」と一行報告する。
- `{basename}` はファイル名のみ（例: `20260421_230133_search-api.md`）。フルパスは使わない

## List Workflow

`.agents/artifacts/handoff/` 配下のファイルを mtime 降順（最新が上）で一覧表示する。mtime が同一で順序が決まらない場合は、ファイル名先頭のタイムスタンプ（`YYYYMMDD_HHMMSS`）の降順をタイブレークとして使う。フォーマットは以下の番号付き Markdown リスト固定:

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
- `{YYYY-MM-DD HH:MM}` はファイルの mtime。`ls -lt` のローカルタイム表示を `YYYY-MM-DD HH:MM` に整形する（タイムゾーン表記は付けない、年はファイル名の先頭 4 桁から取る）
- 対象ファイルが 0 件なら「handoff ファイルはまだないよ」と一行報告して終了
- 末尾に restore 方法の案内行は**付けない**（ユーザーが聞かれたら答える方針）

## Design Principles

- **LLM ファースト**: 人間向けのナラティブより、次 Claude が最小読解で作業再開できる構造化情報を優先
- **自律抽出**: save 時にユーザーに質問しない。会話履歴から書き起こす
- **使い捨て**: restore したら即削除。.agents/artifacts/handoff/ にゴミを残さない
- **絶対パス**: ファイル参照は絶対パスで。次セッションの CWD を仮定しない
