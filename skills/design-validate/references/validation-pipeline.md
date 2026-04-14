# Validation Pipeline

design-validate スキルが実行する多段階検証パイプラインの仕様。

## パイプライン概要

```
Stage 1: Baseline Check
  └── approval.json 存在確認 + hash 検証

Stage 2: Static Lint (mechanical)
  └── design-lint 実行 → R001, R002, R003 のスコア算出

Stage 3: Visual Regression (visual)
  └── Playwright screenshot comparison → R004, R007 のスコア算出

Stage 4: Rubric Judge (llm-judge)
  └── Agent で独立 judge 起動 → R005, R006 のスコア算出

Stage 5: Aggregation
  └── weighted average → 合否判定 + evidence 出力
```

## Stage 1: Baseline Check

### 前提条件確認

1. `.design/baseline/approval.json` が存在するか
   - なければ「Baseline が確定していません。先に Base Design の承認が必要です」と警告
   - design-scaffold の approval フローへの導線を表示
2. `tokensHash` / `catalogHash` の検証
   - tokens.json の SHA-256 hash を計算し、approval.json の `tokensHash` と比較
   - component-catalog.json の SHA-256 hash を計算し、`catalogHash` と比較
   - 不一致の場合:
     ```
     ⚠️ Baseline と現在の定義ファイルが不一致です。
     tokens.json: {match/mismatch}
     catalog.json: {match/mismatch}
     
     再承認が必要です。`/claude-skills:design-scaffold` で Base Design を更新してください。
     ```

### Baseline 未確定時の動作

baseline が存在しない場合でも Stage 2 (lint) は実行可能。
Stage 3 (visual) と Stage 4 (rubric) は baseline 必須のため skip する。

## Stage 2: Static Lint

### 実行方法

design-lint スキルと同じロジックを内部で実行する。

1. `.design/tokens.json` を Read
2. `.design/lint-config.json` を Read
3. `.design/component-catalog.json` を Read（存在する場合）
4. 全対象ファイルをスキャンし、DL001-204 を適用
5. 結果を rubric の各項目にマッピング:

| Rubric ID | Lint ルール | 算出方法 |
|-----------|-----------|---------|
| R001 (Token Compliance) | DL001-006 | violations=0 → 100, >0 → 0 (binary) |
| R002 (Component Compliance) | DL101-103 | violations=0 → 100, >0 → 0 (binary) |
| R003 (Layout Compliance) | DL201-204 | violations=0 → 100, >0 → 0 (binary) |

### 短絡評価

R001, R002, R003 のいずれかが FAIL の場合:
- Stage 3, 4 は実行しない（lint が通らないコードの visual test は無意味）
- 即座に FAIL レポートを出力
- 修正すべき違反一覧を提示

## Stage 3: Visual Regression

### 前提条件

- `.design/baseline/screenshots/` に baseline スクリーンショットが存在
- Playwright がインストール済み（`npx playwright --version` で確認）
- Storybook がビルド可能（`npx storybook build` が成功）

### 実行方法

1. Storybook をビルド: `npx storybook build --output-dir storybook-static`
2. Playwright でスクリーンショットを撮影し、baseline と比較
3. 差分が `maxDiffPixelRatio` 以下かを判定

### 結果マッピング

| Rubric ID | 対象 | 算出方法 |
|-----------|------|---------|
| R004 (Visual Consistency) | コンポーネント | 全コンポーネントの diff 平均 ≤ 閾値 → pass |
| R007 (Responsive Behavior) | 各ブレークポイント | 全ブレークポイントで diff ≤ 閾値 → pass |

### Storybook / Playwright 未導入時

フレームワーク依存のセットアップが未完了の場合は skip:
- 「Visual test をスキップしました。Storybook + Playwright をセットアップすると visual regression test が有効になります」と案内
- R004, R007 は N/A として weight を再配分

## Stage 4: Rubric Judge (LLM)

### 独立性の原則

生成した LLM とは **別のインスタンス** で評価する（自己採点防止）。
design-validate 内で **Agent ツール** を使い、judge 専用エージェントを起動する。

### Judge 起動

```
Agent({
  description: "Design Rubric Judge",
  prompt: `
    あなたはデザインシステム準拠の独立審査員です。
    以下のスクリーンショットを DESIGN.md のデザインシステムに照らして評価してください。
    
    ## 評価基準
    
    ### R005: Visual Harmony (全体の調和)
    - pass: 色彩・フォント・余白が一貫し、視覚的なノイズがない
    - partial: 概ね一貫しているが、1-2箇所の不統一がある
    - fail: 明らかな不統一や視覚的な違和感がある
    
    ### R006: Interaction Coherence (インタラクションの一貫性)
    - pass: hover/focus/active 状態が全コンポーネントで一貫
    - partial: 概ね一貫しているが、一部のコンポーネントで不統一
    - fail: コンポーネント間でインタラクションパターンが不統一
    
    ## 入力
    - スクリーンショット: {screenshots}
    - DESIGN.md の Do's/Don'ts: {dos_donts}
    
    ## 出力形式
    各項目について以下の JSON で回答してください:
    {
      "R005": { "score": "pass|partial|fail", "reason": "1文で根拠を述べる" },
      "R006": { "score": "pass|partial|fail", "reason": "1文で根拠を述べる" }
    }
  `
})
```

### スコア変換

| Judge 判定 | 数値スコア |
|-----------|----------|
| pass | 100 |
| partial | 50 |
| fail | 0 |

## Stage 5: Aggregation

### Weighted Average 算出

```
totalScore = Σ (criterion.weight × criterion.score) / Σ (active_weights)

※ N/A の項目は weight を除外して再正規化
```

### デフォルト Rubric 項目

| ID | 名前 | 検証方法 | Weight | Scoring |
|----|------|---------|--------|---------|
| R001 | Token Compliance | mechanical | 0.25 | binary |
| R002 | Component Compliance | mechanical | 0.20 | binary |
| R003 | Layout Compliance | mechanical | 0.15 | binary |
| R004 | Visual Consistency | visual | 0.15 | scale-5 |
| R005 | Visual Harmony | llm-judge | 0.10 | scale-5 |
| R006 | Interaction Coherence | llm-judge | 0.08 | scale-5 |
| R007 | Responsive Behavior | visual | 0.07 | binary |

**Weight 比率:** mechanical (60%) > visual (22%) > llm-judge (18%)

### 合否判定

```
if totalScore >= rubric.passingScore:
  verdict = "PASS"
else:
  verdict = "FAIL"
```

デフォルト `passingScore`: 80

### Evidence 出力

```json
{
  "timestamp": "2026-04-14T20:00:00Z",
  "pipeline": "design-validate",
  "tokensVersion": "1.0.0",
  "baselineApproved": "2026-04-14T19:30:00Z",
  "scores": {
    "R001": { "score": 100, "verification": "mechanical", "details": "0 violations" },
    "R002": { "score": 100, "verification": "mechanical", "details": "0 violations" },
    "R003": { "score": 100, "verification": "mechanical", "details": "0 violations" },
    "R004": { "score": 95, "verification": "visual", "details": "avg diff: 0.3%" },
    "R005": { "score": 100, "verification": "llm-judge", "details": "pass: 色彩と余白が一貫" },
    "R006": { "score": 50, "verification": "llm-judge", "details": "partial: ghost button の hover が不統一" },
    "R007": { "score": 100, "verification": "visual", "details": "全ブレークポイント pass" }
  },
  "totalScore": 93.5,
  "passingScore": 80,
  "verdict": "PASS"
}
```

### Evidence 保存

`.design/validate-report.json` に保存。verification-gate 契約に準拠。
