# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Claude Code / Codex CLI 共用の自作スキル集（デュアルプラグイン構造）。実装計画の作成→レビュー→自動実装までのワークフローを提供する。
Claude Code の Plugin として `claude plugin install` でインストールするか、`claude --plugin-dir` でローカルテストできる。
Codex CLI では `codex-skills/` 配下のスキルを `$skill-name` 形式で呼び出す。

## アーキテクチャ

### デュアルプラグイン構造

- **commands/** — Claude Code 用スラッシュコマンド（`/claude-skills:plan-create` 等）。ユーザーが直接呼び出すエントリーポイント。各 `.md` ファイルが1つのコマンドに対応。
- **skills/** — Claude Code 用スキル定義。各ディレクトリが `SKILL.md`（メインロジック）を持ち、必要に応じて `references/`（テンプレート・チェックリスト等の参照資料）を含む。
- **codex-skills/** — Codex CLI 用スキル定義。Claude Code 版と同じワークフローを Codex CLI ネイティブのツール（`spawn_agent`, `send_message`, `apply_patch`, `shell` 等）で再実装。ツール非依存の references は `skills/` へのシンボリックリンクで共有。

### 共有リソース

- **skills/shared/** — 複数スキルが共有するリソースの配置場所。`skills/shared/references/` にロール定義等の共有参照資料を含む。
  - `team-config.md`: team-plan、team-cycle、team-brainstorm が共有する AgenticTeam のロール定義
  - `severity-and-verdicts.md`: team-plan と team-cycle が共有する重大度・判定基準の定義
  - `codex-integration.md`: plan-reviewer、codebase-review、iterate、brainstorm が共有する Codex セカンドオピニオンの呼び出しパターン・フォールバック・セキュリティルール
  - `polling-pattern.md`: FS adapter (`skills/issue/`) / Label adapter (`skills/github-issue/`) が共通参照する polling パターン契約（状態機械 / interface / 純関数 / 安全ブレーキ）。単一ホスト前提
  - `lang-detect.md`: attack-review、generate-review-rules が共有する言語・フレームワーク検出契約（ビルドファイルマッピング / フレームワーク検出 / role分類）

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
commands/issue-polling.md →  skills/issue/SKILL.md (polling ワークフロー)
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
commands/migrate-cycles-to-plans.md → skills/migrate-cycles-to-plans/SKILL.md
commands/codebase-review.md → skills/codebase-review/SKILL.md
commands/attack-review.md → skills/attack-review/SKILL.md (full/auto ワークフロー)
commands/attack-review-server.md → skills/attack-review/SKILL.md (server ワークフロー)
commands/attack-review-client.md → skills/attack-review/SKILL.md (client ワークフロー)
commands/handoff-save.md →  skills/handoff/SKILL.md (save ワークフロー)
commands/handoff-restore.md → skills/handoff/SKILL.md (restore ワークフロー)
commands/github-issue-create.md → skills/github-issue/SKILL.md (create ワークフロー)
commands/github-issue-list.md → skills/github-issue/SKILL.md (list ワークフロー)
commands/github-issue-polling.md → skills/github-issue/SKILL.md (polling ワークフロー)
commands/github-issue-cycle.md → skills/github-issue/SKILL.md (cycle ワークフロー)
commands/design-guide.md     →  skills/design-guide/SKILL.md (session ワークフロー)
commands/design-guide-update.md → skills/design-guide/SKILL.md (update ワークフロー)
commands/design-guide-mockup.md → skills/design-guide/SKILL.md (mockup ワークフロー)
```

> `generate-review-rules` はコマンドなし（Skill ツール直接呼び出し）。

### 主要スキル

| スキル | 役割 |
|--------|------|
| `plan` | 計画ファイル（`docs/plans/{timestamp}_{slug}.md`）、`docs/status.md`、`docs/session-history.md` の生成・管理 |
| `plan-reviewer` | 7観点並行レビュー + Codex セカンドオピニオン（Feasibility / Security / Performance / Architecture / Completeness / Alternatives / UI/UX 条件付き + Codex） |
| `codebase-review` | 4エージェント + Codex 並行によるコードベース全体レビュー。結果はJSON→統合エージェントが集約。Codex は独立セクション「Codex Perspective」として表示 |
| `generate-review-rules` | プロジェクト固有の `.claude/review-rules.md` を自動生成 |
| `commit` | 変更を分析し論理単位で自動コミット（確認なし即実行） |
| `iterate` | cycle 後の追加指示をサイズ適応型の軽量改善ループで実行。Phase 4 レビューに Codex セカンドオピニオンを並行取得 |
| `doc-check` | ドキュメントとコードベースの整合性を検証・自動修正 |
| `issue` | plan 中に発見したスコープ外の問題を記録・管理し、plan → cycle に繋げる。polling ワークフローで `ready/` キューを self-driving 消化するラルフループも提供 |
| `parallel-cycle` | 自然言語の指示を複数 plan に分解し、worktree で並行 cycle 実行・自動マージ |
| `investigate` | 問題を読み取り専用で調査し、構造化レポートを出力。ファイル編集は一切行わない |
| `brainstorm` | アイデアの壁打ちに特化。発散→収束→plan化の導線を提供。壁打ち中はファイル編集禁止。各ターンで Codex セカンドオピニオンを取得し多角的な視点を提供 |
| `doc-write` | LLMとのやり取り・調査結果をリーダブルなドキュメントに昇華。Mermaid図付き |
| `team-cycle` | AgenticTeam によるチーム議論型レビュー + 自動実装サイクル。4専門レビュワーが議論して計画品質を向上 |
| `team-plan` | AgenticTeam によるチーム議論型の計画作成。4専門家が議論しながら多角的な実装計画を作成 |
| `team-brainstorm` | AgenticTeam によるチーム議論型ブレインストーミング。4思考スタイル（Challenger/Explorer/Connector/Grounded）で多角的にアイデアを発散 |
| `skill-improve` | セッションデータからスキル使用時の摩擦を検出・分析し、データ駆動でスキル改善を実行するメタスキル |
| `doc-audit` | docs 内の全アーティファクトを横断スキャンし、不整合を検出・自動修復する |
| `handoff` | セッション間のコンテキスト引き継ぎ。save で現在のコンテキストを `docs/handoff/` に構造化保存、restore で次セッションが読込→自動削除 |
| `migrate-cycles-to-plans` | `docs/cycles/` → `docs/plans/` のマイグレーション。ディレクトリ移動 + 全参照の一括置換 |
| `attack-review` | 6エージェント + Codex 並行によるコードベース攻撃者視点レビュー。リスクマトリクス（Likelihood×Impact）で脅威を分類。server/client/full モード切替対応。言語検出共通契約に基づく言語別攻撃プロファイル注入 |
| `github-issue` | GitHub issue を起点に polling → draft PR → Codex レビュー → auto merge まで自走するスキル。共通契約 `polling-pattern.md` に準拠した Label state adapter 実装。多重防御 atomic claim + fail-closed Codex ゲート + atomic dual-write ラベル + FS retry state + 7 日 hard cap rollback + 単一ホスト前提 |
| `design-guide` | 対話型ディスカバリーでプロジェクト用 DESIGN.md（Google Stitch フォーマット準拠）を生成し、それに基づくモックアップも生成。二択の選択肢でぼんやりしたデザインイメージを構造化し、AIっぽくない一貫したUI生成の基盤を作る。Session（新規作成）/ Update（部分修正）/ Mockup（モックアップ生成）の3ワークフロー |

### ワークフロー設計パターン

- **Agent 委譲**: `cycle` コマンドのように重い処理は Agent ツールに委譲し、メインコンテキストにはサマリーのみ保持する
- **ファイル経由の受け渡し**: `codebase-review` ではエージェント間のデータ受け渡しに `.claude/tmp/` 配下のJSONファイルを使い、コンテキストウィンドウを節約する
- **ヘッドレス対応**: `cycle` コマンドはユーザー確認プロンプトを出さずに全自動で動作する
- **セッション履歴アーカイブ**: Completed セッションは `docs/session-history.md` に自動アーカイブされ、`docs/status.md` の肥大化を防ぐ
- **Worktree 並行実行**: `parallel-cycle` では `EnterWorktree`/`ExitWorktree` で各 cycle を物理的に分離し、複数 Agent を並行起動する
- **ファイル直交性チェック**: 並行実行前に各 plan の影響ファイル集合の交差を判定し、コンフリクトが原理的に発生しないことを保証する
- **部分成功の許容**: 複数 cycle のうち一部が失敗しても、成功分のみマージし失敗ブランチは保持する
- **スクリプト経由データ収集**: `skill-improve` では Python スクリプト（collect.py）を Bash 経由で実行し、JSONL セッションデータを構造化 JSON に変換してエージェントに渡す
- **Polling パターン**: `issue polling` / `github-issue polling` に代表される self-driving ループ。共通契約 `skills/shared/references/polling-pattern.md` に state machine / interface / 純関数 / 安全ブレーキを集約し、state adapter を DI で差し替える 2 実装構成: FS adapter (`skills/issue/`) と Label adapter (`skills/github-issue/`)。両 adapter とも **単一ホスト前提**。Kill file 2 系統（`.STOP` graceful + `.STOP.hard` hard）・max_iter/max_wallclock/failed_streak の 3 重ガード・SIGINT trap + 5 段階 orphan recovery（worktree / stale lock / long running 7 日 hard cap / recovery marker / closed 残ラベル）の多重防御で bypass-permissions 環境での暴走を防ぐ。Label adapter 固有: atomic dual-write ラベル + verification + FS retry state (`<state_root>/retry/{N}.json`) + `error_kind = "lock"` は failed_streak 非カウント

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
