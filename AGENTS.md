# AGENTS.md

This file provides guidance to Codex CLI when working with code in this repository.

## プロジェクト概要

Agent Skills 標準に準拠した自作スキル集。実装計画の作成→レビュー→自動実装までのワークフローを提供する。
Claude Code / Codex CLI / Cursor / Gemini CLI 等のプラットフォームで利用可能。
スキル本文はプラットフォーム非依存の自然言語で記述されており、特定 CLI のツール API 名に依存しない。

## アーキテクチャ

### ディレクトリ構造

- **skills/** — スキル定義（プラットフォーム共通）。各ディレクトリが `SKILL.md`（メインロジック）を持ち、必要に応じて `references/`（テンプレート・チェックリスト等の参照資料）を含む
- **commands/** — スラッシュコマンド（`/claude-skills:plan-create` 等）。スキルの薄いラッパー
- **skills/shared/** — 複数スキルが共有するリソース（ロール定義・共有契約等）

### スキル呼び出し

Codex CLI では `$skill-name` 形式のテキストメンションでスキルを呼び出す:

| 操作 | コマンド |
|------|---------|
| 計画作成 | `$plan` |
| 計画レビュー | `$plan-reviewer` |
| 全自動サイクル | `$cycle` |
| 自動コミット | `$commit` |
| 軽量改善 | `$iterate` |
| 読み取り専用調査 | `$investigate` |
| issue 管理 | `$issue create/list/close` |
| チーム議論型サイクル | `$team-cycle` |
| コードベース全体レビュー | `$codebase-review` |
| 攻撃者視点レビュー | `$attack-review [server/client/full]` |
| 並行 cycle 実行 | `$parallel-cycle` |
| セッション引き継ぎ | `$handoff save/restore/list` |
| アイデア壁打ち | `$brainstorm [wrap/list/plan/resume/テーマ]` |
| 行き詰まり打開の思考ツール | `$problem-solving [simplify/collide/invert/scale/pattern]` |
| 条件収束ループ | `$goal-loop [oracle / 「〜まで回して」]` |
| デザイン scaffold | `$design-scaffold` |
| 制約付きページ生成 | `$design-generate` |
| デザイントークン lint | `$design-lint` |
| デザインガイド作成 | `$design-guide [update/mockup]` |
| デザイン検証ゲート | `$design-validate [lint/visual/full/report]` |
| モックアップ差分 | `$mockup-diff` |
| 動作保持リファクタ | `$refactor [スコープ]` |
| 問題の横展開一括修正 | `$sweep-fix [スコープ]` |
| 構造化デバッグ | `$systematic-debugging [問題 / investigate レポート]` |
| ドキュメント整合性チェック | `$doc-check [コミット数 / all / パス]` |
| ドキュメント化 | `$doc-write [テーマ / resume]` |
| TDD ガイド | `$test-driven-development` |
| チーム議論型計画 | `$team-plan` |
| チーム議論型発散 | `$team-brainstorm [wrap/list/plan/resume/テーマ]` |

### 主要スキル

| スキル | 役割 |
|--------|------|
| `commit` | 変更を分析し論理単位で自動コミット |
| `investigate` | 問題を読み取り専用で調査し、構造化レポートを出力 |
| `plan` | 計画ファイルの生成・管理 |
| `plan-reviewer` | 7観点並行レビュー |
| `issue` | スコープ外の問題を記録・管理 |
| `iterate` | cycle 後の追加指示を軽量改善ループで実行 |
| `cycle` | 計画の refine → implement を全自動で回す |
| `team-cycle` | チーム議論型レビュー + 自動実装サイクル |
| `codebase-review` | 4エージェント並行によるコードベース全体レビュー |
| `attack-review` | 6エージェント並行の攻撃者視点レビュー |
| `parallel-cycle` | 指示を複数 plan に分解し、並行 cycle 実行・マージ |
| `brainstorm` | アイデアの壁打ちに特化。発散→収束→plan化 |
| `goal-loop` | 機械検証可能な oracle が真になるまで自律反復 |
| `sweep-fix` | 問題を検出→パターン化→横展開検索→一括修正 |
| `refactor` | 動作保持のまま表現を改善し、類似コードへ横展開 |

## 基本ワークフロー

```
$plan ○○機能を追加したい
  ↓ docs/plans/{timestamp}_{slug}.md が生成される
$plan-reviewer
  ↓ 6-7観点のレビュー結果が出力される
$cycle
  ↓ refine→implement→commit の全自動サイクル
```

## ファイル構成

```
.claude-plugin/   # Claude Code Plugin マニフェスト
.codex-plugin/    # Codex CLI Plugin マニフェスト
commands/         # スラッシュコマンド
skills/           # スキル定義（プラットフォーム共通）
rules/            # グローバルルール
AGENTS.md         # Codex CLI 用プロジェクト説明（本ファイル）
CLAUDE.md         # Claude Code 用プロジェクト説明
```

## 編集時の注意

- スキル本文ではプラットフォーム固有のツール API 名やモデル名を使わず、自然言語で意図を記述すること（Agent Skills 標準準拠）
- 編集後は `python3 scripts/validate_repo.py` でリポジトリ整合性を検証すること。CI でも同じチェックが走る
