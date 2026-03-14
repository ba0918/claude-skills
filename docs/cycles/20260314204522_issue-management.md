# Issue 管理スキル

**Cycle ID:** `20260314204522`
**Started:** 2026-03-14 20:45:22
**Status:** 🟢 Complete

---

## 📝 What & Why

plan 実行中に発見したスコープ外の問題を `docs/issues/` にローカルファイルとして記録し、後から plan → cycle に繋げるフローを構築する。現状は別件発見時に手動でメモ → 手動で plan 作成しており、発見→記録→計画化のパスが断絶している。

## 🎯 Goals

- plan 中に発見した別件を素早く issue として記録できるようにする
- 未解決 issue の一覧を `issue-status.md` で効率的に確認できるようにする
- issue から plan → cycle への導線を作る
- close した issue を自動アーカイブしてインデックスの肥大化を防ぐ

## 📐 Design

### ディレクトリ構成

```
skills/issue/
  SKILL.md                    - issue 管理のメインロジック（4つのワークフロー）
  references/
    issue-template.md         - 個別 issue ファイルのテンプレート

commands/
  issue-create.md             - issue 新規作成コマンド
  issue-list.md               - 未解決 issue 一覧コマンド
  issue-cycle.md              - issue → plan → cycle コマンド
  issue-close.md              - issue クローズ（アーカイブ）コマンド
```

### docs/issues/ 構成（スキル利用先プロジェクトに生成される）

```
docs/issues/
  issue-status.md             - インデックスファイル（LLM はまずこれを読む）
  YYYY-MM-DD_<slug>.md        - 個別 issue ファイル
  archives/                   - close 済み issue の保管場所
```

### Key Points

- **issue-status.md がインデックス**: LLM は全 issue を開かず、このファイルだけ読めば状況を把握できる。コンテキスト節約。
- **close = アーカイブ**: close したら即 `archives/` に移動 + `issue-status.md` から行削除。2つの概念を分けない。
- **plan スキルとの連携**: plan の SKILL.md に「スコープ外の問題は `/issue-create` で記録して続行」の指示を1行追加。
- **コマンドは薄いラッパー**: ロジックは SKILL.md に集約。既存パターンに従う。
- **4ワークフロー1ファイル集約の根拠**: 各ワークフローは短く（5-7ステップ）、共通のデータ構造（`issue-status.md`、issue ファイル）を操作する凝集度の高い機能群。スキルを分割すると `issue-status.md` のフォーマット定義が分散し、変更時の整合性維持が困難になる。SKILL.md 内でセクション見出しを使い、コマンドから呼び出し時に対象ワークフローを引数で指定する。

### issue-status.md のフォーマット

```markdown
# Issue Status

**Last Updated:** YYYY-MM-DD

| Issue | Tags | Created | Summary |
|-------|------|---------|---------|
| [slug](YYYY-MM-DD_slug.md) | `tag` | YYYY-MM-DD | 概要 |
```

### 個別 issue ファイルのフォーマット

```markdown
---
title: Issue のタイトル
status: open
created: YYYY-MM-DD
source: docs/cycles/xxxxx.md  # 発見元（任意）
---

## 概要

問題の説明

## 備考

補足情報
```

## 🔧 Implementation Steps

### Step 1: issue テンプレート作成

`skills/issue/references/issue-template.md` を作成。個別 issue ファイルの雛形。

**Files:**
- `skills/issue/references/issue-template.md` (新規)

### Step 2: SKILL.md 作成

`skills/issue/SKILL.md` を作成。4つのワークフロー（create / list / cycle / close）を定義。

**Files:**
- `skills/issue/SKILL.md` (新規)

**ワークフロー詳細:**

#### create ワークフロー
1. 引数からタイトルと概要を受け取る
2. `docs/issues/` ディレクトリを作成（なければ）
3. `issue-status.md` を作成（なければテンプレートから）
4. slug を生成（日付 + タイトルのケバブケース）
   - タイトルからスラッシュ(`/`)、ドット2連続(`..`)、バックスラッシュ等のパス区切り文字・特殊文字を除去してからケバブケース化する
5. issue ファイルをテンプレートから作成
6. `issue-status.md` にテーブル行を追加
7. 作成結果を表示

#### list ワークフロー
1. `docs/issues/issue-status.md` を読み込む（存在しない場合は「issue がまだ登録されていません」と表示して終了）
2. テーブル内容を表示
3. 件数サマリーを表示

#### cycle ワークフロー
1. `docs/issues/issue-status.md` を読み込む（存在しない場合は「issue がまだ登録されていません」と表示して終了）
2. AskUserQuestion で対象 issue を選択させる
3. 選択された issue ファイルを読み込む
4. issue 内容を基に `/plan-create` を Skill ツールで実行
5. 作成された plan で `/cycle` を Skill ツールで実行
6. `/plan-create` または `/cycle` が失敗した場合はエラー内容を表示し、issue は open のまま保持して終了
7. cycle 完了後、`/issue-close` を Skill ツールで実行

#### close ワークフロー
1. 引数で issue slug を受け取る（省略時は AskUserQuestion で確認）
2. issue ファイルの存在を確認（見つからない場合はエラーメッセージを表示して終了）
3. `docs/issues/archives/` ディレクトリを作成（なければ）
4. issue ファイルを `docs/issues/archives/` に移動（`mv` コマンド）
5. `issue-status.md` から該当行を削除（Edit ツール）
6. 結果を表示

### Step 3: コマンドファイル作成

4つのコマンドファイルを作成。既存コマンド（`commit.md` 等）のフォーマットに準拠。

**Files:**
- `commands/issue-create.md` (新規)
- `commands/issue-list.md` (新規)
- `commands/issue-cycle.md` (新規)
- `commands/issue-close.md` (新規)

### Step 4: plan スキルとの連携

`skills/plan/SKILL.md` に issue 記録の指示を追加。

**Files:**
- `skills/plan/SKILL.md` (既存・修正)

**変更内容:**
- Notes セクションに「調査中にスコープ外の問題を発見した場合、`/issue-create` で記録して plan を続行する」を追加

### Step 5: install.sh の確認

新規コマンド・スキルが `install.sh` のシンボリックリンク対象に含まれるか確認し、必要なら追加。

**Files:**
- `install.sh` (既存・確認/修正)

### Step 6: CLAUDE.md・README.md の更新

新しいスキルとコマンドをドキュメントに反映。

**Files:**
- `CLAUDE.md` (既存・修正)
- `README.md` (既存・修正)

## ✅ Tests

このプロジェクトはテストフレームワークを持たないため、手動検証を行う:

- [ ] `/issue-create` で issue ファイルと issue-status.md が正しく生成される
- [ ] `/issue-list` で issue-status.md の内容が表示される
- [ ] `/issue-close` で archives/ への移動と issue-status.md からの削除が行われる
- [ ] `/issue-cycle` で issue 選択 → plan → cycle の一連のフローが動作する
- [ ] `install.sh` 実行後にシンボリックリンクが正しく張られる

## 🔒 Security (if applicable)

- [ ] issue ファイルにセンシティブ情報が記録されないよう、テンプレートに注意書きを記載

## 📊 Progress

| Step | Description | Status |
|------|-------------|--------|
| 1 | issue テンプレート作成 | 🟢 |
| 2 | SKILL.md 作成 | 🟢 |
| 3 | コマンドファイル作成 | 🟢 |
| 4 | plan スキル連携 | 🟢 |
| 5 | install.sh 確認 | 🟢 |
| 6 | ドキュメント更新 | 🟢 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

## Phase 1 でやらないこと

- GitHub Issues 連動
- 優先度・ラベルの複雑な管理（Tags はフリーテキストのみ）
- issue 間の依存関係
- archives/ の検索コマンド（`/issue-archive`）

## 将来の拡張ポイント（Phase 2 以降）

- GitHub リポジトリ判定 → `gh issue create` 連動
- cycle 完了時の自動 close
- `/issue-archive` で過去 issue の検索・閲覧
- ラベルによるフィルタリング

---

**Next:** レビュー → 実装 → コミット 🚀
