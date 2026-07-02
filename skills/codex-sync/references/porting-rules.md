# Porting Rules: Claude Code → Codex CLI

Claude 版スキルを Codex 版へ移植・同期する際の変換ルール。
乖離は3層に分類され、第1〜2層は機械的に適用し、第3層は人間の判断を仰ぐ。

ツール名の対応表は [tool-mapping.md](../../../codex-skills/shared/references/tool-mapping.md) を正とする。

## 第1層: 機械的置換（必ず適用）

| Claude 版 | Codex 版 | 備考 |
|-----------|----------|------|
| `AskUserQuestion` | `request_user_input` | 構造化質問UI |
| `Agent` (subagent_type) | `spawn_agent` + `wait_agent` | |
| `Bash` | `shell` | 見出し内の言及も置換 |
| `Read` / `Grep` / `Glob` | `shell` (`cat` / `rg` / `find`) | |
| `Write` / `Edit` | `apply_patch` | shell リダイレクトでのファイル書き込みは禁止 |
| `Skill` ツール呼び出し | `$skill-name` メンション | |
| `/claude-skills:X` / `X-Y` コマンド | `$X Y` | 例: `/claude-skills:issue-cycle` → `$issue cycle` |
| `.claude/tmp/` | `.codex/tmp/` | 作業ディレクトリ |
| `CLAUDE.md` 参照 | `AGENTS.md` 参照 | プロジェクト説明ファイル |
| `TaskCreate` / `TaskUpdate` | 除去（`list_agents` で代替） | |
| `EnterWorktree` / `ExitWorktree` | `git worktree` 直叩き | |

## 第2層: 構造的変換（ルールに合致したら適用）

1. **Codex セカンドオピニオンの削除** — Codex の中で Codex に意見を聞くのは自己レビューで無意味。
   セカンドオピニオン用のエージェント・セクション・統合手順（例: `agent-5-codex.json`、
   「Codex Perspective」節、`codex-integration.md` 参照）は丸ごと削除し、エージェント数の
   記述（「5エージェント」等）も減算して整合させる
2. **Claude 固有の環境チェックの削除** — `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` 等の
   環境変数チェックは Step ごと削除し、後続 Step の番号を詰める
3. **AgenticTeam → spawn_agent グループ** — `TeamCreate` / `TeamDelete` / `SendMessage` は
   `spawn_agent` 群 + `send_message` / `close_agent` で再現する
4. **headless 化** — ユーザー承認プロンプトは撤廃し、判断基準を明文化して自動判定に置き換える
   （例: parallel-cycle Codex 版は Step 0.2 を "Report Decomposition (headless)" に変更）
5. **タイトル規約** — H1 に `(Codex Edition)` を付与し、直後に「## Codex CLI ツールの使い分け」
   セクションを置く（handoff / parallel-cycle / attack-review の慣例）
6. **references の共有** — ツール非依存の references はコピーせず symlink を張る:
   `ln -s ../../../skills/<name>/references/<file> codex-skills/<name>/references/<file>`
   ツール名を含む references のみ Codex 版として実体コピー・変換する
7. **frontmatter** — `name` は同一、`description` から Claude 固有機能への言及
   （標準 plan mode 比較等）を除去する

## 第3層: 意味的な再設計（自動変換禁止 — 報告して人間の判断を仰ぐ）

以下に該当する箇所は勝手に変換せず、**報告書に「要判断」として列挙**する:

- サンドボックス・承認モデルの違いに起因する安全設計の変更
  （例: attack-review Codex 版の shell heredoc ベース化）
- プラットフォーム固有機能に依存するワークフロー
  （例: issue polling は Claude 版のみ — Codex 版は polling ワークフロー自体を持たない）
- empirical tuning で作り込まれた数値・閾値・プロンプト文言の変更
- 新規スキルの移植で、上記ルールのどれにも該当しない設計判断が必要な箇所

## 検証（移植・同期後に必ず実施）

```bash
python3 scripts/validate_repo.py                    # [sync] 未登録/未同期が出ることを確認
# → 新規スキルなら AGENTS.md（構造ツリー・スキル表）と README（codex 表）に追記
python3 scripts/validate_repo.py --update-manifest  # 台帳更新
python3 scripts/validate_repo.py                    # 全チェック合格を確認（エビデンス）
```

大規模な移植（第3層判断を含む）の後は、`empirical-prompt-tuning` での実機チューニングを推奨する。
