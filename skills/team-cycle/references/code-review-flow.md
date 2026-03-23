# Code Review Flow

実装後のコードレビューフロー。計画レビューより軽量な構成。

## 概要

2名のレビュワー（Security + Architect）が独立して実装コードをレビューし、問題を検出する。

```
Step 1: 独立レビュー（並行） → Security と Architect が各自の観点からレビュー
Step 2: 論点整理（Lead）     → 報告を統合し、問題を整理する
Step 3: 合意形成（Lead）     → 判定を下し、必要なら修正指示を出す
```

> **注意**: 計画レビューと異なり、議論ラウンドは最大1回。コードレビューはメンバー間議論より独立検証が重要。

## Step 1: 独立レビュー（並行）

### 目的

Security と Architect が独立して実装コードを分析し、各自の専門観点から問題を洗い出す。

### レビュー対象

`git diff {base_commit}..HEAD` の変更差分のみ。

- `base_commit` は Phase 2 実装開始直前に `git rev-parse HEAD` でキャプチャしておく
- diff が 500 行を超える場合はファイル単位で分割して各 Agent に配分する

### 手順

1. 2名のレビュワーを **並行で** Agent spawn する
2. 各レビュワーに以下を渡す:
   - `git diff {base_commit}..HEAD` の出力
   - CLAUDE.md の内容
   - [team-config.md](../../shared/references/team-config.md) に定義されたコードレビュー用プロンプト
3. 各レビュワーは SendMessage で Lead に報告を送る

### Agent プロンプトテンプレート

```
あなたは {role_name} としてコードレビューに参加しています。
チーム名: {team_name}

{code_review_prompt_from_team_config}

## レビュー対象（git diff）
{diff_content}

## プロジェクトルール (CLAUDE.md)
{claude_md_content}

レビューが完了したら、SendMessage ツールを使って Lead（team_name: {team_name}、recipient: "lead"）に結果を報告してください。
```

## Step 2: 論点整理（Lead）

### 目的

各レビュワーの報告を統合し、問題を整理する。

### 手順

1. 全レビュワーからの SendMessage を受け取る
2. 報告を以下に分類する:

| カテゴリ | 説明 | 処理 |
|----------|------|------|
| **共通問題** | 両レビュワーが指摘した同一の問題 | 高優先度で対応 |
| **個別問題** | 片方のレビュワーのみの指摘 | 重大度に応じて対応 |

## Step 3: 合意形成と判定（Lead）

### 目的

レビュー結果を踏まえて判定を下す。

### 判定

判定基準の詳細は [severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md) の「コードレビュー判定」を参照。

| 判定 | 条件 | アクション |
|------|------|-----------|
| PASS | 問題なし、または INFO のみ | 続行 |
| PASS WITH NOTES | WARN レベルの指摘あり | 指摘を記録して続行 |
| NEEDS FIX | BLOCK レベルの問題あり | 修正 → 再レビュー |

### NEEDS FIX 時の処理

1. **通常モード**: 修正指示を Agent に渡して再実装 → 再レビュー（最大1回リトライ）
2. **headless モード**: ユーザーにレビュー結果を出力し処理を中断

### 再レビュー

- 最大1回のリトライ。2回目の NEEDS FIX では Lead が最終判断を下す
- 再レビューは修正差分のみ対象（全体の再レビューは不要）

## エラーケース

### レビュワー spawn 失敗

- 1名でも成功すれば続行（2名中1名）
- 全員失敗した場合はコードレビューをスキップし、警告を出力

### レビュワーからの報告がない

- 報告がないレビュワーは除外
- 1名以上の報告があれば続行
