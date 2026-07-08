---
name: design-validate
description: デザインシステム準拠の多段階検証ゲート。Static Lint → Visual Regression → Rubric Judge の順で検証し、全ゲート合格でコード反映を承認する。「デザイン検証」「design validate」「バリデーション」で起動。
---

# Design Validate (Codex Edition)

デザインシステム準拠の **多段階検証ゲート**。
Static Lint → Visual Regression Test → Rubric Judge の順で検証し、全ゲート合格でコード反映を承認する。

## Codex CLI ツールの使い分け

- **shell** — lint スクリプトの実行、ファイル読み取り（`cat` / `rg` / `find`）、hash 計算、Visual Regression の Playwright / npx / node 呼び出し（`npx playwright ...` / `npx storybook build ...`）。Playwright・Storybook はフレームワーク呼び出しであり Codex ツールではないため shell で実行する
- **spawn_agent** / **wait_agent** — Stage 4（Rubric Judge）の独立 judge エージェント委譲。生成した LLM とは別インスタンスで評価する（自己採点防止）。judge は Read-only
- **apply_patch** — evidence（`.design/validate-report.json`）の出力・保存

> **Visual Regression の環境前提:** visual regression は playwright / node（および Storybook ビルド）に依存する。未導入環境では該当ゲート（Stage 3）をスキップし、mechanical (lint) + llm-judge で判定して報告する（weight は再配分）。

**共有契約:**
- [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md) — デザインシステム検証の共通契約
- [../shared/references/verification-gate.md](../shared/references/verification-gate.md) — 完了前検証ゲート共通契約

**パイプライン仕様:** [references/validation-pipeline.md](references/validation-pipeline.md) を参照。

## 前提条件

1. `.design/tokens.json` が存在すること（必須）
2. `.design/lint-config.json` が存在すること（省略時デフォルト使用）
3. `.design/component-catalog.json` が存在すること（DL101-103 に必要）
4. `.design/rubric.json` が存在すること（省略時デフォルト rubric を使用）
5. `.design/baseline/` が存在すること（visual test に必要。なければ lint のみ実行）

## Workflow

### Step 1: 環境チェック

1. 必要ファイルの存在確認（`shell` の `cat` / `find` / `ls`）
2. baseline の hash 検証（approval.json の tokensHash / catalogHash）
3. 利用可能な検証レベルを判定:
   - tokens.json あり → Level 1 (lint) 利用可能
   - baseline あり + Playwright あり → Level 3 (visual) 利用可能
   - rubric.json あり → Level 4 (rubric) 利用可能
4. 環境サマリーを表示:
   ```
   🔍 Validation Environment
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   tokens.json:    ✅ Found (v1.0.0)
   catalog.json:   ✅ Found (4 components)
   baseline:       ✅ Approved (2026-04-14)
   Playwright:     ✅ Available
   rubric.json:    ✅ Found (7 criteria)
   
   Available stages: Lint ✅ | Visual ✅ | Rubric ✅
   ```

### Step 2: Stage 1 — Baseline Check

validation-pipeline.md の Stage 1 に従い、baseline の整合性を検証。

- hash 一致 → 続行
- hash 不一致 → 警告表示し、再承認への導線を提示。lint のみ実行モードに切り替え

### Step 3: Stage 2 — Static Lint

design-lint スキルと同じロジックを内部実行。

1. 全対象ファイルをスキャン
2. DL001-006 (Token) + DL101-103 (Component) + DL201-204 (Page/Layout) を適用
3. 結果を R001, R002, R003 にマッピング

**短絡評価:** いずれかの mechanical 項目が FAIL → Stage 3, 4 をスキップし即 FAIL

```
❌ Stage 2: Static Lint — FAIL

R001 Token Compliance: FAIL (3 violations)
R002 Component Compliance: PASS
R003 Layout Compliance: PASS

修正が必要:
  src/components/Header.tsx:42 — DL001: 直書きカラー '#FF6B6B'
  src/pages/Landing.tsx:15 — DL006: CSS変数未使用 '#2563EB'
  src/pages/Landing.tsx:28 — DL001: 直書きカラー '#10B981'

Visual / Rubric ステージはスキップされました。
まず lint 違反を修正してから再実行してください。
```

### Step 4: Stage 3 — Visual Regression

baseline スクリーンショットとの比較。

1. Storybook ビルド確認（`npx storybook build` が可能か）
   - 不可能 → skip、weight 再配分
2. Playwright でスクリーンショット撮影
3. baseline/screenshots/ の対応するファイルと pixel-level 比較
4. `maxDiffPixelRatio` 以下 → pass
5. 結果を R004, R007 にマッピング

**未導入時の graceful degradation:**
```
⚠️ Stage 3: Visual Regression — SKIPPED
Storybook / Playwright が未導入のため、visual test はスキップされました。
R004, R007 の weight は他の項目に再配分されます。
```

### Step 5: Stage 4 — Rubric Judge

`spawn_agent` / `wait_agent` で独立 judge エージェントを起動。

1. 対象のスクリーンショットを準備（Stage 3 で撮影済み、または baseline を使用）
2. DESIGN.md の Do's/Don'ts セクションを `shell` の `cat` で読む
3. rubric.json の `llm-judge` 項目のプロンプトを構築
4. `spawn_agent` で judge を起動し、`wait_agent` で構造化された評価を取得
5. 結果を R005, R006 にマッピング

**重要:** judge エージェントは **Read-only**。ファイル編集は一切行わない。

### Step 6: Aggregation + 最終判定

validation-pipeline.md の Stage 5 に従い:

1. 全項目の weighted average を算出
2. `passingScore` と比較
3. evidence JSON を構築
4. `apply_patch` で `.design/validate-report.json` に保存

### Step 7: 結果表示

**PASS の場合:**
```
✅ Design Validation: PASS (Score: 93.5/100)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| ID   | Name                   | Score | Method     |
|------|------------------------|-------|------------|
| R001 | Token Compliance       | 100   | mechanical |
| R002 | Component Compliance   | 100   | mechanical |
| R003 | Layout Compliance      | 100   | mechanical |
| R004 | Visual Consistency     | 95    | visual     |
| R005 | Visual Harmony         | 100   | llm-judge  |
| R006 | Interaction Coherence  | 50    | llm-judge  |
| R007 | Responsive Behavior    | 100   | visual     |

📄 Evidence: .design/validate-report.json

コード反映 OK！ ✅
```

**FAIL の場合:**
```
❌ Design Validation: FAIL (Score: 65.0/100, required: 80)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{項目別のスコア表}

改善が必要な項目:
  R001 Token Compliance: 3 violations → var(--*) に置き換え
  R006 Interaction Coherence: ghost button の hover 効果が不統一

📄 Evidence: .design/validate-report.json
```

## 引数による実行モード

| 引数 | 動作 |
|------|------|
| (なし) | 全ステージ実行 |
| `lint` | Stage 2 のみ（lint only） |
| `visual` | Stage 2 + Stage 3（lint + visual） |
| `full` | 全ステージ（デフォルトと同じ） |
| `report` | 最新の validate-report.json を表示 |

## 絶対的な制約

- 検証結果は **捏造しない**。全てのスコアは実際のツール実行結果に基づく
- evidence は verification-gate 契約に準拠した形式で出力する
- LLM judge は生成した LLM とは **別の spawn_agent インスタンス** で実行する
- baseline なしで visual test を「pass」と判定してはならない
- lint のみの場合でも evidence を残す（partial evidence として）

## References

- **パイプライン仕様:** [references/validation-pipeline.md](references/validation-pipeline.md)
- **Rubric Schema:** [../design-scaffold/references/rubric-schema.json](../design-scaffold/references/rubric-schema.json)
- **共有契約:** [../shared/references/design-system-contract.md](../shared/references/design-system-contract.md)
- **検証ゲート:** [../shared/references/verification-gate.md](../shared/references/verification-gate.md)
