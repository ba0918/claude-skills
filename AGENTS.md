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
│       ├── lang-detect.md         # 言語・フレームワーク検出契約（共有シンボリックリンク）
│       ├── convergence-pattern.md # 条件収束ループ契約（変換コピー）
│       └── polling-pattern.md     # polling 状態機械・安全ブレーキ契約（共有シンボリックリンク）
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
├── sweep-fix/
│   ├── SKILL.md                   # find-one-fix-all: 問題を全体へ横展開検索・文脈検証・一括修正
│   └── references/                # パターン抽出・文脈検証（変換コピー）
├── refactor/
│   ├── SKILL.md                   # 動作保持リファクタ + 類似コード横展開（バグは issue 化案）
│   └── references/                # 検証観点・カタログ・類似検出（symlink + 変換コピー混在）
├── systematic-debugging/
│   ├── SKILL.md                   # 4フェーズ構造化デバッグ（根本原因特定 → 修正、3回失敗ルール）
│   └── references/                # データフロートレース手法（共有シンボリックリンク）
├── doc-check/
│   ├── SKILL.md                   # ドキュメント↔コード整合性の検証・自動修正
│   └── references/                # 構造/内容チェック（symlink + 変換コピー混在）
├── doc-write/
│   ├── SKILL.md                   # 調査結果を Mermaid 付きドキュメントに昇華
│   └── references/                # ADR/技術ノート等テンプレート（共有シンボリックリンク）
├── test-driven-development/
│   └── SKILL.md                   # TDD (RED-GREEN-REFACTOR) 対話ガイド（shell でテスト実行証拠を要求）
├── team-plan/
│   ├── SKILL.md                   # spawn_agent グループによるチーム議論型計画作成（4専門家）
│   └── references/                # 計画フロー（変換コピー）
├── team-brainstorm/
│   ├── SKILL.md                   # spawn_agent グループによるチーム議論型発散（4思考スタイル）
│   └── references/                # 発散フロー・ロール・テンプレート（symlink + 変換コピー混在）
├── goal-loop/
│   ├── SKILL.md                   # oracle 収束まで自律反復（maker/checker 分離・ハッシュロック）
│   └── scripts/                   # goal_loop.py（symlink、純関数 + unittest）
├── design-scaffold/
│   ├── SKILL.md                   # DESIGN.md → tokens/CSS/lint 設定を scaffold 生成
│   └── references/                # schema 5本（共有シンボリックリンク）
├── design-generate/
│   ├── SKILL.md                   # ページ定義+カタログに基づく制約付きページ生成
│   └── references/                # 生成制約（共有シンボリックリンク）
├── design-lint/
│   ├── SKILL.md                   # tokens.json ベースのデザイントークン lint（スクリプト駆動）
│   ├── references/                # lint 契約（変換コピー）
│   └── scripts/                   # design_lint.py（symlink、標準ライブラリ + unittest）
├── design-guide/
│   ├── SKILL.md                   # 対話ディスカバリーで DESIGN.md 生成（Session/Update/Mockup）
│   └── references/                # ディスカバリー質問・テンプレート・アンチパターン（symlink + 変換）
├── design-validate/
│   ├── SKILL.md                   # 多段階検証ゲート（lint→visual→rubric judge）
│   └── references/                # 検証パイプライン（変換コピー）
├── mockup-diff/
│   ├── SKILL.md                   # モックアップ vs 実アプリのスクショ比較・差分修正
│   └── references/                # 比較スクリプト要件（変換コピー）
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
| `goal-loop` | 機械検証可能な oracle が真になるまで oracle 実行→implementer 委譲修正を自律反復。ハッシュロックで oracle-gaming 遮断、stall/oscillation 検出。oracle 実行はコントローラのみ（maker/checker 分離） |
| `design-scaffold` | DESIGN.md から machine-readable なデザインシステム（tokens.json/CSS/lint 設定/React theme）を scaffold 生成 |
| `design-generate` | ページ定義+コンポーネントカタログに基づく制約付きページ生成。生成後に design_lint.py で自動 lint |
| `design-lint` | .design/tokens.json ベースでデザイントークン違反（DL001-204）を機械検出。design_lint.py（symlink 共有）を shell 実行 |
| `design-guide` | 対話ディスカバリーで DESIGN.md（Google Stitch 準拠）を生成。Session/Update/Mockup の3ワークフロー。会話ターンで二択質問 |
| `design-validate` | Static Lint→Visual Regression(Playwright)→Rubric Judge の多段階検証ゲート。weighted average で合否判定 |
| `mockup-diff` | 承認済みモックアップ HTML vs 実アプリのスクショ比較で実装差異を検出・修正（compare.mjs / Playwright） |
| `refactor` | ユーザ指定スコープを完全理解し動作保持のまま表現を改善、類似コードへ文脈検証つき横展開（3値判定）。発見したバグは修正せず issue 化案を提示。ファイル改変は Phase 5 の apply_patch のみ |
| `sweep-fix` | ユーザ指定範囲の問題を検出→パターン化→コードベース全体へ横展開検索（grep/ast-grep + symbol-ref フォールバック）→文脈検証（3値判定・fail-safe）→CONFIRMED のみ一括修正する find-one-fix-all 型 |
| `systematic-debugging` | 4フェーズ構造化デバッグ（Root Cause Investigation → Pattern Analysis → Hypothesis & Testing → Implementation）。根本原因を特定してから修正し、3回失敗ルールで設計問題を検出。investigate の補完として修正まで実行（apply_patch は Phase 4 のみ） |
| `doc-check` | ドキュメント（README/AGENTS.md 等）とコードの整合性を検証し、不整合を apply_patch で自動修正。Content Check は spawn_agent に委譲 |
| `doc-write` | LLMとのやり取り・調査結果を Mermaid 図付きの構造化ドキュメントに昇華（会話ターンでの要件ディスカバリー、apply_patch で生成） |
| `test-driven-development` | TDD (RED-GREEN-REFACTOR) 対話ガイド。各フェーズで shell テスト実行を証拠要求。tdd-contract / verification-gate 準拠 |
| `team-plan` | spawn_agent グループによるチーム議論型計画作成。4専門家（Security/Performance/Architect/Pragmatist）が議論 |
| `team-brainstorm` | spawn_agent グループによるチーム議論型発散。4思考スタイル（Challenger/Explorer/Connector/Grounded）。壁打ち中はファイル編集禁止 |

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
