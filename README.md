# claude-skills

Claude Code 用の自作スキル・コマンド集。
実装計画の作成からレビュー・自動実装までのワークフローを提供する。

## インストール

```bash
git clone <repo-url> ~/develop/claude-skills
cd ~/develop/claude-skills
./install.sh
```

`~/.claude/commands/` と `~/.claude/skills/` に symlink が張られる。

## コマンド一覧

| コマンド | 説明 |
|----------|------|
| `/plan-create` | 実装計画を新規作成（`docs/cycles/` に配置） |
| `/plan-review` | 計画を6観点でレビュー |
| `/plan-refine` | レビュー → 修正ループ（PASS まで繰り返す） |
| `/plan-implement` | 実装計画を自動実装（implement → review ループ） |
| `/plan-resume` | 前回のセッションを引き継ぐ |
| `/plan-status` | 計画のステータスを更新 |
| `/cycle` | refine → implement → サマリー生成を全自動で回す |
| `/commit` | 変更内容を分析し、論理単位で自動コミット |
| `/iterate` | cycle 後の追加指示を軽量改善ループで実行 |
| `/doc-check` | ドキュメントとコードの整合性を検証・自動修正 |
| `/issue-create` | スコープ外の問題を issue として記録 |
| `/issue-list` | 未解決 issue の一覧を表示 |
| `/issue-cycle` | issue を選択して plan → cycle で解決 |
| `/issue-close` | issue をクローズしてアーカイブ |
| `/parallel-cycle` | 指示を分解→並行 cycle 実行→自動マージ |

## スキル一覧

| スキル | 説明 |
|--------|------|
| `plan` | 計画ファイルと `docs/status.md` の管理 |
| `plan-reviewer` | 6観点（実現可能性・セキュリティ・性能・設計・網羅性・代替案）の並行レビュー |
| `codebase-review` | 4エージェント並行によるコードベース全体レビュー（100点満点） |
| `generate-review-rules` | プロジェクト固有のレビュールール自動生成 |
| `commit` | 変更を分析し論理単位で自動コミット（確認なし即実行） |
| `iterate` | サイズ適応型の軽量改善ループ（cycle より軽く、直接作業より安全） |
| `doc-check` | ドキュメントとコードベースの整合性検証・自動修正 |
| `issue` | スコープ外の問題を記録・管理し plan → cycle に繋げる |
| `parallel-cycle` | 自然言語の指示を分解し、worktree で並行 cycle 実行・自動マージ |

## 基本ワークフロー

### 手動サイクル

```
/plan-create ○○機能を追加したい
  ↓ docs/cycles/{timestamp}_{slug}.md が生成される
/plan-refine
  ↓ レビュー → 修正を PASS まで繰り返す
/plan-implement
  ↓ ステップごとに TDD で実装 → レビュー → コミット
/plan-status 完了
```

### 全自動サイクル

```
/cycle docs/cycles/20260313_feature-x.md
```

refine（最大4ラウンド）→ implement（ステップごとコミット）→ サマリー生成を
Agent に委譲して全自動で回す。ヘッドレス実行対応。

### cycle 後の追加修正

```
/iterate ○○の挙動をちょっと変えて
```

タスクサイズを自動判定し、小さければ軽量ループ（実装→簡易レビュー）、
大きければ plan 切り出しを提案する。変更は直近の計画ファイルに追記される。

### Issue 管理

```
/issue-create ○○の処理でエラーハンドリングが不足している
  ↓ docs/issues/{date}_{slug}.md と issue-status.md が生成される
/issue-list
  ↓ 未解決 issue の一覧を確認
/issue-cycle
  ↓ issue を選択して plan → cycle で自動解決
/issue-close {slug}
  ↓ archives/ に移動して issue-status.md から削除
```

plan 実行中にスコープ外の問題を発見したら `/issue-create` で記録し、
後から `/issue-cycle` で plan → cycle に繋げて解決する。

### ドキュメント整合性チェック

```
/doc-check          # 直近5コミットの変更を対象
/doc-check 10       # 直近10コミット
/doc-check all      # プロジェクト全体
```

ドキュメント内のテーブル・ツリー図・パス参照等を実態と突き合わせ、
不整合を自動修正する。意味的な整合性もLLMで検証。

### 途中から再開

```
/plan-resume
```

`docs/status.md` から現在のセッションを読み込んで続きから開始する。

## ファイル構成

```
commands/           # スラッシュコマンド
skills/
├── plan/           # 計画管理スキル + テンプレート
├── plan-reviewer/  # 6観点レビュー + チェックリスト
├── commit/         # 自動コミットスキル
├── codebase-review/ # 4エージェント並行レビュー
├── generate-review-rules/
├── iterate/        # サイズ適応型軽量改善ループ
├── doc-check/      # ドキュメント整合性検証・自動修正
├── issue/          # issue 管理（記録・一覧・cycle連携・クローズ）
└── parallel-cycle/ # 指示分解 + 並行 cycle 実行オーケストレータ
install.sh          # ~/.claude/ に symlink を張る
```
