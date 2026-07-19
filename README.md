# claude-skills

AI コーディングエージェント向けのスキル集。
[Agent Skills](https://agentskills.io/) 標準に準拠しており、Claude Code、Codex、Copilot、Cursor、Gemini CLI 等で利用できる。

計画の作成からレビュー、自動実装、コミットまでのワークフローを中心に、セキュリティレビュー、デザインシステム、TDD ガイド、issue 自走ループなど 40 以上のスキルを提供する。

## インストール

### Claude Code Plugin（一括インストール・推奨）

全スキル、共有契約、コマンドをまとめて導入できるため、通常はこちらを推奨する。
常駐ルールとしても使いたい文書は、後述の手順で別途配置する。

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
cp skills/shared/references/design-principles.md ~/.claude/rules/
cp skills/shared/references/testing-anti-patterns.md ~/.claude/rules/
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

スキル群は「発生順の 3 レイヤ」で整理する。このリポジトリは元来メンテナ個人の作業用として plan → implement → review の基本サイクルから始まり、実務で必要になった順にスキルが増えていった。その履歴を初見の利用者にも見えるようにするため、次の 3 段で提示する。

- **Core（幹）** — plan → cycle → commit を回すのに最小限必要なスキル。初めての利用者はここだけ見れば十分。
- **Extensions（枝）** — 実務で必要になったタイミングで後から追加されたスキル。用途別に整理する。必要になったら参照する。
- **Personal / Experimental（葉）** — 本リポジトリ自身のスキル開発サイクル・移行専用スキル・実験的スキル。外部利用者は基本的に無視してよい。

### Core（幹）— まずここから

plan → cycle → commit の基本ワークフローに必要な最小セット。

| スキル | 用途 |
|--------|------|
| `plan` | 計画ファイルの作成とステータス管理 |
| `plan-reviewer` | 7 観点での計画レビュー |
| `cycle` | レビューから実装までの全自動サイクル |
| `iterate` | cycle 後の軽量な追加修正 |
| `commit` | 変更の論理単位での自動コミット |
| `brainstorm` | 計画前のアイデア壁打ち（ファイル編集禁止） |
| `codebase-review` | コードベース全体の並行レビュー（100 点満点） |

### Extensions（枝）— 用途に応じて追加

Core を補強・拡張するスキル群。すべてを覚える必要はなく、直面する課題に応じて拾えばよい。

#### 計画と実装（cycle の内部を直接使いたい場合）

| スキル | 用途 |
|--------|------|
| `plan-refine` | 計画の review → fix ループ改善（cycle の Phase 1 本体） |
| `plan-implement` | 計画の TDD 自動実装ループ（cycle の Phase 2 本体） |
| `parallel-cycle` | 複数の plan を worktree で並行実行 |

#### 調査とデバッグ

| スキル | 用途 |
|--------|------|
| `investigate` | 読み取り専用の問題調査（ファイル編集なし） |
| `systematic-debugging` | 根本原因の特定から修正までの構造化デバッグ |
| `problem-solving` | 行き詰まり打開の思考ツール集 |

#### レビュー

| スキル | 用途 |
|--------|------|
| `attack-review` | 攻撃者視点のセキュリティレビュー |
| `review-testing` | テスト品質の三層 focused レビュー（総合点なし） |
| `review-deps` | 依存ヘルスの focused レビュー（scanner 統合 + 相関分析） |
| `generate-review-rules` | プロジェクト固有のレビュールール自動生成 |

##### Composite と Focused の使い分け

レビュー系は 2 群に分かれる。**Composite**（Core の `codebase-review` と本節の `attack-review`）は総合スコアで全体像を俯瞰し、**Focused**（`review-testing` / `review-deps`）はオンデマンドで特定観点を深掘りして findings + coverage ledger を返す（総合点は出さない）。

| 群 | スキル | 対象 | 観点 | 成果物 | コスト |
|----|--------|------|------|--------|--------|
| Composite | `codebase-review` | src/ 全体（`*.test.*`・lockfile は除外） | セキュリティ/性能/品質/衛生の 8 小観点 | 100 点満点スコア + レポート | 高（4+1 エージェント並行） |
| Composite | `attack-review` | 攻撃対象コード | 6 攻撃領域（server/client モード） | リスクマトリクス | 高（6+1 エージェント並行） |
| Focused | `review-testing` | テストコード + 対応 production | 欠陥検出力・契約検証・安全網の安定性 | findings + coverage ledger | 低〜中（必要時のみ） |
| Focused | `review-deps` | manifest / lockfile / 依存 diff | 既知脆弱性（scanner 正本）+ サプライチェーン相関 | findings + coverage ledger | 低〜中（必要時のみ） |

Focused レビューは [coverage ledger](skills/shared/references/coverage-ledger.md) を必ず出力し、「問題なし（reviewed）」と「見ていない（skipped / unsupported / inconclusive）」を構造的に区別する。Composite が構造的に除外する領域（テストコード・lockfile）を Focused が第一級入力として埋める関係にある。

#### Issue 管理と自走ループ

| スキル | 用途 |
|--------|------|
| `issue` | ローカルファイルベースの issue 管理と polling ループ |
| `github-issue` | GitHub issue を起点とした自走ワークフロー |
| `goal-loop` | oracle が真になるまで修正を自律反復する収束ループ |
| `goal-decomposition` | 大枠ゴールを自走可能な単位に分解 |
| `loop-triage` | センサーの検出結果を issue キューに自動供給 |

#### チーム議論型

| スキル | 用途 |
|--------|------|
| `team-brainstorm` | 4 思考スタイルによるチーム議論型の壁打ち |
| `team-plan` | 4 専門家による議論型の計画作成 |
| `team-cycle` | チーム議論型レビュー付きの自動実装 |

#### ドキュメント

| スキル | 用途 |
|--------|------|
| `doc-check` | ドキュメントとコードの整合性検証 |
| `doc-write` | 調査結果を構造化ドキュメントに昇華 |
| `doc-audit` | docs 内のアーティファクト横断スキャン |
| `decision-journal` | 技術選定の意思決定を判例集方式で記録・聞き取り（着手前 1 行プロトコル / 選定会話の固化 / 判例聞き取り） |
| `handoff` | セッション間のコンテキスト引き継ぎ（揮発型） |

#### デザインシステム

| スキル | 用途 |
|--------|------|
| `design-guide` | 対話的に DESIGN.md を作成 |
| `design-scaffold` | DESIGN.md からトークンと lint 設定を生成 |
| `design-generate` | ページ定義に基づく制約付きページ生成 |
| `design-lint` | デザイントークン違反の機械検出 |
| `design-validate` | 多段階検証ゲート（lint → visual → judge） |
| `mockup-diff` | モックアップと実装の視覚差分を検出 |

#### コード改善

| スキル | 用途 |
|--------|------|
| `sweep-fix` | 問題を全体へ横展開検索し一括修正 |
| `refactor` | 動作を保持したままリファクタリング |
| `test-driven-development` | TDD サイクルのガイド |
| `spec-verify` | 検証可能な契約の正本化・PBT 生成・証拠ベースのドリフト機械検知 |

### Personal / Experimental（葉）— 本リポジトリ開発用・実験的

本スキル集自身の開発・チューニング・移行を支えるメタスキル群と、実験的スキル。外部利用者にとっては直接価値がないため、初見では読み飛ばして構わない。ただし「スキル集の運用ノウハウ自体を学びたい」場合は参考になる。

| スキル | 用途 |
|--------|------|
| `artifacts` | Agent Artifact Store の初期化・状態診断・移行（本スキル集を使うプロジェクトのセットアップ用） |
| `skill-improve` | セッションデータからスキルの摩擦を検出 |
| `trigger-eval` | description の発火精度を実測・改善 |
| `empirical-prompt-tuning` | テキスト指示の品質を実測・反復改善 |
| `context-audit` | 指示ファイルの老朽化を監査 |
| `skill-regression` | 共有契約の変更による回帰を検出 |
| `skill-interface-audit` | SKILL.md の API 契約完備性を静的監査 |
| `migrate-cycles-to-plans` | 旧 docs/cycles/ から .agents/artifacts/plans/ への移行（一回限りの移行専用） |

## 構成

```
skills/          スキル本体（SKILL.md + references/ + scripts/）
  shared/        複数スキルが参照する共有契約（設計・テスト原則を含む）とユーティリティ
commands/        スラッシュコマンド（スキルへの薄いラッパー）
rules/           Claude Code の初期プロンプトに配置する常駐専用ルール
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
