# AGENTS.md

This file provides guidance to Codex CLI when working with code in this repository.

## プロジェクト概要

Claude Code / Codex CLI 共用の自作スキル集。実装計画の作成→レビュー→自動実装までのワークフローを提供する。
本リポジトリはデュアルプラグイン構造を採用し、Claude Code 用と Codex CLI 用の両方のスキルを並立させている。

## アーキテクチャ

### デュアルプラグイン構造

- **skills/** — Claude Code 用スキル定義（変更しない）
- **commands/** — Claude Code 用スラッシュコマンド（変更しない）
- **codex-skills/** — Codex CLI 用スキル定義（本ファイルで説明）

### codex-skills/ 構造

```
codex-skills/
├── shared/
│   └── references/
│       ├── tool-mapping.md        # Claude→Codex ツール変換リファレンス
│       ├── team-config.md         # チームロール定義（Codex 適応版）
│       └── severity-and-verdicts.md  # 重大度・判定基準（共有シンボリックリンク）
├── commit/
│   └── SKILL.md                   # 自動コミット
├── investigate/
│   └── SKILL.md                   # 読み取り専用調査
├── plan/
│   ├── SKILL.md                   # 計画管理
│   └── references/                # テンプレート（共有シンボリックリンク）
├── plan-reviewer/
│   ├── SKILL.md                   # 7観点レビュー
│   └── references/                # レビュー基準（共有シンボリックリンク）
├── issue/
│   ├── SKILL.md                   # issue 管理
│   └── references/                # テンプレート（共有シンボリックリンク）
├── iterate/
│   ├── SKILL.md                   # 軽量改善ループ
│   └── references/                # レビュー基準（共有シンボリックリンク）
├── cycle/
│   └── SKILL.md                   # refine→implement 全自動サイクル
└── team-cycle/
    ├── SKILL.md                   # チーム議論型レビュー＋自動実装
    └── references/                # レビューフロー（共有シンボリックリンク）
```

### 共有リソース

- **skills/shared/** — 複数スキルが共有するリソース。ツール非依存の references は `codex-skills/` からシンボリックリンクで参照する
- **codex-skills/shared/** — Codex 固有の共有リソース（tool-mapping.md、Codex 適応版 team-config.md）

### スキル呼び出し

Codex CLI ではスラッシュコマンドの代わりに `$skill-name` 形式のテキストメンションでスキルを呼び出す:

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

### 主要スキル

| スキル | 役割 |
|--------|------|
| `commit` | 変更を分析し論理単位で自動コミット（確認なし即実行） |
| `investigate` | 問題を読み取り専用で調査し、構造化レポートを出力。ファイル編集は一切行わない |
| `plan` | 計画ファイル（`docs/plans/{timestamp}_{slug}.md`）、`docs/status.md`、`docs/session-history.md` の生成・管理 |
| `plan-reviewer` | 6観点並行レビュー（Feasibility / Security / Performance / Architecture / Completeness / Alternatives + UI/UX 条件付き） |
| `issue` | plan 中に発見したスコープ外の問題を記録・管理し、plan → cycle に繋げる |
| `iterate` | cycle 後の追加指示をサイズ適応型の軽量改善ループで実行 |
| `cycle` | 計画の refine → implement を全自動で回す |
| `team-cycle` | spawn_agent グループによるチーム議論型レビュー + 自動実装サイクル |

### ワークフロー設計パターン

- **spawn_agent 委譲**: 重い処理は spawn_agent に委譲し、メインコンテキストにはサマリーのみ保持する
- **ヘッドレス対応**: cycle はユーザー確認プロンプトを出さずに全自動で動作する
- **セッション履歴アーカイブ**: Completed セッションは `docs/session-history.md` に自動アーカイブされ、`docs/status.md` の肥大化を防ぐ
- **部分成功の許容**: 複数の処理ステップのうち一部が失敗しても、成功分のみ記録し全体を巻き戻さない

## 基本ワークフロー

### 手動サイクル

```
$plan ○○機能を追加したい
  ↓ docs/plans/{timestamp}_{slug}.md が生成される
$plan-reviewer
  ↓ 6-7観点のレビュー結果が出力される
$cycle
  ↓ refine→implement→commit の全自動サイクル
```

### 全自動サイクル

```
$cycle docs/plans/20260313_feature-x.md
```

refine（最大4ラウンド）→ implement（ステップごとコミット）→ サマリー生成を
spawn_agent に委譲して全自動で回す。ヘッドレス実行対応。

### cycle 後の追加修正

```
$iterate ○○の挙動をちょっと変えて
```

タスクサイズを自動判定し、小さければ軽量ループ（実装→簡易レビュー）、
大きければ plan 切り出しを提案する。

### Issue 管理

```
$issue create ○○の処理でエラーハンドリングが不足している
$issue list
$issue close {slug}
```

### 読み取り専用調査

```
$investigate ○○が動かない原因を調べて
```

ファイル編集ゼロ保証。構造化レポートを出力する。

## ファイル構成

```
.claude-plugin/
  plugin.json         # Claude Code Plugin マニフェスト
commands/             # Claude Code 用スラッシュコマンド
skills/               # Claude Code 用スキル
codex-skills/         # Codex CLI 用スキル
rules/                # グローバルルール
AGENTS.md             # Codex CLI 用プロジェクト説明（本ファイル）
CLAUDE.md             # Claude Code 用プロジェクト説明
```

## 編集時の注意

- `codex-skills/` 内の references/ にあるシンボリックリンクは `../../skills/X/references/` を指している。パスを変更する場合はリンクも更新すること
- `skills/` と `commands/` 配下の既存ファイルは変更しない（Claude Code 版との独立性を維持）
- `.claude/review-rules.md` はプロジェクト固有のレビュールールで、ツールに依存しない内容。Codex 版でもそのまま参照する
