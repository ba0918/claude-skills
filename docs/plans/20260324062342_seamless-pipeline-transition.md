# Seamless Pipeline Transition

Issue/Brainstorm から team-cycle/team-plan へのシームレスな遷移パイプラインを構築し、完了後の issue-close 自動実行まで一気通貫で動作するようにする。

## What & Why

### What
- issue-cycle / brainstorm-plan から team-cycle への導線を追加
- brainstorm-plan から cycle 即実行への導線を追加
- 新規ショートカットコマンド（issue-team-cycle, brainstorm-cycle, brainstorm-team-cycle）を新設

### Why
- 現状、issue-cycle は通常の cycle にハードワイヤされており team-cycle に繋がらない
- brainstorm-plan は plan 作成後に「次は /cycle を実行してね」で終わり、cycle への直通導線がない
- team-cycle の Phase 3.4 には issue auto-close ロジックが既に実装済みだが、issue から team-cycle を呼ぶ手段がないため活用できない
- cycle と team-cycle は同じ入力インターフェース（docs/plans/*.md）を共有しており、最小変更で接続可能

## Team Review Summary

4専門家（Security / Performance / Architect / Pragmatist）全員 **BLOCK なし、WARN のみ** で承認。

### 採用した指摘事項
- **フラグパース明確化** (Security): `--team` の除去処理を明示的に記述
- **多重フラグ優先順位** (Security): `--team-cycle` と `--cycle` 同時指定時は `--team-cycle` 優先と明記
- **brainstorm-team-cycle の対称性** (Performance): `brainstorm-team-cycle.md` も新設
- **一元管理** (Pragmatist): コマンド側でフラグを渡し → SKILL.md 側で一元分岐する設計に統一

### 不採用の指摘事項
- **コスト警告表示** (Performance): ヘッドレス設計のため不採用。`--team` 指定時点でユーザーは team-cycle のコストを理解していると判断

## Steps

### Step 1: skills/issue/SKILL.md — Cycle Workflow に `--team` フラグ対応追加

**対象**: skills/issue/SKILL.md の Cycle Workflow（146-157行付近）

**変更内容**: Step 2 に `--team` フラグによる分岐を追加

変更前:
```markdown
2. Execute `claude-skills:cycle` via the Skill tool with the created plan
```

変更後:
```markdown
2. Execute cycle:
   - If `--team` is present in the arguments: Remove `--team` from arguments, then execute `claude-skills:team-cycle` via the Skill tool with the created plan
   - Otherwise: Execute `claude-skills:cycle` via the Skill tool with the created plan
```

### Step 2: skills/issue/SKILL.md — Plan Workflow の Next Steps 拡充

**対象**: skills/issue/SKILL.md の Plan Workflow 完了メッセージ（132-142行付近）

**変更内容**: Next Steps に team-cycle への導線を追加

変更前:
```markdown
## Next Steps
1. Review and discuss the plan
2. Run `/claude-skills:cycle` to implement
3. Issue will be auto-closed when cycle completes 🚀
```

変更後:
```markdown
## Next Steps
1. Review and discuss the plan
2. Run `/claude-skills:cycle` to implement
3. Run `/claude-skills:team-cycle` for team-reviewed implementation
4. Issue will be auto-closed when cycle completes 🚀
```

### Step 3: skills/brainstorm/SKILL.md — Plan Workflow の Next Steps 拡充

**対象**: skills/brainstorm/SKILL.md の Plan Workflow 完了メッセージ（138-147行付近）

**変更内容**: Next Steps に team-cycle への導線を追加

変更前:
```markdown
## Next Steps
1. `/plan-review` で計画をレビュー
2. `/claude-skills:cycle` でサイクル実行
```

変更後:
```markdown
## Next Steps
1. `/plan-review` で計画をレビュー
2. `/claude-skills:cycle` でサイクル実行
3. `/claude-skills:team-cycle` でチームレビュー付きサイクル実行
```

### Step 4: skills/brainstorm/SKILL.md — Plan Workflow に `--cycle` / `--team-cycle` フラグ追加

**対象**: skills/brainstorm/SKILL.md の Plan Workflow（124-147行付近）

**変更内容**: Step 4（plan-create 実行）の後にフラグに応じた cycle 実行を追加

Plan Workflow の Step 4 と Step 5 の間に以下を挿入:

```markdown
4.5. Optional cycle execution:
   - If `--team-cycle` is present in the original `$ARGUMENTS`: Remove the flag, then execute `claude-skills:team-cycle` via the Skill tool with the created plan. Skip Step 7 (Next Steps display).
   - Else if `--cycle` is present in the original `$ARGUMENTS`: Remove the flag, then execute `claude-skills:cycle` via the Skill tool with the created plan. Skip Step 7 (Next Steps display).
   - Otherwise: Continue to Step 5 (no cycle execution, show Next Steps as usual).
   - Note: If both `--team-cycle` and `--cycle` are specified, `--team-cycle` takes priority.
```

### Step 5: commands/issue-team-cycle.md 新設

**対象**: commands/issue-team-cycle.md（新規作成）

```markdown
---
description: "issue を選択して team-cycle（チームレビュー付き）で解決する"
---

Skill ツールで `claude-skills:issue` を実行する。引数: `cycle --team $ARGUMENTS`

**Note:** `--team` は自動付与される。ユーザーが重複指定しても動作に影響しない。
```

### Step 6: commands/brainstorm-cycle.md 新設

**対象**: commands/brainstorm-cycle.md（新規作成）

```markdown
---
description: "アイデアを plan に変換し cycle を即実行する"
---

Skill ツールで `claude-skills:brainstorm` を実行する。引数: `plan --cycle $ARGUMENTS`

**Note:** `--cycle` は自動付与される。`--team-cycle` に変更したい場合は `/claude-skills:brainstorm-team-cycle` を使用する。
```

### Step 7: commands/brainstorm-team-cycle.md 新設

**対象**: commands/brainstorm-team-cycle.md（新規作成）

```markdown
---
description: "アイデアを plan に変換し team-cycle（チームレビュー付き）で即実行する"
---

Skill ツールで `claude-skills:brainstorm` を実行する。引数: `plan --team-cycle $ARGUMENTS`

**Note:** `--team-cycle` は自動付与される。ユーザーが重複指定しても動作に影響しない。
```

### Step 8: CLAUDE.md — コマンド→スキルの対応表更新

**対象**: CLAUDE.md のコマンド→スキルの対応表

**変更内容**: 以下の3行を追加

```markdown
commands/issue-team-cycle.md →  skills/issue/SKILL.md (cycle --team ワークフロー)
commands/brainstorm-cycle.md →  skills/brainstorm/SKILL.md (plan --cycle ワークフロー)
commands/brainstorm-team-cycle.md → skills/brainstorm/SKILL.md (plan --team-cycle ワークフロー)
```

## Notes

- **issue auto-close は追加実装不要**: team-cycle の Phase 3.4 と cycle の Phase 3 Step 5 に既に実装済み。plan ヘッダの `**Issue:**` フィールド経由で自動動作する
- **後方互換性**: フラグなしの場合は全て従来通りの動作を維持
- **入力インターフェースの同型性**: cycle と team-cycle は同じ `docs/plans/*.md` を入力として共有しているため、呼び出し先を切り替えるだけで動作する
