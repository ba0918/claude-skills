# status.md Session History アーカイブ

**Cycle ID:** `20260314210110`
**Started:** 2026-03-14 21:01:10
**Status:** 🟢 Complete

---

## 📝 What & Why

status.md の Session History が cycle を回すたびに肥大化し、LLM がコンテキストを消費する問題を解決する。issue-status.md の archives/ パターンと同様に、完了済みセッションを自動的にアーカイブする仕組みを導入する。

## 🎯 Goals

- Completed になったセッションを Session History から自動的に除去し、status.md のサイズを一定に保つ
- アーカイブされた履歴は別ファイルに保存し、必要時に参照可能にする
- 既存の plan スキルのワークフローに自然に組み込む（破壊的変更なし）

## 📐 Design

### アーカイブ戦略

Session History のエントリが Completed になった時点で、そのエントリを `docs/session-history.md` に移動し、status.md からは削除する。

**なぜ `docs/session-history.md` か:**
- `docs/plans/` は計画ファイル専用。アーカイブデータを混ぜると役割がぼやける
- status.md と同階層に置くことで関連性が明確
- 単一ファイルで十分（Session History のエントリは数行なので、100件でも管理可能）

### Files to Change

```
skills/plan/
  SKILL.md                    - Status Update Workflow にアーカイブ手順を追加
  references/
    status-update-guide.md    - Case 2（Completed）にアーカイブ処理を追加
    status-template.md        - Session History セクションの説明を更新

docs/
  session-history.md          - 新規作成（アーカイブ先）

CLAUDE.md                     - session-history.md の役割を追記
```

### Key Points

- **アーカイブのタイミング**: In Progress → Completed への遷移時に自動実行
- **session-history.md のフォーマット**: 既存の Session History と同じ形式。新しいエントリは先頭に追加（新しい順）
- **session-history.md が未作成の場合**: アーカイブ処理時にヘッダー付きで自動作成する（初回フォールバック）
- **status.md の Session History セクション**: Completed エントリが移動された後は「（なし）」または直近の数件のみ保持

### session-history.md のフォーマット

```markdown
# Session History

| Cycle ID | Feature | Started | Completed | Plan |
|----------|---------|---------|-----------|------|
| `20260314204522` | Issue 管理スキル | 2026-03-14 | 2026-03-14 | [Link](./cycles/20260314204522_issue-management.md) |
```

テーブル形式にすることで、LLM が必要時にサッと読める＆人間にも見やすい。

## ✅ Implementation Steps

### Step 1: status-update-guide.md の更新
- Case 2（In Progress → Completed）にアーカイブ処理を追加
- 具体的には: Completed 時に session-history.md にエントリを追加し、status.md の Session History からは削除
- **session-history.md が存在しない場合**: ヘッダー付きで新規作成してからエントリを追加する（フォールバック処理）
- **対象ファイル**: `skills/plan/references/status-update-guide.md`

### Step 2: SKILL.md の更新
- Status Update Workflow セクションに、Completed 時のアーカイブ手順を追記
- File Organization セクションに session-history.md を追加
- **対象ファイル**: `skills/plan/SKILL.md`

### Step 3: status-template.md の更新
- Session History セクションの説明を更新（アーカイブされることを注記）
- **対象ファイル**: `skills/plan/references/status-template.md`

### Step 4: session-history.md の初期作成
- docs/session-history.md をテンプレートとして新規作成
- 既存の status.md に Session History エントリがあれば移行
- **対象ファイル**: `docs/session-history.md`

### Step 5: 現在の status.md を更新
- 現在の Completed セッション（Issue 管理スキル）を session-history.md に移行
- Session History を「（なし）」に戻す
- **対象ファイル**: `docs/status.md`

### Step 6: CLAUDE.md の更新
- アーキテクチャセクション等に `docs/session-history.md` の存在と役割を追記
- plan スキルの説明に session-history.md の管理が含まれることを反映
- **対象ファイル**: `CLAUDE.md`

## 🔒 Security

- N/A（ドキュメント管理のみ、セキュリティリスクなし）

## 📊 Progress

| Step | Description | Status |
|------|-------------|--------|
| 1 | status-update-guide.md 更新 | 🟢 |
| 2 | SKILL.md 更新 | 🟢 |
| 3 | status-template.md 更新 | 🟢 |
| 4 | session-history.md 初期作成 | 🟢 |
| 5 | status.md の既存データ移行 | 🟢 |
| 6 | CLAUDE.md 更新 | 🟢 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Review → Implement → Commit 🚀
