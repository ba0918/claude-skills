# Tool Mapping

スキル本文をプラットフォーム非依存に保つためのツール語彙対応表。
`SKILL.md` と `references/` では原則として左列・右列の固有 API 名を直書きせず、
「ファイルを読む」「ファイルを編集する」「サブエージェントに委譲する」「シェルコマンドを実行する」などの共通語彙で書く。

## ツール変換マッピング

| Claude Code | Codex CLI | 備考 |
|-------------|-----------|------|
| `Agent` (subagent_type: X) | `spawn_agent` (agent_type 指定) + `wait_agent` | spawn 時に `fork_turns` でコンテキスト共有可 |
| `Agent` (mode: bypassPermissions) | `spawn_agent` (full-auto sandbox 内) | approval_mode の設定で制御 |
| `SendMessage` (to: agent) | `send_message` / `assign_task` | メールボックス方式 |
| `TeamCreate` / `TeamDelete` | `spawn_agent` グループ + `close_agent` | 専用チーム機能はないが再現可 |
| `AskUserQuestion` | 会話ターンでの平文質問（選択肢を列挙し番号/短文で回答を促す） | **`request_user_input` は Plan mode 限定（default/exec 不可、v0.142.4 で実測確認）なので依存しない**。headless/exec で応答不能なら安全側デフォルト（no-op / report-only / UNCERTAIN / 中断）に降格する |
| `Skill` (呼び出し) | `$skill-name` テキストメンション | 直接 API 呼び出しなし。spawn_agent で skill 指定も可 |
| `Read` | `shell` (`cat`, `head`, `tail`) | 専用ツールなし |
| `Write` | `apply_patch` (Add File) | 独自パッチ形式 |
| `Edit` | `apply_patch` (Update File) | 独自パッチ形式 |
| `Grep` | `shell` (`rg`, `grep`) | 専用ツールなし |
| `Glob` | `shell` (`find`) or `codex_file_search` | ファジー検索あり |
| `Bash` | `shell` / `shell_command` | ほぼ同等 |
| `TaskCreate`/`TaskUpdate` | （除去） | エージェント＝タスク。`list_agents` で代替 |
| `EnterWorktree`/`ExitWorktree` | （存在しない） | disjoint write scope ガイダンスで代替 |
| `LSP` | （存在しない） | shell 経由のツール呼び出しで代替 |
| `NotebookEdit` | （存在しない） | 対象外 |

## スキル呼び出しパターン

| Claude Code | Codex CLI |
|-------------|-----------|
| `/claude-skills:plan-create` | `$plan` |
| `/claude-skills:plan-review` | `$plan-reviewer` |
| `/claude-skills:cycle` | `$cycle` |
| `/claude-skills:commit` | `$commit` |
| `/claude-skills:iterate` | `$iterate` |
| `/claude-skills:investigate` | `$investigate` |
| `/claude-skills:issue-create` | `$issue create` |
| `/claude-skills:issue-list` | `$issue list` |
| `/claude-skills:issue-close` | `$issue close` |
| `/claude-skills:team-cycle` | `$team-cycle` |

## Codex Second Opinion の扱い

Codex セカンドオピニオンは、呼び出し元ランタイムとは独立したレビュー視点を得るための任意機能として扱う。
実行環境が該当する外部レビュー手段を持たない場合は、各スキルの graceful degradation に従い、警告して通常レビューのみで続行する。

## 共有契約の可搬性ポリシー

`skills/shared/references/` に置く共有契約は、単一の正本として複数ランタイムから読まれる。
新規・改訂時は次の基準で可搬性を確認する:

- **tool-agnostic**: 内容にツール固有 API 名がなく、そのまま複数ランタイムで通用する
- **platform-aware**: 外部レビュー、サブエージェント、対話確認などランタイム差があるが、共通語彙と fallback で表現できる
- **platform-specific**: どうしても固有 API 名が必要な場合は、その理由と代替不能性を本文に明記し、影響範囲を最小化する

## ファイル操作パターン

### ファイル読み取り

```bash
# Claude Code: Read ツール
# Codex CLI: shell
cat path/to/file.md
head -50 path/to/file.md
tail -20 path/to/file.md
```

### ファイル検索

```bash
# Claude Code: Grep ツール
# Codex CLI: shell
rg "pattern" path/to/dir
grep -rn "pattern" path/to/dir
```

### ファイル一覧

```bash
# Claude Code: Glob ツール
# Codex CLI: shell or codex_file_search
find . -name "*.md" -type f
```

### ファイル作成・編集

```
# Claude Code: Write / Edit ツール
# Codex CLI: apply_patch ツール
# Add File / Update File パッチ形式で適用
```
