# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Claude Code 用の自作スキル・コマンド集（Plugin フォーマット）。実装計画の作成→レビュー→自動実装までのワークフローを提供する。
Claude Code の Plugin として `claude plugin install` でインストールするか、`claude --plugin-dir` でローカルテストできる。

## アーキテクチャ

### 2つのレイヤー

- **commands/** — スラッシュコマンド（`/claude-skills:plan-create` 等）。ユーザーが直接呼び出すエントリーポイント。各 `.md` ファイルが1つのコマンドに対応。
- **skills/** — スキル定義。各ディレクトリが `SKILL.md`（メインロジック）を持ち、必要に応じて `references/`（テンプレート・チェックリスト等の参照資料）を含む。

### 共有リソース

- **skills/shared/** — 複数スキルが共有するリソースの配置場所。`skills/shared/references/` にロール定義等の共有参照資料を含む。
  - `team-config.md`: team-plan、team-cycle、team-brainstorm が共有する AgenticTeam のロール定義
  - `severity-and-verdicts.md`: team-plan と team-cycle が共有する重大度・判定基準の定義

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
commands/issue-create.md →  skills/issue/SKILL.md (create ワークフロー)
commands/issue-list.md   →  skills/issue/SKILL.md (list ワークフロー)
commands/issue-plan.md   →  skills/issue/SKILL.md (plan ワークフロー)
commands/issue-cycle.md  →  skills/issue/SKILL.md (cycle ワークフロー)
commands/issue-close.md  →  skills/issue/SKILL.md (close ワークフロー)
commands/issue-team-cycle.md →  skills/issue/SKILL.md (cycle --team ワークフロー)
commands/plan-resume.md  →  skills/plan/SKILL.md (セッション復帰)
commands/plan-status.md  →  skills/plan/SKILL.md (ステータス更新)
commands/parallel-cycle.md → skills/parallel-cycle/SKILL.md
commands/investigate.md  →  skills/investigate/SKILL.md
commands/brainstorm.md   →  skills/brainstorm/SKILL.md (session ワークフロー)
commands/brainstorm-wrap.md → skills/brainstorm/SKILL.md (wrap ワークフロー)
commands/brainstorm-list.md → skills/brainstorm/SKILL.md (list ワークフロー)
commands/brainstorm-plan.md → skills/brainstorm/SKILL.md (plan ワークフロー)
commands/brainstorm-cycle.md → skills/brainstorm/SKILL.md (plan --cycle ワークフロー)
commands/brainstorm-team-cycle.md → skills/brainstorm/SKILL.md (plan --team-cycle ワークフロー)
commands/brainstorm-resume.md → skills/brainstorm/SKILL.md (resume ワークフロー)
commands/doc-write.md    →  skills/doc-write/SKILL.md (write ワークフロー)
commands/doc-write-resume.md → skills/doc-write/SKILL.md (resume ワークフロー)
commands/team-cycle.md   →  skills/team-cycle/SKILL.md
commands/team-plan.md    →  skills/team-plan/SKILL.md
commands/team-brainstorm.md → skills/team-brainstorm/SKILL.md (session ワークフロー)
commands/team-brainstorm-wrap.md → skills/team-brainstorm/SKILL.md (wrap ワークフロー)
commands/skill-improve.md    →  skills/skill-improve/SKILL.md
commands/doc-audit.md    →  skills/doc-audit/SKILL.md
```

> `codebase-review` と `generate-review-rules` はコマンドなし（Skill ツール直接呼び出し）。

### 主要スキル

| スキル | 役割 |
|--------|------|
| `plan` | 計画ファイル（`docs/cycles/{timestamp}_{slug}.md`）、`docs/status.md`、`docs/session-history.md` の生成・管理 |
| `plan-reviewer` | 6観点並行レビュー（Feasibility / Security / Performance / Architecture / Completeness / Alternatives） |
| `codebase-review` | 4エージェント並行によるコードベース全体レビュー。結果はJSON→統合エージェントが集約 |
| `generate-review-rules` | プロジェクト固有の `.claude/review-rules.md` を自動生成 |
| `commit` | 変更を分析し論理単位で自動コミット（確認なし即実行） |
| `iterate` | cycle 後の追加指示をサイズ適応型の軽量改善ループで実行 |
| `doc-check` | ドキュメントとコードベースの整合性を検証・自動修正 |
| `issue` | plan 中に発見したスコープ外の問題を記録・管理し、plan → cycle に繋げる |
| `parallel-cycle` | 自然言語の指示を複数 plan に分解し、worktree で並行 cycle 実行・自動マージ |
| `investigate` | 問題を読み取り専用で調査し、構造化レポートを出力。ファイル編集は一切行わない |
| `brainstorm` | アイデアの壁打ちに特化。発散→収束→plan化の導線を提供。壁打ち中はファイル編集禁止 |
| `doc-write` | LLMとのやり取り・調査結果をリーダブルなドキュメントに昇華。Mermaid図付き |
| `team-cycle` | AgenticTeam によるチーム議論型レビュー + 自動実装サイクル。4専門レビュワーが議論して計画品質を向上 |
| `team-plan` | AgenticTeam によるチーム議論型の計画作成。4専門家が議論しながら多角的な実装計画を作成 |
| `team-brainstorm` | AgenticTeam によるチーム議論型ブレインストーミング。4思考スタイル（Challenger/Explorer/Connector/Grounded）で多角的にアイデアを発散 |
| `skill-improve` | セッションデータからスキル使用時の摩擦を検出・分析し、データ駆動でスキル改善を実行するメタスキル |
| `doc-audit` | docs 内の全アーティファクトを横断スキャンし、不整合を検出・自動修復する |

### ワークフロー設計パターン

- **Agent 委譲**: `cycle` コマンドのように重い処理は Agent ツールに委譲し、メインコンテキストにはサマリーのみ保持する
- **ファイル経由の受け渡し**: `codebase-review` ではエージェント間のデータ受け渡しに `.claude/tmp/` 配下のJSONファイルを使い、コンテキストウィンドウを節約する
- **ヘッドレス対応**: `cycle` コマンドはユーザー確認プロンプトを出さずに全自動で動作する
- **セッション履歴アーカイブ**: Completed セッションは `docs/session-history.md` に自動アーカイブされ、`docs/status.md` の肥大化を防ぐ
- **Worktree 並行実行**: `parallel-cycle` では `EnterWorktree`/`ExitWorktree` で各 cycle を物理的に分離し、複数 Agent を並行起動する
- **ファイル直交性チェック**: 並行実行前に各 plan の影響ファイル集合の交差を判定し、コンフリクトが原理的に発生しないことを保証する
- **部分成功の許容**: 複数 cycle のうち一部が失敗しても、成功分のみマージし失敗ブランチは保持する
- **スクリプト経由データ収集**: `skill-improve` では Python スクリプト（collect.py）を Bash 経由で実行し、JSONL セッションデータを構造化 JSON に変換してエージェントに渡す

## インストール・開発

### Plugin としてインストール

```bash
# マーケットプレイスからインストール
claude plugin install claude-skills@<marketplace>

# ローカル開発（変更を即テスト）
claude --plugin-dir /path/to/claude-skills
```

`--plugin-dir` でのローカルテスト中は `/reload-plugins` で変更を即反映できる。

### レガシーインストール（非推奨）

```bash
./install.sh    # ~/.claude/ にシンボリックリンクを作成（非推奨）
```

> **Note:** `rules/` ディレクトリは Plugin フォーマットでは自動配置されない。グローバル rules が必要な場合は手動で `~/.claude/rules/` にコピーすること。

## 編集時の注意

- スキルの `SKILL.md` 内で参照する `references/` のファイルは相対パスでリンクしている。パスを変更する場合はリンクも更新すること
- コマンドの frontmatter（`---` ブロック）の `description` フィールドがスキル一覧での表示に使われる
- `.skill` ファイルは `.gitignore` で除外されている（単体ファイル形式のスキルは使わない方針）
