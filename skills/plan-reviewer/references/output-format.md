# Output Format - Plan Reviewer

レビュー結果の出力フォーマット定義。

---

## Individual Dimension Report (各観点レポート)

各レビュー観点は以下のJSON構造で出力する:

```json
{
  "dimension": "security",
  "confidence": 75,
  "verdict": "WARN",
  "issues": [
    {
      "severity": "critical",
      "task": "1-1",
      "title": "escapeHtml()のカバレッジ不足",
      "description": "エラー表示以外にもユーザー入力がDOMに挿入される箇所がある可能性",
      "location": "src/content/index.ts",
      "suggestion": "全てのinnerHTML代入箇所を洗い出し、escapeHtml()適用の網羅性を確認"
    }
  ],
  "positives": [
    "sanitizeHTML()のXSS防御が一貫している",
    "CSP設定が適切"
  ]
}
```

### フィールド定義

| フィールド | 型 | 説明 |
|-----------|------|------|
| dimension | string | レビュー観点名 |
| confidence | 0-100 | 問題の深刻度（高い=より深刻） |
| verdict | PASS/WARN/BLOCK | 判定結果 |
| issues[] | array | 検出された問題 |
| issues[].severity | critical/important/minor | 問題の重要度 |
| issues[].task | string | 計画内のタスク番号 |
| issues[].title | string | 問題の簡潔な説明 |
| issues[].description | string | 問題の詳細 |
| issues[].location | string | 影響ファイル/箇所 |
| issues[].suggestion | string | 修正提案 |
| positives[] | array | 良い点・適切な判断 |

---

## Final Summary Report (最終サマリー)

全観点の結果を統合した最終レポート:

```
================================================================================
PLAN REVIEW 完了
================================================================================

📋 対象: {計画ファイル名}
📅 日時: {YYYY-MM-DD HH:MM}

┌─────────────────────┬────────┬────────┐
│ 観点                │ スコア │  判定  │
├─────────────────────┼────────┼────────┤
│ Feasibility         │   25   │ ✅ PASS │
│ Security            │   75   │ ⚠️ WARN │
│ Performance/Memory  │   40   │ ✅ PASS │
│ Architecture/Design │   30   │ ✅ PASS │
│ Completeness        │   60   │ ⚠️ WARN │
│ Alternatives        │   85   │ 🛑 BLOCK│
└─────────────────────┴────────┴────────┘

総合判定: ⚠️ WARN (最大スコア: 85 → BLOCK)

────────────────────────────────────────

🛑 BLOCK Issues (修正必須):
  [Alternatives] タスク2-1: SHA-256ハッシュ比較よりもETag/Last-Modifiedヘッダを使う方が効率的
    → fetch HEAD リクエストでETagを比較する方式を検討

⚠️ WARN Issues (推奨修正):
  [Security] タスク1-1: escapeHtml()の適用範囲が不十分な可能性
    → 全innerHTML代入箇所の洗い出しを推奨
  [Completeness] タスク2-2: MutationObserverのdisconnect漏れリスク
    → コンポーネントアンマウント時のクリーンアップを明記

✅ Positives:
  - セキュリティ修正を最優先にしている判断が適切
  - レイヤーアーキテクチャに準拠した設計
  - テスト計画が各タスクに含まれている

────────────────────────────────────────

📝 推奨アクション:
  1. BLOCK項目を修正してから実装開始
  2. WARN項目は実装時に追加考慮
================================================================================
```

---

## Verdict Thresholds (判定閾値)

| 最大スコア | 判定 | 意味 | アクション |
|-----------|------|------|-----------|
| 80-100 | 🛑 BLOCK | 重大な問題あり | 計画を修正してから実装開始 |
| 50-79 | ⚠️ WARN | 改善の余地あり | 警告を確認し、必要なら計画修正 |
| 0-49 | ✅ PASS | 問題なし | 実装開始OK |

### 総合判定ルール

- 総合判定 = 全観点の最大スコアに基づく判定
- 1つでもBLOCKがあれば総合はBLOCK
- BLOCKなし、1つ以上WARNあれば総合はWARN
- 全てPASSなら総合はPASS
