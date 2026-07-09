# AGENTS.md

This file is the shared project instruction source for Claude Code, Codex CLI, and other agents.
`CLAUDE.md` must stay a thin wrapper that imports this file with `@AGENTS.md`.

## プロジェクト概要

このリポジトリは Agent Skills 標準に準拠したスキル集である。
実装計画の作成、レビュー、自動実装、コミット、調査、セキュリティレビュー、デザイン検証、TDD、issue 自走ループなどをスキルとして提供する。

スキル本文はプラットフォーム非依存の自然言語で記述し、Claude Code / Codex CLI / Cursor / Gemini CLI など複数のエージェント環境で読める状態を保つ。

## 主要構成

- `skills/` — スキル本体。各スキルは `SKILL.md` を持ち、必要に応じて `references/` や `scripts/` を含む
- `skills/shared/` — 複数スキルが参照する共有契約、参照資料、共通スクリプト
- `commands/` — スラッシュコマンド。スキルを呼び出す薄いラッパーで、ロジックはスキル側に集約する
- `rules/` — 常駐ルールとして使える補助指示
- `scripts/` — リポジトリ整合性バリデータなどの開発用スクリプト
- `.claude-plugin/` / `.codex-plugin/` — 各プラットフォーム向け plugin manifest

## スキル運用

- ユーザーがスキル名を明示した場合は、そのスキルの `SKILL.md` を読んでから作業する。
- 新規スキルは skills-first を基本とし、command は追加しない。command を追加するのは、multi-workflow スキルの名前付き入口が必要な場合に限る。
- command は薄い入口に留め、判断・手順・契約は `skills/<name>/SKILL.md` または `references/` に置く。
- 主要スキルの一覧と用途は `README.md` を参照する。常時ロードされるこのファイルへ詳細なスキルカタログを複製しない。

## 編集ルール

- `SKILL.md` と `references/` では、特定プラットフォームのツール API 名やモデル名に依存しない表現を使う。
  - NG: 固有のツール API 名、固有のモデル名、特定 CLI だけで通じる呼び出し形式
  - OK: 「シェルコマンドを実行する」「ファイルを読む」「ファイルを編集する」「サブエージェントに委譲する」「高性能モデル」
- 共有契約の語彙（例: `AUTO_FIX` / `NEEDS_JUDGMENT` / `REPORT_ONLY`, `CONFIRMED` / `FALSE_POSITIVE` / `UNCERTAIN`）を使う場合は、該当する `skills/shared/references/` の契約へ md リンクを張る。
- スキル内リンクは相対 md リンクを使い、ファイル移動時は参照も更新する。
- スキルを追加・削除・改名したら `README.md` と必要な plugin manifest を更新する。常時指示の詳細化で解決せず、機械検証やスキル本文を正本にする。
- `CLAUDE.md` へ直接プロジェクト指示を追加しない。共通指示が必要ならこの `AGENTS.md` を更新する。

## 検証

編集後は次を実行する。

```bash
python3 scripts/validate_repo.py
```

この validator は symlink、frontmatter、相対リンク、README のスキル名カバレッジ、plugin version 同期、description 品質、共有契約語彙、dossier lint を検証する。CI でも同じチェックが走る。
