# Status.md 旧形式の自動マイグレーション

**Cycle ID:** `20260315193813`
**Started:** 2026-03-15 19:38:13
**Status:** 🟡 In Progress

---

## 📝 What & Why

他プロジェクトで cycle を回したとき、既存の旧形式 status.md が新形式（session-history.md 分離）に自動移行されない。plan スキルの status.md 読み込みロジックに旧形式検出→自動変換を組み込み、意識せずに新形式へ移行させる。

## 🎯 Goals

- status.md 読み込み時に旧形式を自動検出する
- 旧形式の履歴エントリーを session-history.md へ自動移動する
- 新形式テンプレートに書き換える（Current Session の内容は保持）
- ユーザーが migrate コマンドを叩く必要がない（透過的に実行）

## 📐 Design

### Files to Change

```
skills/plan/
  references/status-update-guide.md - 旧形式検出・マイグレーションロジックを追加
  SKILL.md - Phase 4 に旧形式検出のガイダンスを追加
```

### Key Points

- **旧形式の判定基準**: `## 📜 Session History` セクション内に `[session-history.md]` へのリンクが存在せず、かつテーブル行（`|` で始まる行でヘッダー行・区切り行を除く）が直接含まれている場合を旧形式とみなす。セクションヘッダーは `## 📜 Session History` または `## Session History` の両方を検出対象とする
- **マイグレーションのタイミング**: SKILL.md Phase 4 の「Read existing status.md」時点で旧形式を検出したら、新セッション書き込み前にマイグレーション実行
- **べき等性**: すでに新形式ならスキップ。何度実行しても同じ結果になる
- **session-history.md のヘッダー形式**: 新規作成時は status-update-guide.md で定義済みのヘッダー（`# Session History` + テーブルヘッダー `| Cycle ID | Feature | Started | Completed | Plan |`）を使用する

### マイグレーション手順

1. status.md を読み込む
2. `## 📜 Session History` または `## Session History` セクションを検出し、テーブルのデータ行（`|` で始まり、ヘッダー行 `| Cycle ID |` や区切り行 `|---` を除く行）を抽出
3. データ行があれば → session-history.md へ移動
   - session-history.md が既に存在する場合: ヘッダー行の直後（既存データ行の前）に追加
   - session-history.md が存在しない場合: `# Session History` + テーブルヘッダー（`| Cycle ID | Feature | Started | Completed | Plan |`）付きで新規作成
4. status.md の Session History セクションをアーカイブリンクのみに置換:
   ```markdown
   ## 📜 Session History

   _Archived sessions can be found in [session-history.md](./session-history.md)._
   ```
5. `## 🔗 Quick Links` セクションがなければ、status-template.md の定義に従い追加:
   ```markdown
   ## 🔗 Quick Links

   - [Architecture](./ARCHITECTURE.md)
   - [Coding Principles](./CODING_PRINCIPLES.md)
   - [All Cycles](./cycles/)
   - [Project Root](../)
   ```
6. フッターノート（`**Note:** This file is auto-managed by the `plan` skill.`）がなければ追加

## ✅ Tests

- [ ] 旧形式 status.md（履歴テーブル行あり）→ 履歴が session-history.md に移動される
- [ ] 旧形式 status.md + 既存 session-history.md → 既存エントリーの前に追加される
- [ ] 旧形式 status.md に Current Session がある場合 → Current Session の内容が保持される
- [ ] 新形式 status.md → 何も変更されない（べき等性）
- [ ] status.md が存在しない → 通常通りテンプレートから新規作成
- [ ] セクションヘッダーが `## Session History`（絵文字なし）の旧形式でも正しく検出される

## 📊 Progress

| Step | Status |
|------|--------|
| status-update-guide.md にマイグレーションロジック追加 | 🟢 |
| SKILL.md Phase 4 にガイダンス追加 | 🟢 |
| Commit | 🟡 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Write implementation → Commit with `commit` 🚀
