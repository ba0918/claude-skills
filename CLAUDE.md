# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Claude Code 用の自作スキル・コマンド集。実装計画の作成→レビュー→自動実装までのワークフローを提供する。
`install.sh` で `~/.claude/commands/` と `~/.claude/skills/` にシンボリックリンクを張ってインストールする。

## アーキテクチャ

### 2つのレイヤー

- **commands/** — スラッシュコマンド（`/plan-create` 等）。ユーザーが直接呼び出すエントリーポイント。各 `.md` ファイルが1つのコマンドに対応。
- **skills/** — スキル定義。各ディレクトリが `SKILL.md`（メインロジック）+ `references/`（テンプレート・チェックリスト等の参照資料）で構成される。

### コマンド→スキルの関係

コマンドは Skill ツール経由でスキルを呼び出す薄いラッパー。ロジックはスキル側に集約する。

```
commands/plan-create.md  →  skills/plan/SKILL.md
commands/plan-review.md  →  skills/plan-reviewer/SKILL.md
commands/plan-refine.md  →  skills/plan-reviewer/SKILL.md (ループ実行)
commands/plan-implement.md → skills/plan/SKILL.md
commands/cycle.md        →  plan-refine + plan-implement を Agent で連鎖実行
commands/commit.md       →  skills/commit/SKILL.md
commands/iterate.md      →  skills/iterate/SKILL.md
commands/doc-check.md    →  skills/doc-check/SKILL.md
```

### 主要スキル

| スキル | 役割 |
|--------|------|
| `plan` | 計画ファイル（`docs/cycles/{timestamp}_{slug}.md`）と `docs/status.md` の生成・管理 |
| `plan-reviewer` | 6観点並行レビュー（Feasibility / Security / Performance / Architecture / Completeness / Alternatives） |
| `codebase-review` | 4エージェント並行によるコードベース全体レビュー。結果はJSON→統合エージェントが集約 |
| `generate-review-rules` | プロジェクト固有の `.claude/review-rules.md` を自動生成 |
| `commit` | 変更を分析し論理単位で自動コミット（確認なし即実行） |
| `iterate` | cycle 後の追加指示をサイズ適応型の軽量改善ループで実行 |
| `doc-check` | ドキュメントとコードベースの整合性を検証・自動修正 |

### ワークフロー設計パターン

- **Agent 委譲**: `cycle` コマンドのように重い処理は Agent ツールに委譲し、メインコンテキストにはサマリーのみ保持する
- **ファイル経由の受け渡し**: `codebase-review` ではエージェント間のデータ受け渡しに `.claude/tmp/` 配下のJSONファイルを使い、コンテキストウィンドウを節約する
- **ヘッドレス対応**: `cycle` コマンドはユーザー確認プロンプトを出さずに全自動で動作する

## インストール・開発

```bash
./install.sh    # ~/.claude/ にシンボリックリンクを作成
```

変更後は `install.sh` の再実行は不要（シンボリックリンクなので即反映）。

## 編集時の注意

- スキルの `SKILL.md` 内で参照する `references/` のファイルは相対パスでリンクしている。パスを変更する場合はリンクも更新すること
- コマンドの frontmatter（`---` ブロック）の `description` フィールドがスキル一覧での表示に使われる
- `.skill` ファイルは `.gitignore` で除外されている（単体ファイル形式のスキルは使わない方針）
