---
name: systematic-debugging
description: 4フェーズ構造化デバッグスキル。根本原因を特定してから修正する。investigate（調査のみ）の補完として修正まで実行する。「debug」「デバッグ」「バグ修正」「なぜ壊れる」で起動。
---

# Systematic Debugging

4フェーズの構造化デバッグスキル。ランダムな修正を防ぎ、根本原因の特定を義務付ける。

### 他スキルとの差別化

- **investigate との違い**: investigate は読み取り専用の調査。本スキルは調査 + 修正まで実行する。investigate の出力を入力として受け付ける
- **cycle / iterate との違い**: cycle/iterate は計画ベースの実装。本スキルはバグ・問題の構造化された解決に特化

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

Phase 1 を完了するまで、修正を提案してはならない。

## Phase 1: Root Cause Investigation

**修正の提案を一切行わないこと。調査のみ。**

### investigate の出力を入力として受け付ける

`$ARGUMENTS` に investigate スキルの出力ファイルパスが含まれている場合、そのレポートを読み込んでコンテキストとして使用する。Phase 1 の一部をスキップできる。

### Step 1.1: エラーメッセージの精読

1. エラーメッセージ、スタックトレースを**完全に**読む（スキップしない）
2. 行番号、ファイルパス、エラーコードを記録する
3. 警告メッセージも無視しない

### Step 1.2: 再現

1. バグを確実に再現できるか確認する
   - Bash でテストや問題のコマンドを実行する
2. 再現手順を記録する
3. 再現できない場合 → より多くのデータを収集する（推測しない）

### Step 1.3: 最近の変更の確認

```bash
git log --oneline -10
git diff HEAD~5 --stat
```

- 何が変更されたか？
- 新しい依存関係は？設定変更は？
- 環境の差異は？

### Step 1.4: データフロートレース

[references/root-cause-tracing.md](references/root-cause-tracing.md) の手法を適用する。

- バグの症状から後方にトレースする
- 各レイヤーで入出力データを検証する
- 多層システムでは診断インストルメンテーションを追加する

表示:
```
── Phase 1: Root Cause Investigation ──
Error: {error_summary}
Reproducible: {yes/no}
Recent changes: {relevant_changes}
Data flow trace: {trace_summary}
Suspected root cause: {hypothesis}
```

## Phase 2: Pattern Analysis

### Step 2.1: 動作する類似コードの発見

- Grep/Read で同じコードベース内の類似パターンを探す
- 動作している部分と壊れている部分を比較する

### Step 2.2: 差分の特定

- 動作するコードと壊れたコードの**すべての差分**をリスト化する
- 「関係ないだろう」と仮定しない — すべての差分を記録する

### Step 2.3: 依存関係の理解

- このコードが必要とする他のコンポーネントは？
- どんな設定・環境変数・前提条件があるか？

表示:
```
── Phase 2: Pattern Analysis ──
Working reference: {file_path}
Differences found: {count}
Key difference: {description}
```

## Phase 3: Hypothesis & Testing

### Step 3.1: 仮説を1つ立てる

- 「{X} が根本原因だと考える。なぜなら {Y} だから」
- 具体的に書く（曖昧にしない）

### Step 3.2: 最小限の変更でテスト

- 仮説を検証する**最小限の変更**を1つだけ行う
- 一度に複数の修正をしない
- Bash でテストを実行して結果を確認する

### Step 3.3: 検証

- 仮説が正しかった → Phase 4 へ
- 仮説が間違っていた → **新しい仮説**を立てる（追加の修正を重ねない）
- わからない → 「わからない」と認める。推測しない

表示:
```
── Phase 3: Hypothesis ──
Hypothesis: {description}
Test: {minimal_change}
Result: {confirmed/rejected}
```

## Phase 4: Implementation

### Step 4.1: 失敗するテストケースの作成

- このバグを再現する最小限のテストを書く
- TDD 契約に従う: [../shared/references/tdd-contract.md](../shared/references/tdd-contract.md)
- Bash でテストを実行し、**失敗することを確認する**

### Step 4.2: 修正の実装

- 根本原因を修正する（症状ではなく）
- **1つの変更のみ**。「ついでに」改善しない
- バンドルリファクタリング禁止

### Step 4.3: 検証

- Bash でテストを実行し、**全パスを確認する**:
  - 新しい回帰テストが通ること
  - 既存テストが壊れていないこと
- verification-gate を適用: [../shared/references/verification-gate.md](../shared/references/verification-gate.md)

表示:
```
── Phase 4: Implementation ──
Fix: {description}
Regression test: {test_name}
Tests: {pass_count}/{total_count} passed
Result: ALL PASS ✅
```

## 3回修正失敗ルール

3回以上修正を試みて失敗した場合、**自動修正を続行しない**。

AskUserQuestion で相談する:

```
⚠️ 3回の修正試行が失敗しました。根本的な設計の問題の可能性があります。

これまでの試行:
1. {試行1の概要} → {失敗理由}
2. {試行2の概要} → {失敗理由}
3. {試行3の概要} → {失敗理由}

選択肢:
1. アーキテクチャの問題を一緒に検討する（推奨）
2. 別のアプローチで修正を試す
3. 調査結果をレポートとして出力し中断する
```

- 「1」選択 → アーキテクチャの議論に移行
- 「2」選択 → Phase 1 に戻って再分析（異なるアプローチ）
- 「3」選択 → 調査レポートを表示して終了:
  ```
  ══════════════════════════════════════
  DEBUG SESSION REPORT (INCOMPLETE)
  Error: {error_summary}
  Root cause hypothesis: {best_hypothesis}
  Attempts: 3 (all failed)
  Recommendation: {architecture_review_suggestion}
  ══════════════════════════════════════
  ```

## investigate からの連携

investigate の出力を受け取る導線:

```
/claude-skills:investigate {problem}
  → 調査レポートを確認
  → /claude-skills:debug {investigate_report_summary}
```

Phase 1 で investigate レポートの内容をコンテキストとして活用し、重複した調査を省略する。

## 完了表示

```
══════════════════════════════════════
DEBUG SESSION COMPLETE
Error: {error_summary}
Root cause: {root_cause}
Fix: {fix_description}
Regression test: {test_name}
Tests: ALL PASS ✅
══════════════════════════════════════
```

## 重要なルール

- **Phase 1 完了前に修正を提案しない** — 根本原因の特定が先
- **一度に1つの変更** — 複数の修正を同時にしない
- **「ついでに」改善しない** — 修正と改善を混ぜない
- **3回失敗したら止まる** — 設計の問題を疑う
- **「わからない」と認める** — 推測より追加調査
