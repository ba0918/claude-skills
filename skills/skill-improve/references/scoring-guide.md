# Scoring Guide

摩擦スコアリング基準。collect.py の出力から各スキルの摩擦スコアを計算し、改善アクションを決定する。

## 摩擦スコア計算式

各スキルの摩擦スコア（0-10）は以下の重み付き合算で計算する:

```
friction_score = min(10, (
    retry_rate × 3.0 +
    correction_rate × 2.0 +
    abandonment_rate × 3.0 +
    error_rate × 2.0
))
```

### レート計算

| レート | 計算式 | 説明 |
|--------|--------|------|
| retry_rate | retry_count / invocation_count | リトライ率（0-1） |
| correction_rate | correction_turns / (invocation_count × 5) | 修正率（5ターン以上で飽和） |
| abandonment_rate | session_abandoned_count / invocation_count | 離脱率（0-1） |
| error_rate | tool_error_count / max(total_turns_to_completion, 1) | エラー率（0-1、1で飽和） |

### invocation_count が 0 の場合

invocation_count が 0（呼び出しなし）のスキルはスコア計算対象外とする。

## 閾値テーブル

| スコア範囲 | 判定 | 意味 |
|-----------|------|------|
| 0.0 - 0.9 | **Excellent** | 摩擦なし。改善不要 |
| 1.0 - 1.9 | **Good** | 軽微な摩擦。監視のみ |
| 2.0 - 2.9 | **Acceptable** | 許容範囲内。レポートに記録 |
| 3.0 - 4.9 | **Needs Attention** | 改善推奨。iterate Small で対応可能 |
| 5.0 - 6.9 | **Problematic** | 改善必須。iterate で対応 |
| 7.0 - 10.0 | **Critical** | 緊急対応。cycle で根本改善 |

## アクション対応表

| 摩擦スコア | アクション | 委譲先 |
|-----------|-----------|--------|
| 0 - 2 | レポートのみ | なし（friction-report.md を出力して終了） |
| 3 - 5 | Small 改善 | `claude-skills:iterate` に委譲 |
| 6+ | Large 改善 | 改善仮説から plan を作成 → `claude-skills:cycle` に委譲 |

## Dry-run ルール

**全レベルで Dry-run を必ず実行する。**

Dry-run では以下を表示し、実際の変更は行わない:

1. 改善対象のスキルファイル一覧
2. 変更内容の概要（差分プレビュー）
3. 期待される摩擦スコアの変化

`improve` モード時のみ Dry-run 表示後に実際の実装に進む。
`analyze` モードでは Dry-run 表示で終了。

## 信頼度の考慮

| invocation_count | 信頼度 | 注記 |
|-----------------|--------|------|
| 1-2 | Low | サンプル不足。スコアは参考値 |
| 3-9 | Medium | 傾向は見えるが統計的に不十分 |
| 10+ | High | 信頼できるスコア |

信頼度が Low のスキルは改善対象から除外し、レポートにのみ記載する。
