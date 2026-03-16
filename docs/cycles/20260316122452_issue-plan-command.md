# issue-plan コマンド追加と cycle の issue 自動 close 対応

**Cycle ID:** `20260316122452`
**Started:** 2026-03-16 12:24:52
**Status:** 🟡 Planning

---

## 📝 What & Why

issue-cycle は全自動で plan → cycle → close を回すが、plan 作成後にユーザーと議論してから cycle に進みたいケースがある。issue-plan コマンドを新設し、plan 作成で止まるワークフローを提供する。また、cycle 側で plan に紐付いた issue を自動 close する仕組みを入れることで、issue-plan → 議論 → /cycle でも close が漏れないようにする。

## 🎯 Goals

- issue-plan コマンドを新設し、issue 選択 → plan 作成で止まるワークフローを提供する
- plan ファイルに `issue_id` を記録する仕組みを導入する
- cycle 完了時に plan の `issue_id` を見て自動 close する
- 既存の issue-cycle も新しい仕組みに乗せて close ロジックを一箇所に集約する

## 📐 Design

### Files to Change

```
commands/
  issue-plan.md        - 新規: issue-plan コマンド（薄いラッパー）
skills/
  issue/SKILL.md       - 変更: plan ワークフロー追加（Workflow Selection に plan キーワード追加）、
                                cycle ワークフローから close 直接呼び出しを削除
  plan/SKILL.md        - 変更: plan テンプレートに issue_id フィールド追加の説明
  plan/references/plan-template.md - 変更: issue_id オプショナルフィールド追加
commands/
  cycle.md             - 変更: Phase 3（サマリー生成）の status.md 更新後に
                                issue 自動 close ステップを追加
CLAUDE.md              - 変更: コマンドマッピング表に issue-plan を追加
```

> **Note:** `install.sh` はディレクトリ自動走査のため編集不要。新規ファイル追加後に `./install.sh` を再実行すれば反映される。

### Key Points

- **issue-plan ワークフロー（issue/SKILL.md に追加）**: Workflow Selection に `plan` キーワードを追加。issue 選択 → plan-create を issue_id 付きで実行 → 完了メッセージで次のステップ（議論 → /cycle）を案内。cycle は呼ばない。issue ファイルが見つからない場合は一覧を表示してエラー終了。
- **plan テンプレートに issue_id**: `**Issue:** {slug}` 行をオプショナルで追加。issue 起点でない plan には記載しない。
- **cycle の Phase 3 で自動 close**: Phase 3（サマリー生成）の status.md 更新完了後、plan ファイルを読み `**Issue:**` 行があれば Skill ツールで `issue` スキルの `close {slug}` を委譲実行する。`**Issue:**` 行がなければスキップ。close 失敗時は警告表示のみで cycle 自体は成功扱いとする（close 失敗で実装結果を巻き戻さない）。
- **issue-cycle の簡素化**: issue-cycle の cycle ワークフローから直接の close 呼び出し（Step 7）を削除。cycle 側に close を任せることで、issue-plan 経由でも issue-cycle 経由でも同じ close パスを通る。

### フロー比較

**Before:**
```
issue-cycle: issue選択 → plan-create → cycle → issue close
                                        ↑ close はここでしか動かない
```

**After:**
```
issue-cycle: issue選択 → plan-create(issue_id付き) → cycle → (cycle内で自動close)
issue-plan:  issue選択 → plan-create(issue_id付き) → 止まる
             ユーザー議論...
             /cycle → (cycle内で自動close)
```

## ✅ Tests

- [ ] issue-plan コマンドが issue 選択 → plan 作成で止まることを確認
- [ ] 作成された plan に `**Issue:**` 行が含まれることを確認
- [ ] /cycle 完了時に plan の issue_id を検出して自動 close されることを確認
- [ ] issue 起点でない通常の plan で cycle しても close 処理がスキップされることを確認
- [ ] issue-cycle が従来通り plan → cycle → close の一気通貫で動くことを確認
- [ ] 存在しない issue slug を指定した場合にエラー表示されることを確認
- [ ] cycle 内の issue close が失敗しても cycle 自体は成功扱いになることを確認

## 🔒 Security (if applicable)

- [ ] issue slug のバリデーション（パストラバーサル防止）— 既存の issue close ロジックを再利用するため追加対応不要

## 📊 Progress

| Step | Status |
|------|--------|
| 1. plan テンプレートに issue_id 追加 | 🟢 |
| 2. issue/SKILL.md に plan ワークフロー追加（Workflow Selection 含む） | ⚪ |
| 3. commands/issue-plan.md 新規作成 | ⚪ |
| 4. cycle.md に issue 自動 close 追加 | ⚪ |
| 5. issue-cycle から直接 close を削除 | ⚪ |
| 6. CLAUDE.md のコマンドマッピング更新 | ⚪ |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Review the plan → Discuss → `/cycle` で実行 🚀
