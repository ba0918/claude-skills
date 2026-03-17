# Brainstorm Skill

**Cycle ID:** `20260317161207`
**Started:** 2026-03-17 16:12:07
**Status:** 🟡 Planning

---

## What & Why

アイデアの壁打ちに特化したスキルを新規作成する。現在のスキルセットは「何を作るか決まった後」のフローは強いが、「何を作るか考える」フェーズが欠けている。brainstorm スキルで発散→収束→plan化の導線を整備し、アイデア段階から plan までシームレスに繋げる。

## Goals

- ひたすら議論だけを行い、LLMが勝手に実装に走らない壁打ちセッションを提供する
- 壁打ちの成果をメモファイルとして永続化し、後から参照できるようにする
- 収束したアイデアから plan-create へスムーズに接続するフローを構築する

## Design

### ファイル構成

```
skills/brainstorm/
  SKILL.md              - メインスキル定義
  references/
    idea-template.md    - アイデアメモのテンプレート

commands/
  brainstorm.md         - /brainstorm コマンド（新規セッション開始・対話ループ）
  brainstorm-wrap.md    - /brainstorm-wrap コマンド（壁打ちを整理してサマリー生成）
  brainstorm-list.md    - /brainstorm-list コマンド（過去のアイデア一覧）
  brainstorm-plan.md    - /brainstorm-plan コマンド（アイデアを plan に変換）

docs/ideas/             - 壁打ちメモの保存先（利用プロジェクト側に生成）
  idea-status.md        - アイデアインデックス
  {slug}.md             - 個別アイデアメモ
  archives/             - 完了・破棄したアイデアの保管先
```

### コマンド→スキルのマッピング

```
commands/brainstorm.md       →  skills/brainstorm/SKILL.md (session ワークフロー)
commands/brainstorm-wrap.md  →  skills/brainstorm/SKILL.md (wrap ワークフロー)
commands/brainstorm-list.md  →  skills/brainstorm/SKILL.md (list ワークフロー)
commands/brainstorm-plan.md  →  skills/brainstorm/SKILL.md (plan ワークフロー)
```

### 各コマンドファイルの定義

各コマンドは issue スキルと同様に Skill ツールへの薄いラッパー:

- **brainstorm.md**: `Skill ツールで brainstorm を実行する。引数: $ARGUMENTS`
- **brainstorm-wrap.md**: `Skill ツールで brainstorm を実行する。引数: wrap $ARGUMENTS`
- **brainstorm-list.md**: `Skill ツールで brainstorm を実行する。引数: list`
- **brainstorm-plan.md**: `Skill ツールで brainstorm を実行する。引数: plan $ARGUMENTS`

### Key Points

- **絶対的な制約: 議論中はファイル編集・コード生成を一切行わない**: investigate スキルと同様の強い制約として設計する。Edit/Write/NotebookEdit ツールの使用を禁止し、壁打ちに集中させる
- **issue スキルと同じパターン**: サブコマンド分割（brainstorm / brainstorm-wrap / brainstorm-list / brainstorm-plan）で issue の create/list/plan/close パターンを踏襲
- **skill-creator で作成**: 実際のスキル・コマンドファイル作成は skill-creator スキルに委譲する
- **AskUserQuestion による対話ループ**: 壁打ちフェーズでは AskUserQuestion を使ってユーザーとの対話を繰り返す

### スキル詳細設計

#### SKILL.md のワークフロー選択

```
$ARGUMENTS の先頭キーワード:
- (なし or テーマ文字列) → Session Workflow（壁打ちセッション）
- wrap   → Wrap Workflow（整理・サマリー生成）
- list   → List Workflow（一覧表示）
- plan   → Plan Workflow（plan に変換）
```

#### Session Workflow（壁打ちセッション）

**絶対的な制約:**
- Edit, Write, NotebookEdit ツールの使用禁止（investigate スキルと同じアプローチ）
- コード生成・実装提案禁止（擬似コードでの概念説明は可）
- 「じゃあ実装しますね」「コードを書きます」は絶対に言わない

**フロー:**
1. テーマを $ARGUMENTS から取得（なければ AskUserQuestion で聞く）
2. 壁打ち対話ループに入る:
   - ユーザーのアイデアに対して質問・深掘り・反論・別視点を提供
   - 必要に応じて既存のコードベースを Read/Grep で調査（読み取り専用）
   - AskUserQuestion で次の入力を求める
   - ユーザーが「wrap」「まとめて」「終わり」等と言ったらループ終了
3. ループ終了時に Wrap Workflow への誘導メッセージを表示

**壁打ち中の振る舞い:**
- 質問で深掘りする（Why? What if? How about?）
- 反論や懸念を率直に出す（「それだと〇〇が問題になりそう」）
- 別のアプローチを提案する（「こういう手もあるけど」）
- 過去の議論を要約して整理する（「ここまでの論点をまとめると」）
- 技術的実現可能性をコードベース調査で裏付ける（読み取り専用）

#### Wrap Workflow（整理・サマリー生成）

**前提チェック:**
- 現在の会話に壁打ちセッションの内容がない場合（単独で `/brainstorm-wrap` が呼ばれた場合）、「壁打ちセッションが見つかりません。先に `/brainstorm テーマ` で壁打ちを行ってください」と表示して終了

1. 現在の会話から壁打ちの内容を整理する
2. AskUserQuestion でタイトルとサマリーを確認
3. `docs/ideas/` ディレクトリを作成（なければ mkdir -p）
4. slug を生成: `YYYY-MM-DD_{kebab-title}`
5. idea-template.md をもとにメモファイルを生成: `docs/ideas/{slug}.md`
6. `docs/ideas/idea-status.md` を更新（なければ作成）
7. 完了メッセージ表示

**idea-template.md の構成:**
```markdown
# {Title}

**Created:** {YYYY-MM-DD}
**Status:** 💡 Idea
**Tags:** {tags}

---

## Summary

{1-3 sentence summary}

## Key Discussion Points

- {論点1}
- {論点2}
- ...

## Decisions & Conclusions

- {決定事項1}
- {決定事項2}

## Open Questions

- {未解決の疑問1}
- {未解決の疑問2}

## Next Steps

- {次のアクション}
```

#### List Workflow

1. `docs/ideas/idea-status.md` を読む（なければ「まだアイデアがありません」で終了）
2. テーブル内容をそのまま表示
3. 件数サマリーを表示

#### Plan Workflow

1. `docs/ideas/idea-status.md` を読む
2. AskUserQuestion で対象アイデアを選択
3. アイデアファイルを読み込む
4. Skill ツールで `plan-create` を実行（引数フォーマット: `{Title}: {Summary from idea file}` — plan-create は $ARGUMENTS をそのまま What & Why の種として使う）
5. アイデアの Status を `💡 Idea` → `📋 Planned` に更新
6. 完了メッセージ表示

### idea-status.md のフォーマット

```markdown
# Idea Status

**Last Updated:** YYYY-MM-DD

| Idea | Tags | Created | Status | Summary |
|------|------|---------|--------|---------|
| [slug](slug.md) | `tag` | YYYY-MM-DD | 💡 Idea | Summary |
```

### ステータスの種類

| ステータス | 意味 |
|-----------|------|
| 💡 Idea | 壁打ち済み、まだ plan 化していない |
| 📋 Planned | plan に変換済み |
| 🗑️ Dropped | 見送り・破棄 |

### アーカイブフロー

ステータスが `📋 Planned` または `🗑️ Dropped` に変更されたとき:
1. `docs/ideas/{slug}.md` を `docs/ideas/archives/{slug}.md` に移動
2. `idea-status.md` のテーブルからエントリを削除（または archives セクションに移動）

アーカイブの実行タイミング:
- **Plan Workflow**: ステータスを `📋 Planned` に更新した後に自動実行
- **手動 Drop**: ユーザーが `/brainstorm-list` でアイデア一覧を確認し、AskUserQuestion で破棄対象を選択 → ステータスを `🗑️ Dropped` に更新後に自動実行

## Tests

このスキルは .md ファイルのみで構成されるため、自動テストの対象外。手動で以下を確認する:

- [ ] `/brainstorm テーマ` で壁打ちセッションが開始される
- [ ] 壁打ち中に Edit/Write が呼ばれない
- [ ] 「まとめて」で wrap workflow に遷移する
- [ ] `/brainstorm-wrap` でメモファイルが正しく生成される
- [ ] `/brainstorm-list` でアイデア一覧が表示される
- [ ] `/brainstorm-plan` で plan-create に接続される
- [ ] idea-status.md が正しく更新される

## Security

- 壁打ち内容に機密情報が含まれる場合、メモファイルに書き出す前に AskUserQuestion で確認する
- docs/ideas/ は .gitignore 対象外（プロジェクトの判断に委ねる）

## Progress

| Step | Status |
|------|--------|
| SKILL.md 作成 | 🟢 |
| idea-template.md 作成 | ⚪ |
| brainstorm.md コマンド作成 | ⚪ |
| brainstorm-wrap.md コマンド作成 | ⚪ |
| brainstorm-list.md コマンド作成 | ⚪ |
| brainstorm-plan.md コマンド作成 | ⚪ |
| install.sh 更新 | ⚪ |
| CLAUDE.md 更新 | ⚪ |
| Commit | ⚪ |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Write tests → Implement → Commit with `commit`
