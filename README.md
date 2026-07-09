# claude-skills

AI コーディングエージェント向けのスキル集。
[Agent Skills](https://agentskills.io/) 標準に準拠しており、Claude Code、Codex、Copilot、Cursor、Gemini CLI 等で利用できる。

計画の作成からレビュー、自動実装、コミットまでのワークフローを中心に、セキュリティレビュー、デザインシステム、TDD ガイド、issue 自走ループなど 40 以上のスキルを提供する。

## インストール

### gh skill（推奨）

```bash
# 共有契約ライブラリ（他スキルが依存。最初にインストールする）
gh skill install ba0918/claude-skills shared --agent <your-agent>

# 個別スキルをインストール
gh skill install ba0918/claude-skills plan --agent claude-code

# 対話的に選択
gh skill install ba0918/claude-skills --agent claude-code
```

`--agent` には `claude-code` / `codex` / `github-copilot` / `cursor` / `gemini` 等を指定する。
`--scope user` を付けるとグローバルインストールになる。

> スキル本文は Claude Code のツール名で記述されている。
> Codex 等で利用する場合は、`shared/references/tool-mapping.md` の変換マッピングを参照する。

### Claude Code Plugin（一括インストール）

全スキル、コマンド、ルールをまとめて導入したい場合は Plugin が適している。

```bash
claude plugin marketplace add ba0918/claude-skills
claude plugin install claude-skills@claude-skills
```

Plugin ではコマンドを `/claude-skills:plan-create` のように名前空間付きで呼び出せる。

## 基本ワークフロー

plan（計画）→ cycle（自動実装）→ commit（コミット）が基本の流れになる。

```
計画を作りたい        → plan-create
計画を自動実装したい  → cycle
追加修正したい        → iterate
コミットしたい        → commit
```

`cycle` は計画のレビューと実装をエージェントに委譲し、全自動で回す。
`iterate` は cycle 後の軽微な修正に使う。タスクの大きさを自動判定し、大きければ新しい plan の作成を提案する。

## スキル一覧

### 計画と実装

| スキル | 用途 |
|--------|------|
| `plan` | 計画ファイルの作成とステータス管理 |
| `plan-reviewer` | 7 観点での計画レビュー |
| `cycle` | レビューから実装までの全自動サイクル |
| `iterate` | cycle 後の軽量な追加修正 |
| `commit` | 変更の論理単位での自動コミット |
| `parallel-cycle` | 複数の plan を worktree で並行実行 |

### 調査とデバッグ

| スキル | 用途 |
|--------|------|
| `investigate` | 読み取り専用の問題調査（ファイル編集なし） |
| `systematic-debugging` | 根本原因の特定から修正までの構造化デバッグ |
| `problem-solving` | 行き詰まり打開の思考ツール集 |

### レビュー

| スキル | 用途 |
|--------|------|
| `codebase-review` | コードベース全体の並行レビュー（100 点満点） |
| `attack-review` | 攻撃者視点のセキュリティレビュー |
| `generate-review-rules` | プロジェクト固有のレビュールール自動生成 |

### Issue 管理と自走ループ

| スキル | 用途 |
|--------|------|
| `issue` | ローカルファイルベースの issue 管理と polling ループ |
| `github-issue` | GitHub issue を起点とした自走ワークフロー |
| `goal-loop` | oracle が真になるまで修正を自律反復する収束ループ |
| `goal-decomposition` | 大枠ゴールを自走可能な単位に分解 |
| `loop-triage` | センサーの検出結果を issue キューに自動供給 |

### アイデアとチーム議論

| スキル | 用途 |
|--------|------|
| `brainstorm` | アイデアの壁打ち（ファイル編集禁止） |
| `team-brainstorm` | 4 思考スタイルによるチーム議論型の壁打ち |
| `team-plan` | 4 専門家による議論型の計画作成 |
| `team-cycle` | チーム議論型レビュー付きの自動実装 |

### ドキュメント

| スキル | 用途 |
|--------|------|
| `doc-check` | ドキュメントとコードの整合性検証 |
| `doc-write` | 調査結果を構造化ドキュメントに昇華 |
| `doc-audit` | docs 内のアーティファクト横断スキャン |
| `handoff` | セッション間のコンテキスト引き継ぎ（揮発型） |

### デザインシステム

| スキル | 用途 |
|--------|------|
| `design-guide` | 対話的に DESIGN.md を作成 |
| `design-scaffold` | DESIGN.md からトークンと lint 設定を生成 |
| `design-generate` | ページ定義に基づく制約付きページ生成 |
| `design-lint` | デザイントークン違反の機械検出 |
| `design-validate` | 多段階検証ゲート（lint → visual → judge） |
| `mockup-diff` | モックアップと実装の視覚差分を検出 |

### コード改善

| スキル | 用途 |
|--------|------|
| `sweep-fix` | 問題を全体へ横展開検索し一括修正 |
| `refactor` | 動作を保持したままリファクタリング |
| `test-driven-development` | TDD サイクルのガイド |

### メタスキル（本リポジトリ開発用）

| スキル | 用途 |
|--------|------|
| `skill-improve` | セッションデータからスキルの摩擦を検出 |
| `trigger-eval` | description の発火精度を実測・改善 |
| `empirical-prompt-tuning` | テキスト指示の品質を実測・反復改善 |
| `context-audit` | 指示ファイルの老朽化を監査 |
| `skill-regression` | 共有契約の変更による回帰を検出 |
| `codex-sync` | Claude 版から Codex 版への自動移植 |
| `migrate-cycles-to-plans` | 旧 docs/cycles/ から docs/plans/ への移行 |

## 構成

```
skills/          スキル本体（SKILL.md + references/ + scripts/）
  shared/        複数スキルが参照する共有契約とユーティリティ
commands/        Claude Code 用スラッシュコマンド（スキルへの薄いラッパー）
codex-skills/    Codex CLI 用スキル（将来的に skills/ へ統合予定）
rules/           設計原則とテストアンチパターン
scripts/         リポジトリ整合性バリデータ（CI で自動実行）
```

## 開発

```bash
# ローカルテスト
claude --plugin-dir /path/to/claude-skills

# 整合性チェック
python3 scripts/validate_repo.py

# Codex 同期台帳の更新
python3 scripts/validate_repo.py --update-manifest
```

リポジトリ整合性チェックは GitHub Actions で push / PR ごとに実行される。
symlink の切れ、frontmatter の欠落、スキル名のドリフト、バージョン同期等を機械検証する。
