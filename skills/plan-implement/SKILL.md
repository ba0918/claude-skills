---
name: plan-implement
description: 実装計画の全ステップを TDD（RED → GREEN → REFACTOR）の implement → review ループで自動実装する。ステップごとにレビュー・ステータス更新・コミットを行う。cycle の Phase 2 としても単体でも使える。「plan-implement」「計画を実装して」「この計画を自動実装」で起動。
---

# Plan Implement

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

実装計画の自動実装ループを実行する。
オーケストレータとして振る舞い、実装 → レビュー → フィードバック反映を自走で繰り返す。

次のいずれかに該当する場合、委譲や他スキル起動の代わりに当該役割を自分がインラインで実行してよい:
サブエージェントを起動できない / 他スキル（`claude-skills:plan` 等）が対象プロジェクトを正しく指せない /
変更が数行規模の trivial なステップで委譲のオーバーヘッドが見合わない。
インラインでステータス更新する場合は status.md と計画ファイルを直接編集する。
インラインでもレビュー（Step B）は独立した批判的レビュワーの立場を取り、実装時の判断を前提とせず
コードとテストだけを読み直して評価し、指摘の有無を BLOCK / WARN / INFO で明示すること。

## パラメータ

- 引数: 追加の指示（特定ステップの指定、スコープの限定など）

## Phase 0: 計画の読み込みとステータス更新

1. `.agents/artifacts/status.md` を読み、現在 🟡 Planning のセッションを特定する
   - 途中ステップからの再入（既に 🔵 Implementing のセッション）も正常系として扱う
2. 該当する計画ファイル (`.agents/artifacts/plans/` 内) を読み込む
3. 計画の全体像・ステップ一覧・現在の進捗を把握する（🟢 Done のステップは再実装しない）
4. 引数に特定ステップの指定があればそこから開始する
5. **ステータスを 🔵 Implementing に更新する**（スキル `claude-skills:plan` を起動し status 更新。既に 🔵 Implementing なら更新不要）

## Phase 1-N: 実装ループ（ステップごとに繰り返し）

各ステップについて以下を実行する:

### Step A: TDD 実装（Red → Green → Refactor）

サブエージェントで実装エージェントを起動する。以下の TDD サイクルを**厳守**させる。

**TDD 契約参照**: [tdd-contract.md](../shared/references/tdd-contract.md) に従い、テストファースト（RED → GREEN → REFACTOR）で進めること。

#### Red（テスト先行）
1. 計画の該当ステップの要件からテストを**先に**書く
   - 期待する入出力、エッジケース、エラーパスをテストで表現する
   - 対象プロジェクトの `AGENTS.md` / `CLAUDE.md` と、共有の [design-principles.md](../shared/references/design-principles.md) を遵守する
   - [testing-anti-patterns.md](../shared/references/testing-anti-patterns.md) のアンチパターンを避ける
2. テストを実行し、**失敗することを確認する**
   - コンパイルエラーは許容（未実装の型・関数への参照）
   - 既存テストが壊れていないことも確認する
   - **各ステップの RED の失敗出力の要点（エラー種別・メッセージ）を記録し、完了報告に含める**（「RED 確認」とだけ書くのは不可）

#### Green（最小実装）
3. テストを通すための**最小限の実装**を書く
   - 過剰な抽象化や先回り実装はしない
   - まずテストが全て通ることを最優先にする
4. テストを実行し、**全パスを確認する**

#### Refactor（リファクタリング）
5. テストが通った状態でコードを整理する
   - 重複排除、命名改善、責務分離
   - リファクタリング後も**テストが全パスすることを確認する**

**Verification Gate**: テスト実行結果を各ステップで確認し、[verification-gate.md](../shared/references/verification-gate.md) の Gate Function に従うこと。テスト全パスのエビデンス（コマンド出力）を結果ファイルに含めること。

実装結果を受け取る。

### Step B: レビュー

1. サブエージェントでレビューエージェントを起動する
   - **厳しめの評価基準**を与える。批判的な立場を取らせる
   - **`.claude/review-rules.md` が存在する場合、必ず読み込んでレビュー基準として使用する**
   - `.claude/review-rules.md` がない場合は以下のデフォルト観点を使用:
     - 対象プロジェクト固有の指示と [design-principles.md](../shared/references/design-principles.md) への違反がないか
     - 責務の混在がないか
     - テストが十分か（カバレッジ、エッジケース）
     - パフォーマンス・メモリ効率に問題がないか
     - セキュリティ上の懸念がないか
     - コード重複・デッドコードがないか
   - 指摘を severity (BLOCK / WARN / INFO) で分類させる（定義は
     [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md) 準拠）
   - **指摘ゼロの場合も「BLOCK / WARN / INFO: なし」と明示的に報告させる**（分類スキームを適用した証拠を残す）
2. レビュー結果を受け取る

### Step C: 判定と反映

1. レビュー結果を審議する
   - **BLOCK**: 必ず修正が必要 → Step A に戻る（修正指示を出す）
   - **WARN**: 改善が望ましい → 内容を検討し、修正するか判断する
     - 修正する場合 → Step A に戻る
     - 許容する場合 → 理由を明記して次へ
   - **INFO**: 参考情報 → 記録して次へ
2. BLOCK/WARN が残っている場合、修正エージェントを起動して対応する
3. 修正後、再度 Step B のレビューを実行する
4. **BLOCK がなくなるまでこのループを繰り返す**（Step B レビュー → Step C 修正の往復 1 回を 1 イテレーションと数え、**ステップごとに**最大 3 イテレーション）

### Step D: ステータス更新とコミット（必須 - スキップ禁止）

**ステップ完了ごとに必ず実行する。これをスキップしてはならない。**

1. スキル `claude-skills:plan` を起動し、以下を更新する:
   - 完了したステップのステータスを 🟢 Done に変更
   - 次のステップ情報を記載
   - 実装のサマリー（変更ファイル、テスト数など）を記録
2. 当該ステップの変更（実装・テスト・ステータス更新）をコミットする
   - ビルド生成物・キャッシュ（例: `__pycache__`, `node_modules`, `target`）は追跡しない。混入するなら先に ignore 設定を整備する
   - `.agents/artifacts` が Git 追跡外のプロジェクトでは、ステータス更新はコミット対象に含まれない（実装とテストのみコミットする）
3. コミットが完了してから次のステップに進む

## Phase Final: 完了処理

全ステップ完了後:

1. **変更内容全体のレビュー**をサブエージェントで実行する
   - `git diff` で全変更を確認
   - 実装計画の全課題が解決されたか網羅的に検証
   - プロジェクトのテストコマンドを実行して全パスを確認する（例: `cargo test`, `npm test`, `go test ./...` など）
   - プロジェクトの lint コマンドを実行して警告がないことを確認する（例: `cargo clippy`, `eslint`, `golangci-lint` など）。lint が設定されていないプロジェクトではスキップし、その旨を報告する
2. 最終レビューで WARN 以上の指摘があれば修正ループに戻る
3. 全て解決したら:
   - スキル `claude-skills:plan` を起動し、ステータスを 🟢 Complete に更新
   - 未コミットの変更（ステータス更新等）が残っていればコミットする
   - 実装サマリーをユーザーに提示する

## 重要なルール

- **ステータス更新は各ステップ完了時に必ず行う。後回しにしない。**
- **TDD サイクル (Red → Green → Refactor) を厳守する。実装コードより先にテストを書く。**
- **テストなしの実装は禁止。テストが書けない場合は設計を見直す。**
- **BLOCK 指摘は必ず解消してから次に進む。**
- **最大イテレーション数を超えた場合は、残存する指摘を一覧表示してユーザーに判断を仰ぐ。**
- 各エージェントには対象プロジェクトの `AGENTS.md` / `CLAUDE.md` と [design-principles.md](../shared/references/design-principles.md) の内容を必ず伝達する。
