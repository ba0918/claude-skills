# Tool Mapping: Claude Code → Codex CLI

Codex CLI スキルで使用するツール変換リファレンス。
Claude Code 版スキルとの対応関係を定義する。

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

## Codex Second Opinion

Claude Code 版では `subagent_type: "codex:codex-rescue"` で Codex をセカンドオピニオンとして呼び出していたが、Codex CLI 版では自分自身を呼ぶ必要がないため **完全に除去** する。

## 共有契約の可搬性ポリシー

`codex-skills/shared/references/` に置く共有契約は次の3分類で管理する:

- **symlink（tool-agnostic）**: 内容にツール固有語彙がなくそのまま通用するもの。
  現行: `lang-detect.md` / `severity-and-verdicts.md` / `verification-gate.md` / `tdd-contract.md`
  （verification-gate / tdd-contract の「Bash」「Agent」表記は概念として Codex の `shell` / `spawn_agent` に読み替え可能で無害）
- **変換済み実体コピー（sync 追跡）**: ツール名変換が必要なもの。現行: `team-config.md`。
  スキル側 references も同基準 — ツール名・Codex 第二意見節を含むものは symlink 禁止、実体変換して
  `validate_repo.py` の `EXTRA_SYNC_PAIRS` で台帳追跡する
- **不移植（意図的）**: `codex-integration.md`（Claude から Codex を呼ぶ契約。Codex 内では無意味）、
  `skill-authoring.md`（リポジトリ開発メタ。Claude 側の authoring 資料）、
  `orchestration-patterns.md`（model 階層等が Claude Agent tool 固有。必要になった時点で変換コピーを検討）

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
