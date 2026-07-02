# claude-skills

Claude Code / Codex CLI 両対応の自作スキル・コマンド集（デュアルプラグイン構造）。
**実装計画の作成 → レビュー → 自動実装 → セッション引き継ぎ** までのワークフローと、
**GitHub issue を起点とした self-driving ラルフループ**を提供する。

> **Features:** plan 中心ワークフロー / AgenticTeam チーム議論型レビュー /
> Codex CLI セカンドオピニオン並行 / GitHub issue 自走 polling /
> worktree 並行 cycle / 揮発型セッション引き継ぎ /
> 攻撃者視点セキュリティレビュー / 機械検証可能なデザインシステム / TDD 強制ガイド

## インストール

### Plugin としてインストール（推奨）

```bash
# マーケットプレイスを追加
claude plugin marketplace add ba0918/claude-skills

# マーケットプレイスからインストール
claude plugin install claude-skills@claude-skills

# ローカル開発（変更を即テスト）
claude --plugin-dir /path/to/claude-skills
```

Plugin としてインストールすると、コマンドは `/claude-skills:plan-create` のように名前空間付きで呼び出せる。

`--plugin-dir` でのローカルテスト中は `/reload-plugins` で変更を即反映できる。

### レガシーインストール（非推奨）

```bash
git clone https://github.com/ba0918/claude-skills.git ~/develop/claude-skills
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
| `/claude-skills:issue-polling` | `ready/` キューを self-driving 消化するラルフループ（FS adapter） |
| `/claude-skills:github-issue-create` | `claude-auto` ラベル付きの GitHub issue を作成 |
| `/claude-skills:github-issue-list` | `claude-auto` ラベル付きの issue 一覧を表示 |
| `/claude-skills:github-issue-cycle` | GitHub issue を plan → cycle → draft PR → Codex レビュー → auto merge で自走 |
| `/claude-skills:github-issue-polling` | GitHub 側の `claude-auto` issue を self-driving 消化するラルフループ（Label adapter） |
| `/claude-skills:handoff-save` | 現在のセッション状態を `docs/handoff/` に構造化保存 |
| `/claude-skills:handoff-restore` | 保存されたハンドオフを読み込み → 自動削除（揮発型） |
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
| `/claude-skills:attack-review` | コードベースを攻撃者視点で6エージェント + Codex 並行レビュー（リスクマトリクス分類） |
| `/claude-skills:attack-review-server` | サーバーサイド特化の攻撃者視点レビュー |
| `/claude-skills:attack-review-client` | クライアントサイド特化の攻撃者視点レビュー |
| `/claude-skills:design-guide` | 対話型ディスカバリーで DESIGN.md（デザインシステム定義）を作成 |
| `/claude-skills:design-guide-update` | 既存の DESIGN.md を対話的に部分修正 |
| `/claude-skills:design-guide-mockup` | DESIGN.md のトークンに基づくモックアップを生成（Base Design 承認ゲート付き） |
| `/claude-skills:design-scaffold` | DESIGN.md → tokens.json + tokens.css + lint 設定を scaffold 生成 |
| `/claude-skills:design-generate` | ページ定義 + コンポーネントカタログに基づく制約付きページ生成 |
| `/claude-skills:design-validate` | Static Lint → Visual Regression → Rubric Judge の多段階検証ゲート |
| `/claude-skills:design-lint` | コードベースをデザイントークンで lint（DL001-204 を機械検出） |
| `/claude-skills:mockup-diff` | 承認済みモックアップ vs 実アプリのスクショ比較で実装差異を検出・修正 |
| `/claude-skills:tdd` | TDD (RED-GREEN-REFACTOR) サイクルをガイドし、テストファースト開発を強制 |
| `/claude-skills:debug` | 4フェーズ構造化デバッグ（根本原因特定 → 修正まで実行） |
| `/claude-skills:problem-solving` | 行き詰まった時の思考ツール集（simplify/collide/invert/scale/pattern） |
| `/claude-skills:codex-sync` | Claude 版スキルを Codex 版へ自動移植・差分同期（port / sync / 未同期スキャン） |

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
| `issue` | スコープ外の問題を記録・管理し plan → cycle に繋げる。polling ワークフローで `ready/` キューを self-driving 消化するラルフループも提供 |
| `github-issue` | GitHub issue を起点に polling → draft PR → Codex レビュー → auto merge まで自走。ラベルベース状態機械 + 多重防御 atomic claim + fail-closed Codex ゲート |
| `handoff` | セッション間のコンテキスト引き継ぎ。save で現在のコンテキストを `docs/handoff/` に構造化保存、restore で次セッションが読込→自動削除（揮発型） |
| `parallel-cycle` | 自然言語の指示を分解し、worktree で並行 cycle 実行・自動マージ |
| `investigate` | 問題を読み取り専用で調査し、構造化レポートを出力。ファイル編集は一切行わない |
| `sweep-fix` | 指定範囲の問題検出 → 全体への横展開検索 → 文脈検証（偽陽性除去）→ 一括修正の find-one-fix-all 型スキル。コマンドなし（`/claude-skills:sweep-fix` で直接起動） |
| `brainstorm` | アイデアの壁打ちに特化。発散→収束→plan化の導線を提供。壁打ち中はファイル編集禁止 |
| `team-cycle` | AgenticTeam によるチーム議論型レビュー + 自動実装サイクル。4専門レビュワーが議論して計画品質を向上 |
| `team-plan` | AgenticTeam によるチーム議論型の計画作成。4専門家が議論しながら多角的な実装計画を作成 |
| `team-brainstorm` | AgenticTeam によるチーム議論型ブレインストーミング。4思考スタイル（Challenger/Explorer/Connector/Grounded）で多角的にアイデアを発散 |
| `skill-improve` | セッションデータからスキル使用時の摩擦を検出・分析し、データ駆動でスキル改善を実行するメタスキル |
| `doc-audit` | docs 内の全アーティファクトを横断スキャンし、不整合を検出・自動修復 |
| `migrate-cycles-to-plans` | `docs/cycles/` → `docs/plans/` のマイグレーション。ディレクトリ移動 + 全参照の一括置換 |
| `attack-review` | 6エージェント + Codex 並行の攻撃者視点レビュー。リスクマトリクス（Likelihood×Impact）で脅威を分類。server/client/full モード + 言語別攻撃プロファイル |
| `design-guide` | 対話型ディスカバリーで DESIGN.md（Google Stitch フォーマット準拠）を生成。Session / Update / Mockup の3ワークフロー |
| `design-scaffold` | DESIGN.md から machine-readable なデザインシステム（tokens.json + tokens.css + lint-config + React theme）を scaffold 生成 |
| `design-generate` | ページ定義 + コンポーネントカタログに基づく制約付きページ生成。LLM の自由度をコンテンツのみに限定し再現性を保証 |
| `design-validate` | Static Lint → Visual Regression (Playwright) → Rubric Judge (LLM) の多段階検証ゲート。weighted average で合否判定 |
| `design-lint` | `.design/tokens.json` に基づくデザイントークン違反の機械検出（DL001-006 トークン / DL101-103 コンポーネント / DL201-204 ページ構成）。CI 組み込み可 |
| `mockup-diff` | 承認済みモックアップ HTML vs 実行中アプリのスクショ比較で実装差異を検出・修正。spacing/font/layout のラストワンマイル担当 |
| `test-driven-development` | TDD (RED-GREEN-REFACTOR) の対話型ガイド。各フェーズで Bash テスト実行を要求し、テストファーストを強制 |
| `systematic-debugging` | 4フェーズ構造化デバッグ（Root Cause Investigation → Pattern Analysis → Hypothesis & Testing → Implementation）。3回失敗ルールでアーキテクチャ問題を検出 |
| `problem-solving` | 行き詰まった時の思考ツール集。5サブワークフロー（simplify/collide/invert/scale/pattern）で多角的アプローチ。ファイル編集禁止 |
| `codex-sync` | Claude 版スキルを Codex 版へ自動移植・差分同期するメタスキル（本リポジトリ専用）。3層変換ルールを適用し、要判断箇所は人間にエスカレーション。validate → 同期台帳更新まで一気通貫 |

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

### Issue 管理（local file ベース）

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

### Self-Driving Polling Loop（ラルフループ）

`issue` と `github-issue` スキルはどちらも「claim → cycle → mark_done/mark_failed」の
状態機械ループ（ラルフループ）を提供する。`/loop` コマンドと組み合わせて常駐運用可能。

```
# ローカル issue を消化（FS adapter）
/claude-skills:issue-polling --loop --max-parallel 2

# GitHub issue を消化（Label adapter）
/claude-skills:github-issue-polling --loop --max-parallel 4
```

共通契約 `skills/shared/references/polling-pattern.md` に state machine / interface /
純関数 / 安全ブレーキを集約し、**state adapter（FS / GitHub Label）を DI で差し替える**
構造。以下の多重防御で bypass-permissions 環境でも安全に稼働する:

- **Kill file 2 系統**: `<state_root>/.STOP`（graceful）/ `.STOP.hard`（即時）
- **3 重ガード**: `max_iter` / `max_wallclock` / `failed_streak`
- **Initial dry-run**: 初回起動時は強制 dry-run で claim 計画のみ出力
- **Atomic claim 3 段防御**: flock → label/assignee → re-verify（race condition 排除）
- **Fail-closed**: Codex 不在・unsupported FS・state_root 衝突等で polling abort

### GitHub Issue 自走ワークフロー

```
/claude-skills:github-issue-create "○○を修正したい" --label claude-auto
  ↓ GitHub 上に claude-auto ラベル付きの issue を作成
/claude-skills:github-issue-polling --loop
  ↓ polling が issue を claim → cycle → draft PR → Codex レビュー → auto merge
  ↓ 成功: issue close + PR merge
  ↓ 失敗: claude-failed-transient/permanent ラベル付与で人間判断待ち
```

オフラインの local issue と異なり、GitHub 上の issue を正本として扱う。
**Codex レビューは merge 必須ゲート**（`codex_required_for_merge=true` ロック）で、
Codex 不在時は fail-closed で merge しない安全設計。

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

### セッション間の引き継ぎ（Handoff）

コンテキストウィンドウが肥大化してきた時や、明示的に次セッションへ引き継ぎたい時に使う揮発型のコンテキスト保存。

```
/claude-skills:handoff-save
  ↓ 現在の作業コンテキストを docs/handoff/ に構造化保存
  ↓ 次に検討すべきこと・未解決事項・直近の意思決定を明示的に書き出す

# セッション終了 → /clear → 新セッション

/claude-skills:handoff-restore
  ↓ docs/handoff/ の内容を読み込んで作業再開
  ↓ 読み込み後は自動削除（揮発型 — 一度限りの引き継ぎ）
```

`plan-resume` が「計画の進捗」を追跡するのに対し、`handoff` は **計画外の文脈**（設計判断の背景、懸念事項、検討中の選択肢等）を保存する。一度 restore したら消えるので、**長期ドキュメントではない**。

### 攻撃者視点セキュリティレビュー

```
/claude-skills:attack-review           # テックスタックから server/client/full を自動検出
/claude-skills:attack-review-server    # サーバーサイド特化（Injection / AuthN・AuthZ / Data / Infra / Business Logic）
/claude-skills:attack-review-client    # クライアントサイド特化（XSS / CSRF / Client Attack 等）
```

6つの専門エージェント + Codex が並行で攻撃者視点レビューを実行し、
リスクマトリクス（Likelihood × Impact）で脅威を分類する。スコアではなく
**攻撃シナリオベース**で報告するのが `codebase-review` との違い。
言語検出共通契約（`lang-detect.md`）に基づき、言語別の攻撃プロファイルが注入される。

### デザインシステムワークフロー

```
/claude-skills:design-guide
  ↓ 対話型ディスカバリーで DESIGN.md を生成
/claude-skills:design-scaffold
  ↓ DESIGN.md → .design/tokens.json + tokens.css + lint 設定に変換
/claude-skills:design-guide-mockup
  ↓ schema ベースのモックアップ生成 → 自動 lint → Base Design 承認（Human-in-the-Loop Once）
/claude-skills:design-generate
  ↓ ページ定義 + カタログに基づく制約付きページ生成
/claude-skills:design-validate
  ↓ Static Lint → Visual Regression → Rubric Judge の多段階検証
/claude-skills:design-lint
  ↓ トークン違反（DL001-204）を機械検出（CI 組み込み可）
/claude-skills:mockup-diff
  ↓ 承認済みモックアップ vs 実アプリのスクショ比較で実装差異を修正
```

**人間の承認は Base Design の1回だけ**で、以降の検証はすべて機械的に行う設計。
共通契約は `skills/shared/references/design-system-contract.md` に集約されている。

### TDD・デバッグ・問題解決

```
/claude-skills:tdd ○○機能をテストファーストで実装したい
  ↓ RED → GREEN → REFACTOR を各フェーズのテスト実行付きで強制

/claude-skills:debug ○○が動かない
  ↓ 根本原因調査 → パターン分析 → 仮説検証 → 修正の4フェーズ

/claude-skills:problem-solving 設計に行き詰まった
  ↓ simplify / collide / invert / scale / pattern の思考ツールで打開
```

`investigate` が読み取り専用の調査で止まるのに対し、`debug` は修正まで実行する。
`problem-solving` は brainstorm セッション中からも呼び出せる（ファイル編集禁止）。

## 使い方のコツ・ハマりどころ

このスキル集は構造化されたワークフローを前提に設計されているので、いくつか癖がある。
初めて使う時にハマりやすいポイントを整理した。

### 1. plan は必ず `docs/plans/` 配下に置く

`docs/cycles/` ではない（旧パス — `migrate-cycles-to-plans` で移行済み）。
`plan-create` は自動的に `docs/plans/{timestamp}_{slug}.md` に配置する。
**手で別の場所に作ると cycle / plan-implement が見つけられない**。

### 2. `docs/status.md` は手動編集しない

`plan` スキルが自動管理する。Current Session と Session History の 2 セクション構成で、
cycle 完了時に自動アーカイブされる。手動編集するとパーサーが壊れることがある。

### 3. `issue` と `github-issue` は別物

- **`issue`**: ローカルファイル (`docs/issues/`) ベース。オフライン・個人作業向け
- **`github-issue`**: GitHub 上の issue を正本として扱う。チーム作業・自走運用向け

polling でも FS adapter / Label adapter と実装が分かれている。両者とも共通契約
`skills/shared/references/polling-pattern.md` に準拠している。

### 4. `cycle` vs `team-cycle` の使い分け

- **`cycle`**: 単独の review → implement ループ。軽量で速い
- **`team-cycle`**: 4 ロール（Security / Performance / Architect / Pragmatist）が
  議論しながらレビュー → 合意形成 → 実装。**重要な変更・複雑な設計向け**

`team-cycle` は実験的機能フラグが必要:

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

未設定だと起動時に中断する。

### 5. `brainstorm` はファイル編集禁止

発散フェーズでは LLM が勝手に実装に走らないよう、**brainstorm セッション中はファイル
編集が禁止されている**。議論に集中して、結論が出たら `brainstorm-wrap` でメモ化 →
`brainstorm-plan` で plan 化 → `cycle` で実装という段階的な流れを守る。

### 6. `handoff` は揮発型（一度限り）

`handoff-restore` すると保存ファイルは自動削除される。長期保存したいなら `docs/` 配下
に別途ドキュメント化すること。`plan-resume` とは別物で、計画外の文脈（検討中の選択肢・
設計判断の背景）を次セッションに渡す用途。

### 7. polling ループは必ず kill file 2 系統を用意

bypass-permissions 環境でラルフループを回す場合、暴走防止のため以下を覚えておく:

```bash
touch <state_root>/.STOP        # graceful stop（現 tick 完了後に停止）
touch <state_root>/.STOP.hard   # hard stop（即時停止）
```

初回起動時は `<state_root>/.polling-initialized` が存在しないため、**強制 dry-run**
で claim 計画のみ出力される。本番実行は 2 回目以降。

### 8. 並列実行は worktree ベース

`parallel-cycle` は `EnterWorktree`/`ExitWorktree` で各 cycle を物理的に分離する。
**ファイル直交性チェック**が走り、影響ファイルが重なる plan は並列化されない。
部分成功も許容（成功分のみマージ、失敗ブランチは保持）。

### 9. plugin.json の version bump 忘れ注意

新スキルを追加してマーケットプレイスに公開する時、`.claude-plugin/plugin.json` の
version を上げないと**インストーラがスキルを認識しない**。PATCH/MINOR/MAJOR を
変更内容に応じて適切に bump すること。

### 10. Codex セカンドオピニオンは fail-closed

`plan-reviewer` / `codebase-review` / `iterate` / `brainstorm` / `github-issue` は
Codex CLI をセカンドオピニオンとして並行呼び出しする。**Codex 不在でも処理は継続**
するが、`github-issue` の merge ゲートでは `codex_required_for_merge=true` がロック
されており、Codex 不在時は auto merge しない（人間判断待ち）。

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
| `plan-reviewer` | 7観点並行レビュー（UI/UX 条件付き） |
| `codebase-review` | 4エージェント並行によるコードベース全体レビュー |
| `attack-review` | 6エージェント並行の攻撃者視点レビュー（Codex セカンドオピニオンは冗長なため除外） |
| `issue` | スコープ外の問題を記録・管理 |
| `iterate` | サイズ適応型の軽量改善ループ |
| `cycle` | refine→implement 全自動サイクル |
| `team-cycle` | チーム議論型レビュー + 自動実装 |
| `parallel-cycle` | 指示分解 + git worktree 並行 cycle 実行（完全 headless） |
| `handoff` | セッション間コンテキスト引き継ぎ（save/restore/list、揮発型） |
| `brainstorm` | アイデアの壁打ち・発散→収束→plan化（Codex セカンドオピニオンは冗長なため除外） |
| `problem-solving` | 行き詰まり打開の思考ツール集（5サブワークフロー、apply_patch 禁止） |

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
  marketplace.json    # マーケットプレイス定義（version は plugin.json と同期必須）
.github/workflows/
  validate.yml        # リポジトリ整合性チェック CI
commands/             # Claude Code 用スラッシュコマンド（薄いラッパー）
skills/               # Claude Code 用スキル（ロジック本体）
├── plan/             # 計画管理スキル + テンプレート + docs/status.md 管理
├── plan-reviewer/    # 7観点レビュー + Codex セカンドオピニオン
├── commit/           # 自動コミットスキル
├── codebase-review/  # 4エージェント + Codex 並行によるコードベース全体レビュー
├── attack-review/    # 6エージェント + Codex 並行の攻撃者視点レビュー
├── generate-review-rules/ # プロジェクト固有レビュールール生成
├── iterate/          # サイズ適応型軽量改善ループ
├── doc-check/        # ドキュメント整合性検証・自動修正
├── doc-write/        # LLMとのやり取り・調査結果のドキュメント化
├── issue/            # local issue 管理（記録・一覧・cycle連携・close・polling）
├── github-issue/     # GitHub issue 自走（Label adapter + polling + Codex gate）
├── handoff/          # セッション間コンテキスト引き継ぎ（save/restore、揮発型）
├── parallel-cycle/   # 指示分解 + worktree 並行 cycle 実行オーケストレータ
├── investigate/      # 読み取り専用の問題調査・構造化レポート
├── sweep-fix/        # find-one-fix-all: 局所の問題を全体へ横展開検索・文脈検証・一括修正
├── brainstorm/       # アイデアの壁打ち・発散→収束→plan化（ファイル編集禁止）
├── design-guide/     # 対話型ディスカバリーで DESIGN.md 生成（Session/Update/Mockup）
├── design-scaffold/  # DESIGN.md → tokens.json + tokens.css + lint 設定
├── design-generate/  # 制約付きページ生成（自由度はコンテンツのみ）
├── design-validate/  # lint → visual regression → rubric judge の多段階検証
├── design-lint/      # デザイントークン違反の機械検出（DL001-204）
├── mockup-diff/      # モックアップ vs 実アプリのスクショ比較・修正
├── test-driven-development/ # TDD (RED-GREEN-REFACTOR) 強制ガイド
├── systematic-debugging/    # 4フェーズ構造化デバッグ
├── problem-solving/  # 行き詰まり打開の思考ツール集（5サブワークフロー）
├── codex-sync/       # Claude 版 → Codex 版の自動移植・差分同期メタスキル
├── team-cycle/       # AgenticTeam チーム議論型レビュー + 自動実装
├── team-plan/        # AgenticTeam チーム議論型の計画作成
├── team-brainstorm/  # AgenticTeam チーム議論型ブレインストーミング
├── skill-improve/    # セッションデータ分析によるスキル改善メタスキル
├── doc-audit/        # docs 内アーティファクトの横断スキャン・不整合修復
├── migrate-cycles-to-plans/ # cycles → plans マイグレーション
└── shared/references/     # 複数スキルが共有するリソース
    ├── team-config.md            # AgenticTeam ロール定義（team-plan/cycle/brainstorm 共有）
    ├── severity-and-verdicts.md  # 重大度・判定基準（team-plan/cycle 共有）
    ├── codex-integration.md      # Codex セカンドオピニオン呼び出しパターン
    ├── polling-pattern.md        # polling 共通契約（state machine / interface / 純関数 / 安全ブレーキ）
    ├── lang-detect.md            # 言語・フレームワーク検出契約（attack-review 等が共有）
    ├── tdd-contract.md           # TDD 共通契約（cycle/iterate/tdd が共有）
    ├── verification-gate.md      # 完了前検証ゲート契約（証拠なし完了主張の防止）
    ├── design-system-contract.md # デザインシステム検証の共通契約
    ├── orchestration-patterns.md # エージェントオーケストレーション設計契約（endorsed/アンチパターン）
    └── skill-authoring.md        # スキル執筆仕様（frontmatter 契約 / 執筆原則 / チェックリスト）
codex-skills/         # Codex CLI 用スキル（Codex ネイティブ API に変換）
├── commit/           # 自動コミット（Codex 版）
├── investigate/      # 読み取り専用調査（Codex 版）
├── plan/             # 計画管理（Codex 版）
├── plan-reviewer/    # 7観点レビュー（Codex 版）
├── codebase-review/  # コードベース全体レビュー（Codex 版）
├── attack-review/    # 攻撃者視点レビュー（Codex 版、6エージェントのみ）
├── issue/            # issue 管理（Codex 版）
├── iterate/          # 軽量改善ループ（Codex 版）
├── cycle/            # 全自動サイクル（Codex 版）
├── team-cycle/       # チーム議論型（Codex 版）
├── parallel-cycle/   # worktree 並行 cycle（Codex 版、完全 headless）
├── handoff/          # セッション引き継ぎ（Codex 版、apply_patch ベース）
├── brainstorm/       # アイデア壁打ち（Codex 版、セカンドオピニオンなし）
├── problem-solving/  # 行き詰まり打開の思考ツール集（Codex 版）
├── shared/           # Codex 固有の共有リソース（tool-mapping.md 等）
└── sync-manifest.json # Claude⇔Codex 同期台帳（ソースの sha256 を記録、CI で検証）
rules/                # グローバルルール（Plugin では手動コピーが必要）
├── design-principles.md      # testability を supreme principle とする設計原則
└── testing-anti-patterns.md  # テストアンチパターン集（Iron Laws + Gate Functions）
scripts/              # リポジトリ整合性バリデータ（CI とローカル両用）
  validate_repo.py    # リンク切れ・対応表・バージョン同期・ドキュメントドリフト検出
  test_validate_repo.py
AGENTS.md             # Codex CLI 用プロジェクト説明
CLAUDE.md             # Claude Code 用プロジェクト説明
CHANGELOG.md          # バージョン履歴（plugin.json から分離）
install.sh            # レガシーインストーラ（非推奨）
```

## リポジトリ整合性チェック（CI）

markdown が「コード」であるこのリポジトリでは、リンク切れ・対応表のズレ・
ドキュメントドリフトが実質的なバグになる。`scripts/validate_repo.py` が以下を機械検証し、
GitHub Actions（`.github/workflows/validate.yml`）で push / PR ごとに実行される:

- 壊れた symlink の検出（codex-skills の共有リンク切れ防止）
- 全スキルの `SKILL.md` 存在 + frontmatter（`name` / `description`）検証
- `commands/*.md` の frontmatter `description` 検証
- SKILL.md / commands 内の相対 `.md` リンクの実在チェック
- CLAUDE.md のコマンド対応表 ⇔ `commands/` 実ファイルの双方向一致
- README.md / AGENTS.md のスキル名カバレッジ（ドリフト検出）
- `plugin.json` ⇔ `marketplace.json` のバージョン同期
- **Claude 版 ⇔ Codex 版スキルの同期台帳**（`codex-skills/sync-manifest.json`）—
  Codex 版は意図的に内容が異なる移植版なので diff 比較はせず、sync 時点の
  ソース（`skills/<name>/SKILL.md`）の sha256 を台帳に記録。ソースが変わったのに
  台帳が古いままなら「未同期」として CI が fail し、片側だけ更新するサイレント
  ドリフトを防ぐ

ローカル実行:

```bash
python3 scripts/validate_repo.py                          # 整合性チェック
python3 -m unittest discover -s scripts -p 'test_*.py'    # バリデータ自体のテスト
python3 scripts/validate_repo.py --update-manifest        # Codex 版へ反映後、同期台帳を更新
```
