# cycle 完了時に status.md を自動で Completed にする

**Cycle ID:** `20260315194952`
**Started:** 2026-03-15 19:49:52
**Status:** 🟢 Done

---

## 📝 What & Why

cycle コマンドの Phase 3 でサマリーファイルは生成するが、status.md の Current Session を Completed に更新して session-history.md にアーカイブする処理が欠落している。cycle 完了後に手動で status 更新する必要があり、忘れると status.md が Planning のまま放置される。

## 🎯 Goals

- cycle コマンドの Phase 3 に status.md 完了処理を追加する
- session-history.md へのアーカイブも Phase 3 で行う
- ヘッドレス実行でも確実に status が更新される

## 📐 Design

### Files to Change

```
commands/
  cycle.md - Phase 3 に status.md 更新ステップを追加
```

### Key Points

- **Phase 3 の拡張**: サマリーファイル生成の後に、status.md の更新と session-history.md へのアーカイブを追加
- **既存の status-update-guide.md を参照**: 完了処理のロジックは既に status-update-guide.md の Case 2 (In Progress → Completed) に定義済み。cycle.md からはその手順を参照指示する
- **1ファイルのみ変更**: cycle.md だけを修正すれば良い

### 追加するステップ

Phase 3 のサマリーファイル生成（手順2）の後に以下を追加:

```
3. status.md を完了状態に更新する:
   - skills/plan/references/status-update-guide.md の Case 2（In Progress → Completed）の手順に従う
   - Step 2a: session-history.md にアーカイブ
   - Step 2b: Session History セクションをクリア
   - Step 2c: Current Session をクリア
   - ガード条件: Current Session が既に空または Completed の場合はスキップ（冪等性を保証）
```

## ✅ Tests

- [x] cycle.md の Phase 3 に status.md 更新ステップが記載されている
- [x] status-update-guide.md の Case 2 への参照指示になっている（具体手順の埋め込みではない）
- [x] session-history.md へのアーカイブ手順が参照されている
- [x] Current Session のクリア手順が参照されている
- [x] Current Session が既に空/Completed の場合にスキップするガード条件が記載されている

## 📊 Progress

| Step | Status |
|------|--------|
| cycle.md Phase 3 に status 更新ステップ追加 | 🟢 |
| Commit | 🟢 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Write implementation → Commit with `commit` 🚀
