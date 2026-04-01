# Codex CLI スキル移植

**Cycle ID:** `20260402033810`
**Started:** 2026-04-02 03:38:10
**Status:** 🟡 In Progress

---

## What & Why

Claude Code 用に構築したスキル群（commit, investigate, plan, plan-reviewer, issue, iterate, cycle, team-cycle）を Codex CLI プラグインとして動作するよう移植する。同一リポジトリにデュアルプラグイン構造を構築し、両方のツールで同じワークフローを利用可能にする。

## Goals

- 既存の Claude Code スキルに一切手を加えず、Codex CLI 用スキルを並立させる
- Phase 1〜4 の段階的移植で、各フェーズ完了時点で動作検証可能な状態を保つ
- ツール参照を Codex CLI ネイティブに変換し、自然な操作感を実現する

## Design

### ディレクトリ構造

```
claude-skills/
├── .claude-plugin/plugin.json         # 既存（Claude Code 用）
├── skills/                             # 既存（Claude Code 用、変更しない）
├── commands/                           # 既存（Claude Code 専用、変更しない）
│
├── codex-skills/                       # 新規（Codex 用）
│   ├── shared/
│   │   └── references/
│   │       ├── tool-mapping.md        # Claude→Codex ツール変換リファレンス
│   │       ├── team-config.md         # ← skills/shared/references/ からコピー＆Codex適応
│   │       └── severity-and-verdicts.md  # ← 共有（ツール非依存）シンボリックリンク
│   ├── commit/
│   │   └── SKILL.md
│   ├── investigate/
│   │   └── SKILL.md
│   ├── plan/
│   │   ├── SKILL.md
│   │   └── references/                # plan-template.md 等はツール非依存なのでシンボリックリンク
│   ├── plan-reviewer/
│   │   ├── SKILL.md
│   │   └── references/
│   ├── issue/
│   │   ├── SKILL.md
│   │   └── references/
│   ├── iterate/
│   │   ├── SKILL.md
│   │   └── references/
│   ├── cycle/
│   │   └── SKILL.md                   # commands/cycle.md をスキルとして再構成
│   └── team-cycle/
│       ├── SKILL.md
│       └── references/
└── AGENTS.md                           # Codex 用（CLAUDE.md の Codex 版）
```

### ツール変換マッピング

これが全スキルに適用される中核の変換ルール。

| Claude Code | Codex CLI | 備考 |
|-------------|-----------|------|
| `Agent` (subagent_type: X) | `spawn_agent` (agent_type 指定) + `wait_agent` | Codex は spawn 時に `fork_turns` でコンテキスト共有可 |
| `Agent` (mode: bypassPermissions) | `spawn_agent` (full-auto sandbox 内) | approval_mode の設定で制御 |
| `Agent` (isolation: worktree) | `spawn_agent` + disjoint write scope 指示 | 物理的 worktree 分離は不可 |
| `SendMessage` (to: agent) | `send_message` / `assign_task` | Codex v2 のメールボックス方式 |
| `TeamCreate` / `TeamDelete` | spawn_agent グループ + close_agent | 専用チーム機能はないが再現可 |
| `AskUserQuestion` | `request_user_input` | 構造化質問UI（選択肢付き、最大3問） |
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

### スキル別の変換方針

#### commit (158行 → 推定150行)
- **変換難易度**: ★☆☆
- ツール参照: `AskUserQuestion` 禁止 → `request_user_input` 禁止に変更
- git コマンドは全てそのまま（shell 経由）
- ファイル読み取りの Read → shell (cat) は記述不要（Codex は元から shell）
- Conventional Commits ロジック、分割判定ロジックはそのまま

#### investigate (157行 → 推定150行)
- **変換難易度**: ★☆☆
- `Agent` (Explore) → `spawn_agent` に変換
- 禁止ツールリスト: Edit/Write/NotebookEdit → `apply_patch` 禁止に変更
- 許可ツールリスト: Read/Grep/Glob → shell (cat/rg/find) に変更
- LSP → 除去（Codex に LSP ツールなし）
- 推奨アクション内のコマンド例: `/claude-skills:X` → `$X` 形式に変更

#### plan (225行 → 推定220行)
- **変換難易度**: ★★☆
- Skill 呼び出し: `/claude-skills:issue-create` → `$issue create` に変更
- Skill 呼び出し: `/claude-skills:investigate` → `$investigate` に変更
- Skill 呼び出し: `claude-skills:commit` → `$commit` に変更
- references/ 内のテンプレートはツール非依存 → シンボリックリンクで共有
- ファイル操作（mkdir, cat）は shell 経由でそのまま

#### plan-reviewer (219行 → 推定200行)
- **変換難易度**: ★★☆
- 6-8 並行 Agent → 6-7 並行 `spawn_agent` に変更（Codex second opinion を除去するので -1）
- Agent (Explore / general-purpose) → spawn_agent (agent_type なし、プロンプトで役割指定)
- Codex Second Opinion (Review 8) → **完全除去**（自分自身を呼ぶ必要なし）
- Step 4 の Codex 統合ロジック → 除去
- `.claude/review-rules.md` 参照 → `.codex/review-rules.md` に変更するか検討（ただし docs ファイルなので共通でもよい）
- references/ (review-dimensions.md, output-format.md) → ツール非依存、シンボリックリンク

#### issue (245行 → 推定240行)
- **変換難易度**: ★★☆
- `AskUserQuestion` 6箇所 → `request_user_input` に変換（選択肢 UI）
- Skill 呼び出し: `claude-skills:plan-create` → `$plan` に変更
- Skill 呼び出し: `claude-skills:cycle` → `$cycle` に変更
- Skill 呼び出し: `claude-skills:team-cycle` → `$team-cycle` に変更
- Skill 呼び出し: `claude-skills:issue-list` → `$issue list` に変更
- Skill 呼び出し: `claude-skills:issue` (close) → `$issue close` に変更
- Edit ツール → apply_patch に変更
- references/issue-template.md → シンボリックリンク

#### iterate (200行 → 推定180行)
- **変換難易度**: ★★☆
- Agent (Explore) → spawn_agent
- Agent (general-purpose) → spawn_agent
- Codex Second Opinion → **除去**（Phase 4 の並行 2agent が 1agent に）
- Codex 統合ロジック → 除去
- Skill 呼び出し: `claude-skills:plan-create` → `$plan` に変更
- Skill 呼び出し: `claude-skills:commit` → `$commit` に変更
- AskUserQuestion 2箇所 → request_user_input

#### cycle (190行 → 推定200行、コマンドからスキル化で若干増)
- **変換難易度**: ★★★
- コマンド（commands/cycle.md）→ 独立スキル（codex-skills/cycle/SKILL.md）に昇格
- 全体が Agent 委譲パターン → spawn_agent チェーンに再構成
- Phase 1: Agent で refine → spawn_agent で `$plan-reviewer` 呼び出し
- Phase 2: Agent で implement → spawn_agent で plan-implement ロジック実行
- Phase 3: Skill(commit) → $commit
- Phase 3: Skill(issue close) → $issue close
- Agent エラーリトライ → spawn_agent + wait_agent + リトライロジック

#### team-cycle (562行 → 推定530行)
- **変換難易度**: ★★★
- `TeamCreate` → spawn_agent グループとして管理（team_name をプロンプトで共有）
- `TeamDelete` → close_agent で全メンバーを終了（try-finally パターンは維持）
- `SendMessage` 7箇所+ → send_message / assign_task に変換
- spawn_agent の fork_turns を活用してコンテキスト共有
- 環境変数チェック（CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS）→ 除去（Codex は spawn_agent がデフォルト）
- Phase 2.5 コードレビュー: Agent 2本並行 → spawn_agent 2本並行（比較的素直な変換）
- Skill 呼び出し 3箇所: plan-implement, commit, issue → $メンション

### Key Points

- **ツール非依存の references はシンボリックリンクで共有**: plan-template.md, status-template.md, issue-template.md, review-dimensions.md, output-format.md, severity-and-verdicts.md 等。メンテナンスコストを最小化
- **Codex Second Opinion は全スキルから除去**: Codex 内で自身を呼ぶのは無意味。7次元レビュー（plan-reviewer）や2観点レビュー（iterate Phase 4）は、Codex のネイティブ能力で十分カバー
- **commands/ 層は不要**: Codex にはカスタムスラッシュコマンドがない。SKILL.md の description を充実させて暗黙呼び出し + $メンションで対応
- **AGENTS.md は CLAUDE.md の Codex 適応版**: プロジェクト構造の説明は共通、ツール固有の説明を Codex 用に書き換え
- **`.claude/review-rules.md` は共通利用**: このファイルはプロジェクト固有のレビュールールで、ツールに依存しない内容。Codex 版でもそのまま参照する

## Implementation Steps

### Phase 1: 基盤構築 + commit + investigate

| # | タスク | 影響ファイル |
|---|--------|-------------|
| 1.1 | codex-skills/ ディレクトリ構造を作成 | `codex-skills/` ディレクトリツリー |
| 1.2 | ツール変換リファレンス（tool-mapping.md）を作成 | `codex-skills/shared/references/tool-mapping.md` |
| 1.3 | commit スキルを移植 | `codex-skills/commit/SKILL.md` |
| 1.4 | investigate スキルを移植 | `codex-skills/investigate/SKILL.md` |
| 1.5 | AGENTS.md を作成（CLAUDE.md の Codex 適応版） | `AGENTS.md` |
| 1.6 | Codex CLI でインストール・動作確認 | （手動テスト） |

### Phase 2: plan + plan-reviewer + issue

| # | タスク | 影響ファイル |
|---|--------|-------------|
| 2.1 | plan スキルを移植 | `codex-skills/plan/SKILL.md` |
| 2.2 | plan の references をシンボリックリンクで共有 | `codex-skills/plan/references/` |
| 2.3 | plan-reviewer スキルを移植（Codex 2nd opinion 除去） | `codex-skills/plan-reviewer/SKILL.md` |
| 2.4 | plan-reviewer の references をシンボリックリンクで共有 | `codex-skills/plan-reviewer/references/` |
| 2.5 | issue スキルを移植（AskUserQuestion → request_user_input） | `codex-skills/issue/SKILL.md` |
| 2.6 | issue の references をシンボリックリンクで共有 | `codex-skills/issue/references/` |
| 2.7 | shared references を準備（シンボリックリンク + Codex 適応版） | `codex-skills/shared/references/` |
| 2.8 | Codex CLI で plan → plan-reviewer の一連フローを動作確認 | （手動テスト） |

### Phase 3: iterate + cycle

| # | タスク | 影響ファイル |
|---|--------|-------------|
| 3.1 | iterate スキルを移植（Codex 2nd opinion 除去） | `codex-skills/iterate/SKILL.md` |
| 3.2 | iterate の references をシンボリックリンクで共有 | `codex-skills/iterate/references/` |
| 3.3 | cycle をコマンドからスキルに昇格・移植 | `codex-skills/cycle/SKILL.md` |
| 3.4 | Codex CLI で cycle の全フロー（refine→implement→commit）を動作確認 | （手動テスト） |

### Phase 4: team-cycle

| # | タスク | 影響ファイル |
|---|--------|-------------|
| 4.1 | team-cycle スキルを移植（TeamCreate→spawn_agent グループ） | `codex-skills/team-cycle/SKILL.md` |
| 4.2 | team-cycle の references をシンボリックリンク + Codex 適応 | `codex-skills/team-cycle/references/` |
| 4.3 | shared/team-config.md の Codex 適応版を作成 | `codex-skills/shared/references/team-config.md` |
| 4.4 | Codex CLI で team-cycle の全フロー（チームレビュー→実装→コードレビュー）を動作確認 | （手動テスト） |

### Phase 5: 仕上げ

| # | タスク | 影響ファイル |
|---|--------|-------------|
| 5.1 | AGENTS.md に全スキルの説明を追記 | `AGENTS.md` |
| 5.2 | README.md に Codex 対応の記述を追加 | `README.md` |
| 5.3 | CLAUDE.md にデュアルプラグイン構造の説明を追加 | `CLAUDE.md` |

## Tests

- [ ] commit: Codex CLI で `$commit` と入力し、変更のない状態で「No changes」と返ること
- [ ] investigate: Codex CLI で `$investigate {問題}` と入力し、レポートが出力されること
- [ ] plan: Codex CLI で `$plan {機能名}` と入力し、docs/plans/ に計画ファイルが作成されること
- [ ] plan-reviewer: `$plan-reviewer` で並行レビュー結果が出力されること
- [ ] issue: `$issue create "test"` で docs/issues/ にファイルが作成されること
- [ ] iterate: `$iterate {指示}` でスコープ分析→実装→レビューが走ること
- [ ] cycle: `$cycle` で refine→implement→commit の全フローが完走すること
- [ ] team-cycle: `$team-cycle` でチームレビュー→実装→コードレビューが完走すること
- [ ] シンボリックリンク: Codex CLI から references 内のテンプレートが正しく参照できること

## Security

- [ ] AGENTS.md に機密情報を含めない
- [ ] tool-mapping.md に API キー等を含めない
- [ ] Codex skills 内で .env, credentials, private keys へのアクセスを禁止する記述を維持

## Progress

| Step | Status |
|------|--------|
| Phase 1: 基盤 + commit + investigate | 🟢 |
| Phase 2: plan + plan-reviewer + issue | 🟢 |
| Phase 3: iterate + cycle | 🟢 |
| Phase 4: team-cycle | 🟢 |
| Phase 5: 仕上げ | 🟢 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Phase 1 から実装開始 → `$commit` と `$investigate` を Codex で動かす！
