---
name: iterate
description: cycle 完了後の追加指示を、サイズ適応型の軽量改善ループで実行する。修正・機能追加どちらにも対応。「iterate」「追加修正」「ここ直して」「これも追加して」「もうちょっと改善して」で起動。cycle よりも軽く、直接作業よりも品質を担保する中間的なワークフロー。
---

# Iterate

cycle 完了後の追加指示に対し、タスクサイズを自動判定して適切な改善ループを回すスキル。

## フロー概要

```
追加指示 → スコープ分析 → サイズ判定 ─→ Small → 実装 → 軽量レビュー → 完了
                                      └→ Large → ユーザーに提案 ─→ 続行 → 実装 → 厚めレビュー → 完了
                                                                  └→ plan → /plan-create を案内
```

## Phase 0: コンテキスト取得

1. 直近の計画ファイルを特定する
   ```bash
   ls -t docs/cycles/*.md 2>/dev/null | grep -v _result | head -1
   ```
2. 計画ファイルが存在すれば読み込み、実装済みの内容を把握する
3. `$ARGUMENTS` からユーザーの追加指示を取得する

## Phase 1: スコープ分析

Agent ツール（subagent_type: Explore）で以下を調査する:

1. 追加指示の内容を既存コードと照合し、影響範囲を推定する
2. 変更が必要なファイルをリストアップする
3. 新規ファイル作成の有無を判定する
4. 設計判断の要否を判定する

判定基準の詳細は [references/scope-criteria.md](references/scope-criteria.md) を参照。

## Phase 2: サイズ判定と分岐

### Small の場合

表示:
```
── Scope: Small ──
影響ファイル: {file_list}
推定変更量: {概算}
→ 軽量ループで実行します
```

Phase 3 へ進む。

### Large の場合

AskUserQuestion で判断を委ねる:

```
── Scope: Large ──
影響ファイル: {file_list}
推定変更量: {概算}
Large と判定した理由: {reasons}

選択肢:
1. このまま iterate で実行する（レビューを厚めにして対応）
2. /plan-create で計画を切り出す（推奨）
```

- ユーザーが「1」→ Phase 3 へ（Large モード）
- ユーザーが「2」→ `/plan-create` の実行を案内して終了

## Phase 3: 実装

Agent ツール（general-purpose）で実装エージェントを起動する。

エージェントへの指示:
- 追加指示の内容を実装する
- 既存コードのスタイル・規約に従う
- CLAUDE.md のルールを遵守する
- `.claude/review-rules.md` があれば参照する
- テストが必要な変更にはテストを追加する
- 実装完了後に既存テストを実行し、全パスを確認する

## Phase 4: レビュー

レビュー観点の詳細は [references/light-review.md](references/light-review.md) を参照。

### Small の場合

Agent ツール（general-purpose）でレビューエージェントを起動する:
- Security + Implementation Quality の 2 観点でレビュー
- `.claude/review-rules.md` があれば追加基準として使用
- 指摘を BLOCK / WARN / PASS で分類

### Large の場合（ユーザーが続行を選択）

Agent ツール（general-purpose）でレビューエージェントを起動する:
- Security + Implementation Quality + Architecture + Completeness の 4 観点でレビュー
- `.claude/review-rules.md` があれば追加基準として使用
- 指摘を BLOCK / WARN / PASS で分類

### レビュー結果の処理

- **BLOCK あり** → 修正して再レビュー（最大 2 イテレーション）
- **WARN のみ** → 修正を実施して完了
- **全 PASS** → そのまま完了

## Phase 5: トレーサビリティ

1. 直近の計画ファイルに「追加修正」セクションを追記する:

```markdown

## 追加修正 ({datetime})

### 指示内容
{ユーザーの追加指示}

### 変更内容
- {変更ファイルと概要}

### レビュー結果
- Security: {PASS|WARN}
- Implementation Quality: {PASS|WARN}
```

2. Skill ツールで `commit` を実行し、変更をコミットする

## Phase 6: 完了報告

```
══════════════════════════════════════
ITERATE COMPLETE
Scope: {Small|Large}
Files changed: {N}
Review: {PASS|WARN}
Plan updated: {plan_file_path}
══════════════════════════════════════
```

## 重要なルール

- **サイズ判定は実際のコード影響で行う** — ユーザーの「ちょっと」等の表現に引きずられない
- **Large 判定時はブロックしない** — 必ずユーザーに選択肢を提示する
- **実装中に想定外の影響が判明した場合は中断して報告する**
- **ヘッドレス対応**: Large 判定時のユーザー確認以外では確認プロンプトを出さない
- **BLOCK 指摘は必ず解消する** — BLOCK を残したまま完了しない
