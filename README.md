# claude-skills

Claude Code 用の自作スキル・コマンド集（Plugin フォーマット）。
実装計画の作成からレビュー・自動実装までのワークフローを提供する。

## インストール

### Plugin としてインストール（推奨）

```bash
# マーケットプレイスからインストール
claude plugin install claude-skills@<marketplace>

# ローカル開発（変更を即テスト）
claude --plugin-dir /path/to/claude-skills
```

Plugin としてインストールすると、コマンドは `/claude-skills:plan-create` のように名前空間付きで呼び出せる。

`--plugin-dir` でのローカルテスト中は `/reload-plugins` で変更を即反映できる。

### レガシーインストール（非推奨）

```bash
git clone <repo-url> ~/develop/claude-skills
cd ~/develop/claude-skills
./install.sh
```

> **Note:** `rules/` ディレクトリは Plugin フォーマットでは自動配置されない。グローバル rules が必要な場合は手動で `~/.claude/rules/` にコピーすること。

## コマンド一覧

| コマンド | 説明 |
|----------|------|
| `/claude-skills:plan-create` | 実装計画を新規作成（`docs/plans/` に配置） |
| `/claude-skills:plan-review` | 計画を7観点で徹底レビュー |
| `/claude-skills:plan-refine` | レビュー → 修正ループ（PASS まで繰り返す） |
| `/claude-skills:plan-implement` | 実装計画を自動実装（implement → review ループ） |
| `/claude-skills:plan-resume` | 前回のセッションを引き継ぐ |
| `/claude-skills:plan-status` | 計画のステータスを更新 |
| `/claude-skills:cycle` | refine → implement → サマリー生成を全自動で回す |
| `/claude-skills:commit` | 変更内容を分析し、論理単位で自動コミット |
| `/claude-skills:iterate` | cycle 後の追加指示を軽量改善ループで実行 |
| `/claude-skills:doc-check` | ドキュメントとコードの整合性を検証・自動修正 |
| `/claude-skills:doc-write` | LLMとのやり取り・調査結果をリーダブルなドキュメントに昇華 |
| `/claude-skills:doc-write-resume` | 既存のドキュメントを再編集 |
| `/claude-skills:issue-create` | スコープ外の問題を issue として記録 |
| `/claude-skills:issue-list` | 未解決 issue の一覧を表示 |
| `/claude-skills:issue-cycle` | issue を選択して plan → cycle で解決 |
| `/claude-skills:issue-plan` | issue を選択して plan を作成（cycle は実行しない） |
| `/claude-skills:issue-close` | issue をクローズしてアーカイブ |
| `/claude-skills:parallel-cycle` | 指示を分解→並行 cycle 実行→自動マージ |
| `/claude-skills:investigate` | 問題を読み取り専用で調査し、構造化レポートを出力 |
| `/claude-skills:brainstorm` | アイデアの壁打ちセッションを開始（議論のみ、実装禁止） |
| `/claude-skills:brainstorm-wrap` | 壁打ちの内容を整理してメモファイル化 |
| `/claude-skills:brainstorm-list` | 過去のアイデア一覧を表示 |
| `/claude-skills:brainstorm-plan` | アイデアを plan に変換 |
| `/claude-skills:brainstorm-resume` | 既存のアイデアメモを元に壁打ちを再開 |
| `/claude-skills:team-cycle` | AgenticTeam によるチーム議論型レビュー → 自動実装の全サイクルを実行 |
| `/claude-skills:team-plan` | AgenticTeam によるチーム議論型の計画作成を実行 |
| `/claude-skills:team-brainstorm` | チーム議論型のブレインストーミングを開始（4思考スタイルで多角的に発散） |
| `/claude-skills:team-brainstorm-wrap` | チーム壁打ちの成果を整理してアイデアメモに保存 |
| `/claude-skills:skill-improve` | セッションデータからスキルの摩擦を検出・分析し、データ駆動でスキル改善を実行 |
| `/claude-skills:doc-audit` | docs 内のアーティファクトを横断スキャンし不整合を検出・修復 |
| `/claude-skills:issue-team-cycle` | issue を選択して team-cycle（チームレビュー付き）で解決 |
| `/claude-skills:brainstorm-cycle` | アイデアを plan に変換し cycle を即実行 |
| `/claude-skills:brainstorm-team-cycle` | アイデアを plan に変換し team-cycle（チームレビュー付き）で即実行 |
| `/claude-skills:migrate-cycles-to-plans` | `docs/cycles/` → `docs/plans/` のマイグレーションを実行 |
| `/claude-skills:codebase-review` | コードベース全体を4つの専門エージェントで並行レビューし、100点満点でスコアリング |

## スキル一覧

| スキル | 説明 |
|--------|------|
| `plan` | 計画ファイルと `docs/status.md` の管理 |
| `plan-reviewer` | 7観点（実現可能性・セキュリティ・パフォーマンス/メモリ・アーキテクチャ・網羅性・代替手法・UI/UX条件付き）+ Codex セカンドオピニオンの並行レビュー |
| `codebase-review` | 4エージェント + Codex 並行によるコードベース全体レビュー（100点満点） |
| `generate-review-rules` | プロジェクト固有のレビュールール自動生成 |
| `commit` | 変更を分析し論理単位で自動コミット（確認なし即実行） |
| `iterate` | サイズ適応型の軽量改善ループ（cycle より軽く、直接作業より安全） |
| `doc-check` | ドキュメントとコードベースの整合性検証・自動修正 |
| `doc-write` | LLMとのやり取り・調査結果をリーダブルなドキュメントに昇華。Mermaid図付き |
| `issue` | スコープ外の問題を記録・管理し plan → cycle に繋げる |
| `parallel-cycle` | 自然言語の指示を分解し、worktree で並行 cycle 実行・自動マージ |
| `investigate` | 問題を読み取り専用で調査し、構造化レポートを出力。ファイル編集は一切行わない |
| `brainstorm` | アイデアの壁打ちに特化。発散→収束→plan化の導線を提供。壁打ち中はファイル編集禁止 |
| `team-cycle` | AgenticTeam によるチーム議論型レビュー + 自動実装サイクル。4専門レビュワーが議論して計画品質を向上 |
| `team-plan` | AgenticTeam によるチーム議論型の計画作成。4専門家が議論しながら多角的な実装計画を作成 |
| `team-brainstorm` | AgenticTeam によるチーム議論型ブレインストーミング。4思考スタイル（Challenger/Explorer/Connector/Grounded）で多角的にアイデアを発散 |
| `skill-improve` | セッションデータからスキル使用時の摩擦を検出・分析し、データ駆動でスキル改善を実行するメタスキル |
| `doc-audit` | docs 内の全アーティファクトを横断スキャンし、不整合を検出・自動修復 |
| `migrate-cycles-to-plans` | `docs/cycles/` → `docs/plans/` のマイグレーション。ディレクトリ移動 + 全参照の一括置換 |

## 基本ワークフロー

### 手動サイクル

```
/claude-skills:plan-create ○○機能を追加したい
  ↓ docs/plans/{timestamp}_{slug}.md が生成される
/claude-skills:plan-refine
  ↓ レビュー → 修正を PASS まで繰り返す
/claude-skills:plan-implement
  ↓ ステップごとに TDD で実装 → レビュー → コミット
/claude-skills:plan-status 完了
```

### 全自動サイクル

```
/claude-skills:cycle docs/plans/20260313_feature-x.md
```

refine（最大4ラウンド）→ implement（ステップごとコミット）→ サマリー生成を
Agent に委譲して全自動で回す。ヘッドレス実行対応。

### cycle 後の追加修正

```
/claude-skills:iterate ○○の挙動をちょっと変えて
```

タスクサイズを自動判定し、小さければ軽量ループ（実装→簡易レビュー）、
大きければ plan 切り出しを提案する。変更は直近の計画ファイルに追記される。

### Issue 管理

```
/claude-skills:issue-create ○○の処理でエラーハンドリングが不足している
  ↓ docs/issues/{date}_{slug}.md と issue-status.md が生成される
/claude-skills:issue-list
  ↓ 未解決 issue の一覧を確認
/claude-skills:issue-plan
  ↓ issue を選択して plan を作成（cycle は実行しない。レビュー・議論用）
/claude-skills:issue-cycle
  ↓ issue を選択して plan → cycle で自動解決
/claude-skills:issue-close {slug}
  ↓ archives/ に移動して issue-status.md から削除
```

plan 実行中にスコープ外の問題を発見したら `/claude-skills:issue-create` で記録し、
後から `/claude-skills:issue-cycle` で plan → cycle に繋げて解決する。

### アイデアの壁打ち

```
/claude-skills:brainstorm ○○について壁打ちしたい
  ↓ 議論のみ（ファイル編集禁止）の壁打ちセッション
/claude-skills:brainstorm-wrap
  ↓ docs/ideas/{slug}.md にアイデアをメモ化
/claude-skills:brainstorm-list
  ↓ 過去のアイデア一覧を確認
/claude-skills:brainstorm-plan
  ↓ アイデアを plan に変換して cycle 実行へ

# 一晩寝かせた後、再議論したくなったら
/claude-skills:brainstorm-resume {slug}
  ↓ 既存メモを読み込んで壁打ち再開
/claude-skills:brainstorm-wrap
  ↓ メモを上書き更新
```

「何を作るか」を決める前の発散フェーズ。壁打ち中は LLM が勝手に実装に走らない。
アイデアは何度でも壁打ちし直せる。

### ドキュメント整合性チェック

```
/claude-skills:doc-check          # 直近5コミットの変更を対象
/claude-skills:doc-check 10       # 直近10コミット
/claude-skills:doc-check all      # プロジェクト全体
```

ドキュメント内のテーブル・ツリー図・パス参照等を実態と突き合わせ、
不整合を自動修正する。意味的な整合性もLLMで検証。

### 途中から再開

```
/claude-skills:plan-resume
```

`docs/status.md` から現在のセッションを読み込んで続きから開始する。

## Codex CLI 対応

本リポジトリはデュアルプラグイン構造を採用し、Claude Code と Codex CLI の両方で同じワークフローを利用できる。

### Codex CLI 用スキル

`codex-skills/` ディレクトリに Codex CLI ネイティブのスキルを配置。
ツール参照を Codex CLI のネイティブ API（`spawn_agent`, `send_message`, `apply_patch`, `shell` 等）に変換済み。

| スキル | 説明 |
|--------|------|
| `commit` | 変更を分析し論理単位で自動コミット |
| `investigate` | 読み取り専用の問題調査・構造化レポート |
| `plan` | 計画ファイルと status.md の管理 |
| `plan-reviewer` | 6-7観点並行レビュー |
| `issue` | スコープ外の問題を記録・管理 |
| `iterate` | サイズ適応型の軽量改善ループ |
| `cycle` | refine→implement 全自動サイクル |
| `team-cycle` | チーム議論型レビュー + 自動実装 |

### Codex CLI での呼び出し

```
$plan ○○機能を追加したい
$cycle
$commit
$iterate ○○を修正して
$investigate ○○が動かない原因を調べて
```

### 共有リソース

ツール非依存の references（テンプレート、チェックリスト等）は `codex-skills/` から `skills/` へのシンボリックリンクで共有し、メンテナンスコストを最小化している。

## ファイル構成

```
.claude-plugin/
  plugin.json         # Claude Code Plugin マニフェスト
commands/             # Claude Code 用スラッシュコマンド
skills/               # Claude Code 用スキル
├── plan/             # 計画管理スキル + テンプレート
├── plan-reviewer/    # 7観点レビュー + Codex セカンドオピニオン
├── commit/           # 自動コミットスキル
├── codebase-review/  # 4エージェント並行レビュー
├── generate-review-rules/
├── iterate/          # サイズ適応型軽量改善ループ
├── doc-check/        # ドキュメント整合性検証・自動修正
├── doc-write/        # LLMとのやり取り・調査結果のドキュメント化
├── issue/            # issue 管理（記録・一覧・cycle連携・クローズ）
├── parallel-cycle/   # 指示分解 + 並行 cycle 実行オーケストレータ
├── investigate/      # 読み取り専用の問題調査・構造化レポート
├── brainstorm/       # アイデアの壁打ち・発散→収束→plan化
├── team-cycle/       # AgenticTeam チーム議論型レビュー + 自動実装
├── team-plan/        # AgenticTeam チーム議論型の計画作成
├── team-brainstorm/  # AgenticTeam チーム議論型ブレインストーミング
├── skill-improve/    # セッションデータ分析によるスキル改善メタスキル
├── doc-audit/        # docs 内アーティファクトの横断スキャン・不整合修復
├── migrate-cycles-to-plans/ # cycles → plans マイグレーション
└── shared/           # 複数スキルが共有するリソース（ロール定義等）
codex-skills/         # Codex CLI 用スキル
├── commit/           # 自動コミット（Codex 版）
├── investigate/      # 読み取り専用調査（Codex 版）
├── plan/             # 計画管理（Codex 版）
├── plan-reviewer/    # 6-7観点レビュー（Codex 版）
├── issue/            # issue 管理（Codex 版）
├── iterate/          # 軽量改善ループ（Codex 版）
├── cycle/            # 全自動サイクル（Codex 版）
├── team-cycle/       # チーム議論型（Codex 版）
└── shared/           # Codex 固有の共有リソース
rules/                # グローバルルール（手動コピーが必要）
AGENTS.md             # Codex CLI 用プロジェクト説明
CLAUDE.md             # Claude Code 用プロジェクト説明
install.sh            # レガシーインストーラ（非推奨）
```
