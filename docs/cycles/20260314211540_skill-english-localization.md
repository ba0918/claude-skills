# スキル英語化

**Cycle ID:** `20260314211540`
**Started:** 2026-03-14 21:15:40
**Status:** 🟡 In Progress

---

## 📝 What & Why

全スキルの SKILL.md および references/ 配下のファイルを英語化する。SKILL.md は LLM への指示書であり、英語の方がトークン効率・指示解釈精度ともに優れるため。

## 🎯 Goals

- 全 SKILL.md と references/ の .md ファイルを英語に統一する
- frontmatter の description も英語化する
- コードブロック内のコメント・プレースホルダーも英語化する
- コマンドファイル（commands/）は対象外（description は日本語の起動フレーズを含むため変更しない）

## 📐 Design

### 対象ファイル（全21ファイル）

8スキル × SKILL.md + 13 references ファイル。

### スキルごとにまとめて作業

各スキルの SKILL.md + references/ を1ステップとして扱い、スキルごとにコミットする。

### 英語化のルール

- 技術用語はそのまま（slug, frontmatter, timestamp 等）
- LLM への指示として明確・簡潔な英語にする
- 日本語のトリガーフレーズは全てそのまま残す（ユーザー入力のマッチングに使うため）。対象フレーズ例:
  - plan SKILL.md: "前回の続き", "続きから", "再開"（セッション復帰検出用）
  - plan-reviewer SKILL.md: "計画をレビュー", "plan review", "計画を確認", "実装計画をチェック", "プランレビュー"（description 内）
  - 各スキルの description 内の日本語起動フレーズ全般
  - ※ 翻訳時に description の起動フレーズを英語化しないよう注意
- issue-template.md のようなユーザー向けテンプレートの日本語セクション見出し（"## 概要" 等）もそのまま残す（出力先プロジェクトで使われるため）

### スコープ外の明示

- **CLAUDE.md は対象外**: CLAUDE.md はプロジェクトドキュメントであり LLM 指示書ではないため、本計画のスコープに含めない
- **commands/ は対象外**: コマンドファイルは薄いラッパーであり、description は起動フレーズとしてそのまま維持する
- **install.sh 再実行不要**: 既存ファイルの内容書き換えのみのため、シンボリックリンク経由で即反映される

### ロールバック方針

- 各スキルごとに個別コミットするため、問題があれば `git revert <commit>` で該当スキルのみ戻せる
- 全体をロールバックする場合は、Step 1 のコミットから連続 revert する

### Files to Change

```
skills/plan/
  SKILL.md                              - 混在 → 英語
  references/plan-template.md           - 混在 → 英語
  references/status-template.md         - 混在 → 英語
  references/status-update-guide.md     - 混在 → 英語

skills/plan-reviewer/
  SKILL.md                              - 混在 → 英語
  references/review-dimensions.md       - 混在 → 英語
  references/output-format.md           - 混在 → 英語

skills/commit/
  SKILL.md                              - 混在 → 英語

skills/iterate/
  SKILL.md                              - 混在 → 英語
  references/scope-criteria.md          - 混在 → 英語
  references/light-review.md            - 混在 → 英語

skills/doc-check/
  SKILL.md                              - 混在 → 英語
  references/structural-checks.md       - 混在 → 英語
  references/content-checks.md          - 混在 → 英語

skills/issue/
  SKILL.md                              - 混在 → 英語
  references/issue-template.md          - 日本語セクション見出しは維持

skills/codebase-review/
  SKILL.md                              - 混在 → 英語
  references/review-criteria.md         - 混在 → 英語
  references/report-template.md         - 混在 → 英語

skills/generate-review-rules/
  SKILL.md                              - 混在 → 英語
  references/output-template.md         - 混在 → 英語
```

## ✅ Implementation Steps

### 各ステップ共通の作業手順

1. 対象ファイルの現在の内容を読み込む
2. 日本語テキストを英語に翻訳（英語化ルールに従う）
3. 日本語トリガーフレーズが残っていることを確認
4. 相対パスリンク（`references/` へのリンク等）が壊れていないことを確認
5. スキルごとにコミット

### Step 1: plan スキルの英語化
- `skills/plan/SKILL.md` + 3 references ファイル
- **対象**: 4ファイル
- **注意**: SKILL.md 内の日本語トリガーフレーズ（"前回の続き", "続きから", "再開" 等）はそのまま残す

### Step 2: plan-reviewer スキルの英語化
- `skills/plan-reviewer/SKILL.md` + 2 references ファイル
- **対象**: 3ファイル

### Step 3: commit スキルの英語化
- `skills/commit/SKILL.md`
- **対象**: 1ファイル

### Step 4: iterate スキルの英語化
- `skills/iterate/SKILL.md` + 2 references ファイル
- **対象**: 3ファイル

### Step 5: doc-check スキルの英語化
- `skills/doc-check/SKILL.md` + 2 references ファイル
- **対象**: 3ファイル

### Step 6: issue スキルの英語化
- `skills/issue/SKILL.md` + 1 references ファイル
- **対象**: 2ファイル
- **注意**: issue-template.md の日本語セクション見出し（"## 概要", "## 影響" 等）はそのまま維持

### Step 7: codebase-review スキルの英語化
- `skills/codebase-review/SKILL.md` + 2 references ファイル
- **対象**: 3ファイル

### Step 8: generate-review-rules スキルの英語化
- `skills/generate-review-rules/SKILL.md` + 1 references ファイル
- **対象**: 2ファイル

## 🔒 Security

- N/A（ドキュメントの言語変更のみ）

## 📊 Progress

| Step | Description | Status |
|------|-------------|--------|
| 1 | plan スキル英語化（4ファイル） | 🟢 |
| 2 | plan-reviewer スキル英語化（3ファイル） | 🟢 |
| 3 | commit スキル英語化（1ファイル） | 🟢 |
| 4 | iterate スキル英語化（3ファイル） | 🟢 |
| 5 | doc-check スキル英語化（3ファイル） | ⚪ |
| 6 | issue スキル英語化（2ファイル） | ⚪ |
| 7 | codebase-review スキル英語化（3ファイル） | ⚪ |
| 8 | generate-review-rules スキル英語化（2ファイル） | ⚪ |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Review → Implement → Commit 🚀
