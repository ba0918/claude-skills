# Unify Date Format Rules Across Skills

**Cycle ID:** `20260324034348`
**Started:** 2026-03-24 03:43:48
**Status:** 🟢 Completed

---

## What & Why

全スキルの date 生成ルールを cycle のフォーマット（`yyyymmddhhmmss`、14文字）に統一する。現状 issue / brainstorm / doc-write が `YYYY-MM-DD` (10文字) を使用しており、issue -> plan や idea -> plan の変換時にファイル名の一貫性が崩れている。

## Goals

- 全スキルのファイル名 timestamp を `yyyymmddhhmmss` (14文字) に統一する
- issue -> plan、idea -> plan 変換時の slug フォーマット不整合を解消する
- ステータステーブル等の人間可読な日付表示は `YYYY-MM-DD HH:MM:SS` で統一する

## Design

### 変更方針

- **ファイル名 timestamp**: `yyyymmddhhmmss` (14文字) — `date +%Y%m%d%H%M%S` で生成
- **人間可読な日付表示**: テンプレート内やステータステーブルでは `YYYY-MM-DD HH:MM:SS`
- **date ルールの定義場所**: 各 SKILL.md に直接記述（DRY ファイルは作らない）
- **既存ファイルのマイグレーション**: スコープ外（新規作成分から適用）
- **slug サニタイズ**: パストラバーサル防御は引き続き維持

### Files to Change

```
skills/
  issue/
    SKILL.md                    - slug 定義を {yyyymmddhhmmss}_{kebab-title} に変更
                                  Create Workflow Step 4/6、Close Workflow、
                                  File Structure、issue-status.md Format、全例示を更新
    references/
      issue-template.md         - frontmatter の created を YYYY-MM-DD HH:MM:SS に変更
  brainstorm/
    SKILL.md                    - Wrap Workflow Step 4/7、Plan Workflow、
                                  Resume Workflow、File Structure の日付フォーマット更新
    references/
      idea-template.md          - Created を YYYY-MM-DD HH:MM:SS に変更
  doc-write/
    SKILL.md                    - Phase 2 Step 4、File Structure の日付フォーマット更新
    references/
      tech-note-template.md     - frontmatter の created/updated を YYYY-MM-DD HH:MM:SS に
      adr-template.md           - 同上（要確認）
      discussion-summary-template.md - 同上（要確認）
  team-brainstorm/
    SKILL.md                    - brainstorm と同じファイル名ルールの箇所を更新
```

### Key Points

- **ファイル名と人間可読日付の分離**: ファイル名は sorting 最適化の `yyyymmddhhmmss`、テンプレート内の表示は人間が読みやすい `YYYY-MM-DD HH:MM:SS`
- **issue -> plan 変換への影響**: issue slug が `yyyymmddhhmmss_{kebab-title}` に変わるため、plan ヘッダーの `**Issue:** {issue_slug}` フィールドも新フォーマットの slug を参照する。変換ロジック自体は変更不要（plan-create が新 timestamp を生成する点は同じ）
- **idea -> plan 変換への影響**: idea slug が変わるため、アーカイブ処理のファイル名が変わる。変換ロジック自体は変更不要
- **各スキル自己完結**: date ルールは各 SKILL.md に直接記述し、共有参照ファイルは作らない（変更頻度が低く、DRY のオーバーヘッドが恩恵を上回る）

## Implementation Steps

### Step 1: issue スキルの更新

**対象ファイル:** `skills/issue/SKILL.md`, `skills/issue/references/issue-template.md`

1. `## Slug Definition` セクション:
   - `{YYYY-MM-DD}_{kebab-title}` → `{yyyymmddhhmmss}_{kebab-title}`
   - 例: `2026-03-23_fix-login-timeout` → `20260323143000_fix-login-timeout`
   - 生成コマンド追記: `date +%Y%m%d%H%M%S`
2. `## Create Workflow` Step 4:
   - `Date: YYYY-MM-DD format` → `Timestamp: yyyymmddhhmmss format (date +%Y%m%d%H%M%S)`
   - `Final slug: {YYYY-MM-DD}_{kebab-title}` → `Final slug: {yyyymmddhhmmss}_{kebab-title}`
3. `## Create Workflow` Step 6:
   - テーブル行の Created 列: `{YYYY-MM-DD}` → `{YYYY-MM-DD HH:MM:SS}`
4. `## issue-status.md Format` セクション:
   - `Last Updated: YYYY-MM-DD` → `Last Updated: YYYY-MM-DD HH:MM:SS`
   - テーブル例の slug と Created を新フォーマットに更新
5. `## Close Workflow` の引数説明:
   - slug の例を新フォーマットに更新
6. `## File Structure`:
   - `YYYY-MM-DD_<kebab-title>.md` → `yyyymmddhhmmss_<kebab-title>.md`
7. `issue-template.md`:
   - `created: {{DATE}}` → `created: {{YYYY-MM-DD HH:MM:SS}}`
8. `## Notes` セクション (末尾):
   - `YYYY-MM-DD_{kebab-title}` → `yyyymmddhhmmss_{kebab-title}` に更新

### Step 2: brainstorm スキルの更新

**対象ファイル:** `skills/brainstorm/SKILL.md`, `skills/brainstorm/references/idea-template.md`

1. `## Wrap Workflow` Step 4:
   - `slug を生成: YYYY-MM-DD_{kebab-title}` → `slug を生成: yyyymmddhhmmss_{kebab-title}` (date +%Y%m%d%H%M%S)
2. `## Wrap Workflow` Step 7:
   - テーブル行の Created 列: `{YYYY-MM-DD}` → `{YYYY-MM-DD HH:MM:SS}`
3. `## Wrap Workflow` の idea-status.md テンプレート:
   - `Last Updated: YYYY-MM-DD` → `Last Updated: YYYY-MM-DD HH:MM:SS`
4. `## File Structure`:
   - `YYYY-MM-DD_{slug}.md` → `yyyymmddhhmmss_{slug}.md`
5. `idea-template.md`:
   - `Created: {{DATE}}` → `Created: {{YYYY-MM-DD HH:MM:SS}}`

### Step 3: doc-write スキルの更新

**対象ファイル:** `skills/doc-write/SKILL.md`, `skills/doc-write/references/tech-note-template.md`, `skills/doc-write/references/adr-template.md`, `skills/doc-write/references/discussion-summary-template.md`

1. `## Write Workflow` Phase 2 Step 4:
   - `slug を生成: YYYY-MM-DD_{kebab-title}` → `slug を生成: yyyymmddhhmmss_{kebab-title}` (date +%Y%m%d%H%M%S)
2. `## File Structure`:
   - `YYYY-MM-DD_{slug}.md` → `yyyymmddhhmmss_{slug}.md`
3. 各テンプレートの frontmatter:
   - `created: "{{DATE}}"` → `created: "{{YYYY-MM-DD HH:MM:SS}}"`
   - `updated: "{{DATE}}"` → `updated: "{{YYYY-MM-DD HH:MM:SS}}"`

### Step 4: team-brainstorm スキルの更新

**対象ファイル:** `skills/team-brainstorm/SKILL.md`

1. `## Wrap Workflow` Step 4:
   - `slug を生成: YYYY-MM-DD_{kebab-title}` → `slug を生成: yyyymmddhhmmss_{kebab-title}` (date +%Y%m%d%H%M%S)
2. `## Wrap Workflow` Step 7:
   - テーブル行の Created 列: `{YYYY-MM-DD}` → `{YYYY-MM-DD HH:MM:SS}`
3. `## Wrap Workflow` の idea-status.md テンプレート:
   - `Last Updated: YYYY-MM-DD` → `Last Updated: YYYY-MM-DD HH:MM:SS`
4. `## File Structure`:
   - `YYYY-MM-DD_{slug}.md` → `yyyymmddhhmmss_{slug}.md`

### Step 5: CLAUDE.md の更新確認

**対象ファイル:** `CLAUDE.md`

1. date フォーマットに関する記述がある場合は更新
2. なければ変更不要

## Tests

- [ ] issue create 後のファイル名が `yyyymmddhhmmss_{slug}.md` になること
- [ ] brainstorm wrap 後のファイル名が `yyyymmddhhmmss_{slug}.md` になること
- [ ] doc-write 後のファイル名が `yyyymmddhhmmss_{slug}.md` になること
- [ ] issue -> plan 変換で plan ヘッダーの Issue フィールドが新フォーマット slug を参照すること
- [ ] idea -> plan 変換で正しくアーカイブされること
- [ ] ステータステーブルの日付が `YYYY-MM-DD HH:MM:SS` で表示されること
- [ ] team-brainstorm のファイル名が brainstorm と同じ新フォーマットであること
- [ ] slug サニタイズ（パストラバーサル防御）が引き続き機能すること

## Security (if applicable)

- [ ] slug 生成時のパストラバーサル防御（`/`, `..`, `\` の除去）は引き続き維持
- [ ] ファイル名に使用する文字の制限（英数字とハイフンのみ）は変更なし

## Progress

| Step | Status |
|------|--------|
| Step 1: issue スキル | 🟢 |
| Step 2: brainstorm スキル | 🟢 |
| Step 3: doc-write スキル | 🟢 |
| Step 4: team-brainstorm スキル | 🟢 |
| Step 5: CLAUDE.md 確認 | 🟢 (変更不要) |
| Tests | ⚪ |
| Commit | ⚪ |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

## Team Planning Results

**Planned:** 2026-03-24 03:43:48
**Team:** Security Advisor, Performance Advisor, Architect, Pragmatist

### 合意事項
- ファイル名 timestamp は `yyyymmddhhmmss` (14文字) に全スキル統一
- 生成コマンドは `date +%Y%m%d%H%M%S`
- 人間可読な日付表示は `YYYY-MM-DD HH:MM:SS` で統一
- date ルールは各 SKILL.md に直接記述（共有参照ファイルは作らない）
- 既存ファイルのマイグレーションはスコープ外
- パストラバーサル防御は引き続き維持

### 議論ハイライト
- **DRY vs 直接記述**: 全員一致で直接記述を推奨。変更頻度が低く、LLM が読む文書は自己完結性が重要。YAGNI 原則にも合致。

### 各メンバーの貢献
- **Security Advisor**: パストラバーサル防御の継続、slug サニタイズルールの維持を提案
- **Performance Advisor**: 人間可読性とソート効率のバランス、認知コスト最小化の観点から直接記述を推奨
- **Architect**: 自己完結性の重要性、DRY のオーバーヘッドが恩恵を上回る判断
- **Pragmatist**: YAGNI 原則の適用、既存マイグレーションのスコープ外化、具体的な変更ファイル一覧の整理

---

**Next:** Write tests -> Implement -> Commit with `claude-skills:commit`
