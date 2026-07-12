# claude-skills

AI コーディングエージェント向けのスキル集。
[Agent Skills](https://agentskills.io/) 標準に準拠しており、Claude Code、Codex、Copilot、Cursor、Gemini CLI 等で利用できる。

計画の作成からレビュー、自動実装、コミットまでのワークフローを中心に、セキュリティレビュー、デザインシステム、TDD ガイド、issue 自走ループなど 40 以上のスキルを提供する。

## インストール

### Claude Code Plugin（一括インストール・推奨）

全スキル、共有契約、コマンド、ルールをまとめて導入できるため、通常はこちらを推奨する。

```bash
claude plugin marketplace add ba0918/claude-skills
claude plugin install claude-skills@claude-skills
```

Plugin ではコマンドを `/claude-skills:plan-create` のように名前空間付きで呼び出せる。

### Codex CLI Plugin（一括インストール・推奨）

```bash
codex plugin marketplace add ba0918/claude-skills
codex plugin add claude-skills@claude-skills
```

スキル本文はプラットフォーム非依存の自然言語で記述されており、そのまま利用できる。

### Claude Code rules（任意）

`rules/` は Claude Code の常駐ルールとしても使えるが、Plugin フォーマットでは自動配置されない。
必要な場合のみ手動でコピーする。

```bash
mkdir -p ~/.claude/rules
cp rules/*.md ~/.claude/rules/
```

### gh skill（個別インストール・実験的）

Agent Skills 標準の個別インストールに対応しているが、現時点では標準仕様上、複数スキルから参照される `shared/` 依存を bundle として宣言できない。
複数スキルを組み合わせて使う場合は Plugin を推奨する。

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
| `plan-refine` | 計画の review → fix ループ改善（cycle の Phase 1） |
| `plan-implement` | 計画の TDD 自動実装ループ（cycle の Phase 2） |
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
| `review-testing` | テスト品質の三層 focused レビュー（総合点なし） |
| `review-deps` | 依存ヘルスの focused レビュー（scanner 統合 + 相関分析） |
| `generate-review-rules` | プロジェクト固有のレビュールール自動生成 |

#### Composite と Focused の使い分け

レビュー系は 2 群に分かれる。**Composite** は総合スコアで全体像を俯瞰し、**Focused** は
オンデマンドで特定観点を深掘りして findings + coverage ledger を返す（総合点は出さない）。

| 群 | スキル | 対象 | 観点 | 成果物 | コスト |
|----|--------|------|------|--------|--------|
| Composite | `codebase-review` | src/ 全体（`*.test.*`・lockfile は除外） | セキュリティ/性能/品質/衛生の 8 小観点 | 100 点満点スコア + レポート | 高（4+1 エージェント並行） |
| Composite | `attack-review` | 攻撃対象コード | 6 攻撃領域（server/client モード） | リスクマトリクス | 高（6+1 エージェント並行） |
| Focused | `review-testing` | テストコード + 対応 production | 欠陥検出力・契約検証・安全網の安定性 | findings + coverage ledger | 低〜中（必要時のみ） |
| Focused | `review-deps` | manifest / lockfile / 依存 diff | 既知脆弱性（scanner 正本）+ サプライチェーン相関 | findings + coverage ledger | 低〜中（必要時のみ） |

Focused レビューは [coverage ledger](skills/shared/references/coverage-ledger.md) を必ず出力し、
「問題なし（reviewed）」と「見ていない（skipped / unsupported / inconclusive）」を構造的に区別する。
Composite が構造的に除外する領域（テストコード・lockfile）を Focused が第一級入力として埋める関係にある。

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
| `artifacts` | Agent Artifact Store の初期化・状態診断・移行 |
| `skill-improve` | セッションデータからスキルの摩擦を検出 |
| `trigger-eval` | description の発火精度を実測・改善 |
| `empirical-prompt-tuning` | テキスト指示の品質を実測・反復改善 |
| `context-audit` | 指示ファイルの老朽化を監査 |
| `skill-regression` | 共有契約の変更による回帰を検出 |
| `skill-interface-audit` | SKILL.md の API 契約完備性を静的監査 |
| `migrate-cycles-to-plans` | 旧 docs/cycles/ から .agents/artifacts/plans/ への移行 |

## 構成

```
skills/          スキル本体（SKILL.md + references/ + scripts/）
  shared/        複数スキルが参照する共有契約とユーティリティ
commands/        スラッシュコマンド（スキルへの薄いラッパー）
rules/           設計原則とテストアンチパターン
scripts/         リポジトリ整合性バリデータ（CI で自動実行）
```

## 開発

```bash
# ローカルテスト
claude --plugin-dir /path/to/claude-skills

# 整合性チェック
python3 scripts/validate_repo.py
```

リポジトリ整合性チェックは GitHub Actions で push / PR ごとに実行される。
symlink の切れ、frontmatter の欠落、スキル名のドリフト、バージョン同期等を機械検証する。
