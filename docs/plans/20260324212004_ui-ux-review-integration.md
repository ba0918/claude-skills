# UI/UXデザイナーレビューの導入

**Cycle ID:** `20260324212004`
**Started:** 2026-03-24 21:20:04
**Status:** 🟢 Completed

---

## 📝 What & Why

レビュースキル（plan-reviewer / team-cycle / team-plan）に UI/UX 観点を段階的に導入する。現在のレビューシステムは Security / Performance / Architecture / Pragmatist の4観点のみで、UI/UX の視点が一切含まれていない。CLI ツールであっても、ターミナル出力・対話フロー・エラーメッセージ等の UX 設計は品質に直結するため、この観点を体系的にカバーする仕組みが必要。

## 🎯 Goals

- plan-reviewer の6観点を7観点に拡張し、UI/UX レビューチェックリストを追加する
- キーワード検出による条件付き UI/UX レビューの自動トリガーを実装する
- team-config.md に UX Advisor ロールを追加し、team-cycle / team-plan で使えるようにする
- 偽陰性より偽陽性を許容する設計で、`.claude/review-rules.md` によるユーザーオーバーライドを可能にする

## 📐 Design

### Files to Change

```
skills/plan-reviewer/
  references/review-dimensions.md  - UI/UX セクション追加（7観点化）
  SKILL.md                         - 7観点化に伴う記述更新 + キーワード検出ロジック追加

skills/shared/references/
  team-config.md                   - UX Advisor ロール定義追加

skills/team-cycle/
  SKILL.md                         - optional specialist 対応（UI/UX 検出時に UX Advisor を動的追加）

skills/team-plan/
  SKILL.md                         - optional specialist 対応（同上）
```

### Key Points

- **段階的導入**: Step 1（チェックリスト追加）→ Step 2（キーワード検出）→ Step 3（専任ロール追加）の3段階で、各段階が独立して検証可能
- **偽陽性許容設計**: UI/UX 検出は広めにマッチさせ、見落とし（偽陰性）よりも余分なレビュー（偽陽性）を許容する
- **ユーザーオーバーライド**: `.claude/review-rules.md` に `ui_ux_review: always` / `never` を書けば自動検出を上書き可能
- **Open-Closed Principle**: 既存ロール定義は変更せず、新ロールを追加する形で拡張

## 🔧 Implementation Steps

### Step 1: review-dimensions.md に UI/UX セクション追加

**対象ファイル:** `skills/plan-reviewer/references/review-dimensions.md`

Table of Contents に `7. [UI/UX](#7-uiux)` を追加し、末尾に以下のセクションを追加:

```markdown
## 7. UI/UX

User-facing output quality, interaction flow design, and information architecture.
This dimension is triggered conditionally — only when the plan involves changes to user-facing output or interaction patterns.

### Checklist

- [ ] Error messages are actionable: include what happened, why, and how to fix it
- [ ] Progress feedback is provided for operations taking > 5 seconds
- [ ] AskUserQuestion options follow Hick's Law: ≤ 4 options, clear labels, sensible defaults
- [ ] Output format is consistent with existing skills (terminology, indentation, section headers)
- [ ] Cancel/abort paths are designed and tested (not just happy path)
- [ ] Information hierarchy follows "summary first, details on demand" pattern
- [ ] Long output uses visual grouping (headers, separators, blank lines) for scannability
- [ ] No jargon leak: user-facing text avoids internal implementation terms

### Confidence Score Criteria

| Score | Condition |
|-------|-----------|
| 80-100 | No error recovery guidance, missing progress feedback for long operations, cancel path undesigned |
| 50-79 | Inconsistent output format, excessive cognitive load, suboptimal option design |
| 0-49 | Good user experience design |
```

### Step 2: plan-reviewer SKILL.md の更新

**対象ファイル:** `skills/plan-reviewer/SKILL.md`

2箇所の変更:

**(a)** description と観点数の記述を6→7に更新:
- `6観点` → `7観点` に変更
- `6-dimension` → `7-dimension` に変更
- Review 7: UI/UX のセクションを追加

**(b)** Step 2（Gather Project Context）に UI/UX キーワード検出ロジックを追加:

```markdown
### Step 2.5: UI/UX Review Trigger Detection

Scan the plan content for UI/UX signals. If ANY of the following are detected, include Review 7 (UI/UX) in the parallel review:

**Strong signals (any one triggers):**
- Keywords: "UI", "UX", "component", "screen", "page", "button", "form", "modal", "frontend", "AskUserQuestion", "accessibility", "a11y"
- File extensions in affected files: `.tsx`, `.jsx`, `.vue`, `.svelte`, `.css`, `.scss`, `.html`

**Weak signals (2+ required to trigger):**
- Keywords: "display", "layout", "style", "output", "format", "message", "error message", "progress"

**Override:** If `.claude/review-rules.md` contains `ui_ux_review: always`, always include. If `ui_ux_review: never`, always skip.

If no signals detected and no override, skip Review 7.
```

### Step 3: team-config.md に UX Advisor ロール追加

**対象ファイル:** `skills/shared/references/team-config.md`

既存の Pragmatist セクションの後に新ロールを追加:

```markdown
### UX Advisor (optional specialist)

**専門観点:** ユーザー体験・情報設計・対話フロー

**追加条件:** plan に UI/UX 要素（ユーザー向け出力変更、対話フロー変更、エラーメッセージ変更）が含まれる場合。plan-reviewer が `ui_ux_detected: true` と判定した場合に自動追加される。

**専門知識:**
- ニールセンのユーザビリティヒューリスティクス（10原則）
- ヒックの法則（選択肢数と意思決定時間の関係）
- CLI/ターミナル UX 設計（プログレス表示、エラーメッセージ、対話フロー）
- 情報アーキテクチャ（見出し階層、スキャナビリティ、サマリーファースト）
- アクセシビリティ基本原則
- デザインシステムの一貫性（用語・フォーマット・対話パターンの統一）
```

スポーンプロンプトは **計画レビュー用のみ** 追加する（助言者フレーミング for team-plan、批判者フレーミング for team-cycle）。**コードレビュー用プロンプトは追加しない** — Phase 2.5 コードレビューは引き続き Security + Architect の2名体制とする（UX観点のコードレビューは対象外）。

### Step 4: team-cycle SKILL.md に optional specialist 対応追加

**対象ファイル:** `skills/team-cycle/SKILL.md`

Phase 1 のチーム構成に条件付き UX Advisor 追加のロジックを追加:

```markdown
### Step 1.2.5: Optional Specialist Detection

Step 1.2（コンテキスト収集）完了後、Step 1.3（レビュワー spawn）の前に実行する。

計画内容を plan-reviewer Step 2.5 と同じキーワード検出ロジックでスキャンする。

If UI/UX signals detected:
- Step 1.3 で UX Advisor を5人目として追加 spawn する
- Phase 1 の全議論ラウンドに UX Advisor を含める
- Phase 1 表示を `Reviewers: {active_count}/{total}` に動的化

If not detected:
- 標準4人構成で続行

**spawn 失敗時の扱い:**
- UX Advisor（optional specialist）の spawn 失敗は WARNING のみ。コア4ロール（Security/Performance/Architect/Pragmatist）のうち2名以上成功すれば続行可能。
- Phase 2.5（コードレビュー）には UX Advisor は参加しない。
```

### Step 5: team-plan SKILL.md に同様の optional specialist 対応追加

**対象ファイル:** `skills/team-plan/SKILL.md`

team-cycle と同じ条件付き UX Advisor 追加ロジックを追加。

### Step 6: plugin.json のバージョンバンプ

**対象ファイル:** `plugin.json`（プロジェクトルートの plugin.json）

バージョンを上げる（新ロール追加のため）。

## ✅ Tests

- [ ] plan-reviewer で UI/UX キーワードを含む計画をレビューした際に、7番目の観点（UI/UX）が含まれること
- [ ] plan-reviewer で UI/UX キーワードを含まない計画をレビューした際に、UI/UX 観点がスキップされること
- [ ] `.claude/review-rules.md` に `ui_ux_review: always` を設定した場合、常に UI/UX 観点が含まれること
- [ ] team-cycle で UI/UX 要素を含む計画を実行した際に、UX Advisor がスポーンされること
- [ ] team-cycle で UI/UX 要素を含まない計画を実行した際に、標準4ロールのみであること
- [ ] team-plan で同様の動的ロール追加が機能すること

## 🔒 Security

- [ ] UX Advisor のスポーンプロンプトに機密情報を含めない
- [ ] `.claude/review-rules.md` のオーバーライド値のバリデーション（`always` / `never` / `auto` のみ許可。無効値はデフォルト `auto` にフォールバック）

## 🔍 Team Review Results

**Reviewed:** 2026-03-24 21:38:00
**Verdict:** APPROVED WITH CONCERNS

### 修正事項
- UX Advisor はコードレビュー（Phase 2.5）には参加しないと明記（指摘者: Architect, Pragmatist）
- スポーンプロンプトは計画レビュー用のみ（助言者/批判者の2フレーミング）と明記（指摘者: Architect, Pragmatist, Security）
- optional specialist の spawn 失敗は WARNING のみ、コア4ロールで2名以上成功なら続行と明記（指摘者: Architect）
- キーワード検出の挿入位置を Step 1.2 と Step 1.3 の間（Step 1.2.5）と明確化（指摘者: Pragmatist）
- review-rules.md 無効値はデフォルト `auto` にフォールバックと明記（指摘者: Security）

### 残存リスク
- キーワード検出の偽陽性/偽陰性（許容理由: 偽陽性許容の設計方針。ユーザーオーバーライドで制御可能）
- UX Advisor のレビュー品質はプロンプト設計に依存（許容理由: 段階的導入で実運用しながら改善予定）

### 議論ハイライト
- 全レビュワーが WARN 以下で収束。BLOCK なし。トレードオフ議論不要で早期収束。
- Performance: 全く問題なし。Markdown編集のみでパフォーマンス影響なし。
- Security: プロンプトインジェクションリスクは INFO レベル（構造化フィールドのみ対象）。

## 📊 Progress

| Step | Description | Status |
|------|-------------|--------|
| Step 1 | review-dimensions.md に UI/UX セクション追加 | 🟢 |
| Step 2 | plan-reviewer SKILL.md 更新（7観点化 + キーワード検出） | 🟢 |
| Step 3 | team-config.md に UX Advisor ロール追加 | 🟢 |
| Step 4 | team-cycle SKILL.md に optional specialist 対応 | 🟢 |
| Step 5 | team-plan SKILL.md に optional specialist 対応 | 🟢 |
| Step 6 | plugin.json バージョンバンプ | 🟢 |
| Tests | 動作確認 | 🟢 |
| Commit | コミット | ⚪ |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Write tests → Implement → Commit with `claude-skills:commit` 🚀
