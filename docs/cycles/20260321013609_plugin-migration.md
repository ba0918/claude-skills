# Plugin Migration

**Cycle ID:** `20260321013609`
**Started:** 2026-03-21 01:36:09
**Status:** 🟡 Planning

---

## 📝 What & Why

現在 `install.sh` でシンボリックリンクを張って `~/.claude/` に配置している commands/skills/rules を、Claude Code の plugin フォーマットに移行する。これにより `install.sh` が不要になり、`/plugin install` でインストール・更新が完結するようになる。

## 🎯 Goals

- Plugin フォーマット（`.claude-plugin/plugin.json`）に準拠した構造にする
- 既存の commands/skills/rules がそのまま動作することを保証する
- private GitHub repo からインストールできるようにする
- `install.sh` によるシンボリックリンク管理を廃止する

## 📐 Design

### 現状 → 移行後の構造

```
【現状】
claude-skills/
├── install.sh              ← シンボリックリンク管理（廃止）
├── commands/*.md           ← ~/.claude/commands/ にリンク
├── skills/*/SKILL.md       ← ~/.claude/skills/ にリンク
└── rules/*.md              ← ~/.claude/rules/ にリンク

【移行後】
claude-skills/
├── .claude-plugin/
│   └── plugin.json         ← NEW: Plugin マニフェスト
├── commands/*.md           ← そのまま（plugin が自動認識）
├── skills/*/SKILL.md       ← そのまま（plugin が自動認識）
├── rules/*.md              ← ※ plugin でどう扱うか要確認
├── install.sh              ← 削除 or 非推奨化
├── CLAUDE.md               ← 更新（インストール手順を変更）
└── README.md               ← 更新（インストール手順を変更）
```

### Key Points

- **構造変更は最小限**: `commands/` と `skills/` のディレクトリ構造は plugin フォーマットとほぼ同一なので、そのまま流用できる
- **plugin.json の追加のみがコア作業**: `.claude-plugin/plugin.json` を作成するだけで基本的に plugin として認識される
- **rules/ の扱い**: Plugin フォーマットでは `rules/` ディレクトリの自動配置はサポートされていない可能性がある。調査が必要
- **名前空間の変化**: Plugin 化すると `/plan-create` → `/claude-skills:plan-create` のように名前空間が付く。既存のコマンド間の相互参照（Skill ツール呼び出し）に影響する可能性あり
- **ローカル開発**: `claude --plugin-dir ./` でローカルから直接テスト可能。`/reload-plugins` で変更を即反映

### 要調査事項と対応方針

各事項は実装ステップ1（調査フェーズ）で確認し、結果に応じて以下の方針で進める。

1. **rules/ の移行方法**
   - **調査内容**: Plugin フォーマットが `rules/` ディレクトリを自動認識するか確認（`claude --plugin-dir ./` でローカルテスト）
   - **方針A（サポートあり）**: そのまま `rules/` を配置
   - **方針B（サポートなし）**: rules の内容を CLAUDE.md に統合するか、plugin の `postInstall` フックで `~/.claude/rules/` にコピーする。最悪の場合は「rules は手動コピー」とドキュメントに明記する

2. **スキル名の名前空間**
   - **調査内容**: Plugin 化後に Skill ツール呼び出しが `plan-reviewer` のまま動くか、`claude-skills:plan-reviewer` に変更が必要か確認
   - **方針A（短縮名で動く）**: 修正不要
   - **方針B（名前空間必須）**: 以下のファイルの Skill ツール呼び出しを一括更新
     - `commands/cycle.md` （`plan-refine`, `plan-implement`）
     - `commands/plan-refine.md` （`plan-reviewer`）
     - `commands/plan-review.md` （`plan-reviewer`）
     - `commands/issue-cycle.md` （`plan`, `cycle`）
     - `commands/brainstorm-plan.md` （`plan`）
     - `commands/parallel-cycle.md` （`cycle`）
     - `skills/parallel-cycle/SKILL.md` （`plan`, `cycle`, `plan-implement`）
     - `skills/iterate/SKILL.md` （`commit`）
     - `skills/issue/SKILL.md` （`plan-create`, `cycle`）

3. **CLAUDE.md の扱い**
   - **調査内容**: Plugin ルートの CLAUDE.md がインストール先プロジェクトに影響するか確認
   - **方針**: Plugin 用の説明は CLAUDE.md から分離し、README.md に移す。CLAUDE.md はこのリポジトリ自体の開発用として残す

4. **docs/ ディレクトリ**
   - **結論（確定）**: docs/ は plugin パッケージには含めるが、インストール先には影響しない。計画ファイルや status.md はインストール先プロジェクトのワーキングディレクトリに生成される。plugin.json の `exclude` で docs/ を除外することも検討

### plugin.json の構造（想定）

```json
{
  "name": "claude-skills",
  "version": "1.0.0",
  "description": "Implementation planning, review, and automation workflow skills for Claude Code",
  "commands": "commands/",
  "skills": "skills/"
}
```

> 注: 正確なスキーマは調査フェーズで Claude Code のドキュメントまたは既存 plugin の実例から確認する。上記は想定であり、フィールド名やネスト構造が異なる可能性がある。

### Files to Change

```
.claude-plugin/
  plugin.json               - NEW: Plugin マニフェスト作成

install.sh                  - 非推奨メッセージに書き換え（削除はしない）
                              → "This script is deprecated. Use: claude plugin install ..." と表示して終了
                              → plugin 未対応環境へのフォールバックとして残す

CLAUDE.md                   - インストール手順を plugin install に更新
README.md                   - インストール手順を plugin install に更新

commands/*.md               - 名前空間変更が必要な場合のみ、Skill ツール呼び出しを更新（調査結果に依存）
skills/*/SKILL.md           - 同上
```

### スキル間参照の影響調査

以下のコマンド/スキルが他のスキルを Skill ツール経由で呼び出している：

- `commands/cycle.md` → `plan-refine`, `plan-implement` を Agent 経由で呼び出し
- `commands/issue-cycle.md` → `plan`, `cycle` を呼び出し
- `commands/brainstorm-plan.md` → `plan` を呼び出し
- `commands/parallel-cycle.md` → `cycle` を worktree で呼び出し

Plugin 化後にこれらの相互参照が壊れないか確認が必要。

## ✅ Tests

### 構造テスト
- [ ] `plugin.json` が有効な JSON であること（`jq . .claude-plugin/plugin.json`）
- [ ] `plugin.json` が Claude Code の plugin スキーマに準拠していること

### ローカル動作テスト（`claude --plugin-dir ./`）
- [ ] 全コマンドが `/claude-skills:*` として認識されること（`/help` で一覧確認）
- [ ] `/claude-skills:plan-create` → 計画ファイルが生成されること
- [ ] `/claude-skills:commit` → 変更のコミットが動作すること
- [ ] `/claude-skills:cycle` → plan-refine → plan-implement のチェーンが動作すること
- [ ] `/claude-skills:investigate` → 読み取り専用調査が動作すること

### スキル間参照テスト
- [ ] `cycle` が `plan-refine` と `plan-implement` を正しく呼び出せること
- [ ] `issue-cycle` が `plan` と `cycle` を正しく呼び出せること
- [ ] `parallel-cycle` が worktree 内で `cycle` を正しく呼び出せること
- [ ] `brainstorm-plan` が `plan` を正しく呼び出せること

### rules/ テスト
- [ ] design-principles.md の内容が plugin 経由でもプロジェクトに適用されること
- [ ] rules/ が plugin でサポートされない場合、代替手段（方針B）が機能すること

### インストールテスト
- [ ] private repo から `claude plugin install` できること（GitHub token 設定済み環境）
- [ ] アンインストール後に `install.sh`（非推奨版）でフォールバックインストールできること

## 🔒 Security

- [ ] plugin.json に機密情報を含めない
- [ ] GitHub token のスコープは `repo`（read only で十分か確認）
- [ ] `postInstall` フックを使う場合、実行されるスクリプトに危険な操作がないこと

## 🔄 Rollback Plan

Plugin 化に失敗した場合のロールバック手順：

1. `.claude-plugin/` ディレクトリを削除
2. `install.sh` を元の内容に `git checkout install.sh` で復元
3. `./install.sh` を再実行してシンボリックリンクを再作成
4. CLAUDE.md / README.md を `git checkout` で復元

> install.sh は非推奨化するが削除はしないため、ロールバックは `git checkout` 1回で完了する。

## 🔀 Migration Guide（既存ユーザー向け）

1. 既存のシンボリックリンクを削除: `rm ~/.claude/commands/plan-create.md` 等（または `install.sh --uninstall` を追加検討）
2. `claude plugin install github:mizumi/claude-skills` を実行
3. `/help` でコマンド一覧を確認（`/claude-skills:*` の名前空間で表示される）
4. 既存のカスタム rules がある場合は手動で維持（plugin の rules/ とは独立）

## 📊 Progress

| Step | Status |
|------|--------|
| 要調査事項の確認 | 🟢 |
| plugin.json 作成 | 🟢 |
| rules/ 移行方法の決定 | 🟢 |
| スキル間参照の修正（必要なら） | ⚪ |
| install.sh の処理 | ⚪ |
| ドキュメント更新 | ⚪ |
| 動作テスト | ⚪ |
| Commit | ⚪ |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** まず要調査事項を確認 → plugin.json 作成 → テスト → Commit 🚀
