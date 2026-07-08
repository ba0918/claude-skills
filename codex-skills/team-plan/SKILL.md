---
name: team-plan
description: spawn_agent グループによるチーム議論型の計画作成。複数の専門家（Security / Performance / Architect / Pragmatist）がチームとして議論しながら多角的な実装計画を作成する。「team plan」「チーム計画」「チーム議論型計画」で起動。
---

# Team Plan (Codex Edition)

## Codex CLI ツールの使い分け

- **spawn_agent** / **wait_agent** — 専門家議論の起動と結果回収。4つの助言者（Security / Performance / Architect / Pragmatist、条件付きで UX Advisor）を並行で spawn_agent し、各提案を wait_agent で受け取る
- **send_message** — 議論のやり取り。Lead から全メンバーへの要件共有・トレードオフ論点の提示、メンバー間の往復ラウンドで使う
- **close_agent** — チーム解散。spawn_agent 成功後はエラー時も含めて必ず実行する
- **apply_patch** — 計画ファイル（`docs/plans/{timestamp}_{slug}.md`）の生成。shell リダイレクトでのファイル書き込みは禁止
- **shell**（読み取り専用用途） — コードベース調査・コンテキスト収集（`cat` / `rg` / `ls` / `find`）
- **会話ターンでの確認** — 要件が不明確な場合のユーザへの質問など。平文で尋ね、選択肢は列挙して番号/短文で回答を促す。**Codex の `request_user_input` は Plan mode 限定（default/exec 不可）のため使わない。** 要件が `$ARGUMENTS` にある headless 文脈では確認プロンプトを出さない

spawn_agent グループを使った複数の専門家によるチーム議論型の計画作成。

## Flow Overview

```
team-plan
  │
  ├─ Phase 0: 準備（要件受け取り・コードベース調査）
  │
  ├─ Phase 1: チーム議論による計画作成（spawn_agent グループ、try-finally で close_agent 保証）
  │    ├─ spawn_agent × 4 → 議論 → 合意形成 → 計画作成
  │    └─ close_agent で全メンバーを終了（必ず実行）
  │
  ├─ Phase 2: 計画ファイル出力
  │    ├─ docs/plans/{timestamp}_{slug}.md に生成（plan テンプレート準拠）
  │    └─ docs/status.md を更新（status-update-guide 準拠）
  │
  └─ 完了（計画ファイルパスを返す）
```

## パラメータ

- `$ARGUMENTS`: ユーザーの要件（空の場合はユーザーに質問する）

## Phase 0: 準備

### Step 0.1: 要件受け取りとコードベース調査

1. `$ARGUMENTS` からユーザーの要件を取得する
   - 空の場合は会話ターンで「何を作りたいですか？」と質問する
2. コードベースを調査し、関連ファイルの構造・既存実装を把握する
   - プロジェクト構造の理解
   - 既存の類似実装の特定
   - 影響範囲の把握
3. 調査結果を整理し、Phase 1 のメンバー共有に備える

## Phase 1: チーム議論による計画作成（spawn_agent グループ）

**重要**: Phase 1 の全処理は **close_agent を保証する try-finally パターン** で実装する。spawn_agent 成功後、以降のどの段階でエラーが発生しても close_agent を必ず実行する。

### Step 1.1: コンテキスト収集

メンバーに渡すコンテキストを収集する:

```bash
# AGENTS.md
cat AGENTS.md 2>/dev/null || echo ""

# review-rules.md（フォールバックチェーン、存在する場合のみ）
cat .codex/review-rules.md 2>/dev/null || cat .claude/review-rules.md 2>/dev/null || cat review-rules.md 2>/dev/null || echo ""
```

### Step 1.2: Optional Specialist Detection

Step 1.3（メンバー spawn）の前に実行する。

ユーザーの要件とコードベース調査結果を plan-reviewer Step 2.5 と同じキーワード検出ロジックでスキャンする。

**Strong signals (any one triggers):**
- Keywords: "UI", "UX", "component", "screen", "page", "button", "form", "modal", "frontend", "accessibility", "a11y"
- File extensions in affected files: `.tsx`, `.jsx`, `.vue`, `.svelte`, `.css`, `.scss`, `.html`

**Weak signals (2+ required to trigger):**
- Keywords: "display", "layout", "style", "output", "format", "message", "error message", "progress"

**Override:** If review-rules.md contains `ui_ux_review: always`, always include. If `ui_ux_review: never`, always skip. Invalid values fall back to default `auto`.

If UI/UX signals detected:
- Step 1.3 で UX Advisor を5人目として追加 spawn する
- Phase 1 の全議論ラウンドに UX Advisor を含める

If not detected:
- 標準4人構成で続行

**spawn 失敗時の扱い:**
- UX Advisor（optional specialist）の spawn 失敗は WARNING のみ。コア4ロール（Security/Performance/Architect/Pragmatist）のうち2名以上成功すれば続行可能。

### Step 1.3: メンバー spawn（並行）

[codex-skills/shared/references/team-config.md](../shared/references/team-config.md) に定義された4つのロール（+ Step 1.2 で検出された場合は UX Advisor）を **並行で** spawn_agent する。

各エージェントのプロンプトは以下の構成:

1. ロール説明と設計提案の指示（team-config.md のロール専門知識 + 計画作成フレーミング）
2. コンテキスト（要件、コードベース調査結果、AGENTS.md）

**重要: フレーミングの切り替え**

team-config.md のロール定義はレビュー・計画作成の双方で使えるように専門知識に特化している。team-plan ではスポーンプロンプトの冒頭で「レビュー（批判）」ではなく「設計提案（助言）」のフレーミングに切り替える。

**並行 spawn の実行:**

4つの spawn_agent 呼び出しを同時に実行する。各エージェントのプロンプト:

```
あなたは {role_name} として計画作成チームに参加しています。

あなたの役割は「批判」ではなく「設計提案」です。
ユーザーの要件に対して、あなたの専門観点から最適な設計を提案してください。

## あなたの専門知識
{role_expertise_from_team_config}

## 計画作成での役割
- セキュリティ要件を提案する助言者（Security Advisor の場合）
- 効率的な設計を提案する助言者（Performance Advisor の場合）
- テスタブルな構造を提案する助言者（Architect の場合）
- 実現可能なスコープを提案する助言者（Pragmatist の場合）

## ユーザーの要件
{requirements}

## コードベースの関連情報
{codebase_context}

## プロジェクトルール (AGENTS.md)
{agents_md_content}

## 出力フォーマット
以下の形式で提案してください:

### {ロール名} 設計提案

**推奨事項:**
- {設計で考慮すべきポイント}

**やるべきこと:**
- {含めるべき要素}

**やらないべきこと:**
- {スコープ外にすべき要素}

**懸念事項:**
- {リスクや注意点}

提案が完了したら、提案結果の全文を出力してください。
```

**spawn 失敗時の処理:**

- 成功したエージェントが 2 名以上 → 続行
- 成功したエージェントが 1 名以下 → close_agent で全メンバーを終了して中断:

```
⛔ TEAM-PLAN ABORTED: Insufficient team members (need >= 2, got {count})
Agents closed.
```

### Step 1.4: 議論フロー

[references/planning-flow.md](references/planning-flow.md) に従い、議論を進める。

1. **要件共有**: Lead がユーザーの要件 + コードベースの関連情報を全メンバーに send_message で共有
2. **設計提案収集**: 各メンバーからの提案を wait_agent で受け取り、整理
3. **トレードオフ議論**: メンバー間で意見が対立する論点について議論（最大3ラウンド）
4. **各ラウンド終了時にサマリーを出力**: ユーザーに途中経過を可視化する（フォーマットは planning-flow.md 参照）
5. **早期収束チェック**: 全論点が WARN 以下なら残りラウンドをスキップ
6. **合意形成**: Lead が議論を収束に導き、計画の方向性を決定

### Step 1.5: close_agent

**必ず実行する。** 正常完了・エラーのいずれの場合も。

close_agent で全メンバーエージェントを終了する。

## Phase 2: 計画ファイル出力

### Step 2.1: 計画ファイル作成

合意に基づいて計画ファイルを apply_patch で作成する。

1. タイムスタンプを生成: `date +%Y%m%d%H%M%S`
2. slug をユーザーの要件から生成（英数字とハイフンのみ、30文字以内）
3. `docs/plans/{timestamp}_{slug}.md` に出力

計画ファイルは `codex-skills/plan/references/plan-template.md` のフォーマットに**完全準拠**する。

追加で以下のセクションを含める:

```markdown
## Team Planning Results

**Planned:** {datetime}
**Team:** Security Advisor, Performance Advisor, Architect, Pragmatist

### 合意事項
- {合意した設計ポイント}

### 議論ハイライト
- {論点}: {合意内容の要約}

### 各メンバーの貢献
- **Security Advisor**: {主な貢献}
- **Performance Advisor**: {主な貢献}
- **Architect**: {主な貢献}
- **Pragmatist**: {主な貢献}
```

### Step 2.2: status.md 更新

`codex-skills/plan/references/status-update-guide.md` に従い、`docs/status.md` にステータスを Planning 状態として登録する。

## 完了表示

```
══════════════════════════════════════
TEAM-PLAN COMPLETE
Feature: {feature_name}
Team: {active_count}/{total} members participated (total = 4 or 5 depending on UX Advisor)
Discussion rounds: {round_count}
Plan: {plan_file_path}
══════════════════════════════════════
```

計画ファイルのパスを返す。

## エラーハンドリング

### Phase 0 のエラー

- **要件が不明確**: 会話ターンでユーザーに質問する（中断しない）

### Phase 1 のエラー

- **spawn_agent 失敗（2名以上成功）**: 成功したメンバーで続行
- **spawn_agent 失敗（1名以下）**: close_agent → 中断
- **予期しないエラー**: close_agent → エラーメッセージ表示 → 中断

### Phase 2 のエラー

- **計画ファイル書き込み失敗**: エラー内容を表示して中断

## 重要なルール

- **close_agent は必ず実行する**: spawn_agent 以降のどの段階でエラーが発生しても、close_agent を必ず実行する
- **フレーミングは「設計提案」**: team-cycle のレビュー（批判）とは異なり、team-plan では設計提案（助言）のフレーミングを使う
- **計画テンプレート準拠**: 出力する計画ファイルは plan テンプレートに完全準拠し、team-cycle でも通常の cycle でもそのまま使える
- **ヘッドレス実行**: 要件が `$ARGUMENTS` にある場合はユーザーへの確認プロンプトは出さない
- **コードベース調査の組み込み**: Lead がコードベースを調査し、メンバーに共有する。メンバーにも読み取り専用のコードベース調査（shell: `cat` / `rg`）を許可する

## References

- チーム構成: [codex-skills/shared/references/team-config.md](../shared/references/team-config.md)
- 計画作成議論フロー: [references/planning-flow.md](references/planning-flow.md)
- 計画テンプレート: [codex-skills/plan/references/plan-template.md](../plan/references/plan-template.md)
