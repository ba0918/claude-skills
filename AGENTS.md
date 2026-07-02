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
│       ├── severity-and-verdicts.md  # 重大度・判定基準（共有シンボリックリンク）
│       └── lang-detect.md         # 言語・フレームワーク検出契約（共有シンボリックリンク）
├── commit/
│   └── SKILL.md                   # 自動コミット
├── investigate/
│   └── SKILL.md                   # 読み取り専用調査
├── plan/
│   ├── SKILL.md                   # 計画管理
│   └── references/                # テンプレート（共有シンボリックリンク）
├── plan-reviewer/
│   ├── SKILL.md                   # 7観点レビュー（UI/UX 条件付き）
│   └── references/                # レビュー基準（共有シンボリックリンク）
├── codebase-review/
│   ├── SKILL.md                   # 4エージェント並行コードベースレビュー
│   └── references/                # レビュー基準・レポートテンプレート（共有シンボリックリンク）
├── attack-review/
│   ├── SKILL.md                   # 攻撃者視点レビュー（6エージェント、Codex セカンドオピニオンなし）
│   └── references/                # 攻撃基準・言語プロファイル（共有シンボリックリンク）
├── issue/
│   ├── SKILL.md                   # issue 管理
│   └── references/                # テンプレート（共有シンボリックリンク）
├── iterate/
│   ├── SKILL.md                   # 軽量改善ループ
│   └── references/                # レビュー基準（共有シンボリックリンク）
├── cycle/
│   └── SKILL.md                   # refine→implement 全自動サイクル
├── team-cycle/
│   ├── SKILL.md                   # チーム議論型レビュー＋自動実装
│   └── references/                # レビューフロー（共有シンボリックリンク）
├── parallel-cycle/
│   ├── SKILL.md                   # worktree 並行 cycle（完全 headless）
│   └── references/                # 分解ガイド・直交性チェック・マージ戦略（共有シンボリックリンク）
├── handoff/
│   └── SKILL.md                   # セッション引き継ぎ（apply_patch ベース、save/restore/list）
├── brainstorm/
│   ├── SKILL.md                   # アイデア壁打ち（Codex セカンドオピニオンなし、ファイル編集禁止）
│   └── references/                # アイデアメモテンプレート（共有シンボリックリンク）
└── problem-solving/
    └── SKILL.md                   # 行き詰まり打開の思考ツール集（5サブワークフロー、編集禁止）
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
| コードベース全体レビュー | `$codebase-review` |
| 攻撃者視点レビュー | `$attack-review [server/client/full]` |
| 並行 cycle 実行 | `$parallel-cycle` |
| セッション引き継ぎ | `$handoff save/restore/list` |
| アイデア壁打ち | `$brainstorm [wrap/list/plan/resume/テーマ]` |
| 行き詰まり打開の思考ツール | `$problem-solving [simplify/collide/invert/scale/pattern]` |

### 主要スキル

| スキル | 役割 |
|--------|------|
| `commit` | 変更を分析し論理単位で自動コミット（確認なし即実行） |
| `investigate` | 問題を読み取り専用で調査し、構造化レポートを出力。ファイル編集は一切行わない |
| `plan` | 計画ファイル（`docs/plans/{timestamp}_{slug}.md`）、`docs/status.md`、`docs/session-history.md` の生成・管理 |
| `plan-reviewer` | 7観点並行レビュー（Feasibility / Security / Performance / Architecture / Completeness / Alternatives / UI/UX 条件付き） |
| `issue` | plan 中に発見したスコープ外の問題を記録・管理し、plan → cycle に繋げる |
| `iterate` | cycle 後の追加指示をサイズ適応型の軽量改善ループで実行 |
| `cycle` | 計画の refine → implement を全自動で回す |
| `team-cycle` | spawn_agent グループによるチーム議論型レビュー + 自動実装サイクル |
| `codebase-review` | 4エージェント並行によるコードベース全体レビュー（100点満点スコアリング） |
| `attack-review` | 6エージェント並行の攻撃者視点レビュー。リスクマトリクス分類、server/client/full モード対応 |
| `parallel-cycle` | 指示を複数 plan に分解し、git worktree で並行 cycle 実行・マージ（完全 headless） |
| `handoff` | セッション間コンテキスト引き継ぎ。save で `docs/handoff/` に保存、restore で読込→自動削除（揮発型） |
| `brainstorm` | アイデアの壁打ちに特化。発散→収束→plan化の導線を提供し、壁打ち中はファイル編集禁止（apply_patch は wrap/plan のみ） |
| `problem-solving` | 行き詰まった時の思考ツール集。5サブワークフロー（simplify/collide/invert/scale/pattern）で多角的アプローチ。apply_patch 禁止（概念レベルの議論に集中） |

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
- 編集後は `python3 scripts/validate_repo.py` でリポジトリ整合性（symlink / リンク切れ / 対応表 / ドキュメントドリフト / Claude⇔Codex 同期台帳）を検証すること。CI（GitHub Actions）でも同じチェックが走る
- **Claude⇔Codex 同期台帳**: `codex-skills/sync-manifest.json` が各 Codex スキルのソース（`skills/<name>/SKILL.md`、cycle のみ `commands/cycle.md`）の sha256 を記録している。ソース側を変更すると CI が「未同期」で fail するので、Codex 版へ反映（または反映不要と判断）した上で `python3 scripts/validate_repo.py --update-manifest` を実行して台帳を更新すること
