# Codex Second Opinion Integration

**Cycle ID:** `20260401183528`
**Started:** 2026-04-01 18:35:28
**Status:** 🟢 Done

---

## 📝 What & Why

全レビュー系スキル（plan-reviewer, codebase-review, iterate, brainstorm, cycle）に Codex によるセカンドオピニオンをデフォルト組み込みする。Claude と異なるモデル（Codex/GPT系）の視点を並行で取得し、見落としを防ぐ。壁打ちでは各ターンで Codex のセカンドオピニオンを取得する。

## 🎯 Goals

- 全レビューフェーズで Claude + Codex の2つの視点を自動統合する
- brainstorm の壁打ちセッションで各ターンに Codex のセカンドオピニオンを併記する
- Codex が利用不可能な場合は graceful degradation で既存動作にフォールバックする

## 📐 Design

### Files to Change

```
skills/
  shared/
    references/
      codex-integration.md       - [新規] Codex セカンドオピニオンの共通呼び出しパターン・フォールバック・セキュリティルール
  plan-reviewer/
    SKILL.md                     - Step 3 に Codex 並行レビューエージェント追加、Step 4 に統合ロジック追加
    references/output-format.md  - Codex レビュー結果セクション追加
  codebase-review/
    SKILL.md                     - Step 3 に 5番目の Codex エージェント追加、Step 4 統合エージェントに Codex 結果反映
    references/review-criteria.md - Codex セカンドオピニオンの観点説明追加
    references/report-template.md - Codex Perspective セクション追加
  iterate/
    SKILL.md                     - Phase 4 レビューに Codex セカンドオピニオン追加
  brainstorm/
    SKILL.md                     - Session Workflow に各ターンの Codex 意見取得ステップ追加
commands/
  cycle.md                       - 変更なし（plan-reviewer 経由で自動適用）
CLAUDE.md                        - 主要スキルの説明に Codex セカンドオピニオン対応を追記
```

### Key Points

#### Task 1: plan-reviewer への Codex 統合

- **並行起動**: 既存7次元レビューと同時に `codex:rescue` サブエージェントタイプで Codex レビューエージェントを起動
- **Codex エージェントのプロンプト**: 計画ファイルの全文を渡し、「この計画の設計上の問題点、見落とし、代替案を指摘せよ」という包括的レビューを依頼
- **Codex は Bash ツールのみ使用可能** なので、`cat` 等でファイルを読み取り、分析結果をテキストとして返す形式
- **統合**: Step 4 で Codex の指摘を既存7次元の結果と統合。Codex 固有の指摘は `[Codex]` プレフィックス付きで WARN/BLOCK 判定に含める
- **フォールバック**: Codex エージェントがエラーの場合は警告を表示して既存7次元のみで続行

```
Step 3 変更イメージ:
  既存: 7 Explore/general-purpose agents を並行起動
  変更後: 7 agents + 1 Codex agent (subagent_type: "codex:rescue") を並行起動

Step 4 変更イメージ:
  既存: 7次元の結果を集約して判定
  変更後: 7次元 + Codex の結果を集約。Codex の指摘は重複排除後に追加
```

#### Task 2: codebase-review への Codex 統合

- **5番目のエージェント**: 既存4エージェントと並行で `codex:rescue` エージェントを起動
- **Codex エージェントの役割**: コードベース全体を俯瞰し、全体的な設計パターン、アーキテクチャ上の懸念、クロスカッティング concerns を指摘
- **結果出力**: `.claude/tmp/codebase-review-{timestamp}/agent-5-codex.json` に JSON で出力
- **重みづけ**: Codex の結果は独立セクション「Codex Perspective」として表示。既存8サブカテゴリのスコアには影響を与えない（加点/減点なし）。ただし Codex の critical 指摘は統合レポートの Critical Issues にマージする
- **フォールバック**: Codex エージェントが失敗しても graceful degradation で既存4エージェントのみで続行（Step 3.5 の既存ロジックで対応可能）

```
Step 3 変更イメージ:
  既存: 4 agents (security, performance, quality, hygiene) を並行起動
  変更後: 4 agents + 1 Codex agent を並行起動

Step 4 変更イメージ:
  統合エージェントのプロンプトに agent-5-codex.json の読み込みを追加
  レポートに "Codex Perspective" セクションを追加
```

#### Task 3: iterate への Codex 統合

- **Phase 4 のレビューに Codex 並行起動を追加**
- Small/Large 両方で、既存レビューエージェントと同時に Codex レビューエージェントを起動
- Codex は変更差分を受け取り、セカンドオピニオンを返す
- Codex の指摘は既存レビュー結果にマージ（重複排除）
- **フォールバック**: Codex 失敗時は既存レビューのみで判定

```
Phase 4 変更イメージ:
  既存: 1 review agent (2 or 4 perspectives)
  変更後: 1 review agent + 1 Codex agent を並行起動
  Codex 結果はレビュー結果セクションに [Codex] プレフィックス付きで追記
```

#### Task 4: brainstorm への Codex セカンドオピニオン統合

- **Session Workflow の対話ループにステップ追加**
- ユーザーの発言を受けた後、まず Agent tool で Codex にユーザーの発言+壁打ちコンテキストを投げる
- Codex の応答を取得した後、Claude がその結果を含めて応答を生成する
- Codex の意見は `💡 Codex の視点:` セクションとして Claude の応答に追記
- **注意**: Claude の応答生成と Agent 呼び出しは並行実行できないため、逐次実行となる（Codex 呼び出し → Claude 応答生成の順序）
- **フォールバック**: Codex 接続失敗時は初回のみ `⚠️ Codex unavailable — proceeding with Claude only` を表示し、以降は Codex 呼び出しをスキップ
- Resume Workflow にも同様の Codex 統合を適用

```
Session Workflow 対話ループ変更イメージ:
  既存: ユーザー発言 → Claude応答 → AskUserQuestion
  変更後: ユーザー発言 → Codex意見取得(Agent tool) → Claude応答(Codex意見を統合) → AskUserQuestion
  ※ Claude の応答生成と Agent 呼び出しの並行実行は不可のため、逐次実行
```

#### Task 5: cycle への影響確認

- cycle 自体の変更は**不要**
- plan-reviewer への Codex 統合（Task 1）により、Phase 1 の Refine で自動的に Codex レビューが適用される
- cycle.md へのドキュメント追記のみ（「Codex セカンドオピニオンが自動的に含まれます」の一文）

### 共通設計パターン（DRY: 共有リファレンスとして切り出し）

共通パターンは `skills/shared/references/codex-integration.md` に一元化し、各スキルの SKILL.md から参照する。

```
skills/shared/references/codex-integration.md の内容:

Codex セカンドオピニオン呼び出しパターン:

Agent tool parameters:
  subagent_type: "codex:rescue"
  mode: bypassPermissions (or default)
  ※ 並行実行は複数の Agent 呼び出しを同一メッセージ内で発行することで実現する
    （run_in_background は Bash tool のパラメータであり Agent tool には適用されない）

プロンプト構造:
  1. コンテキスト提供（計画/コード/差分）
  2. 「設計上の問題点、見落とし、代替案を指摘せよ」
  3. 出力フォーマット指定（JSON or 構造化テキスト）

フォールバック:
  - Codex エージェントのタスク結果を確認
  - エラー → 警告表示して既存処理のみで続行
  - タイムアウト → brainstorm は10秒、他は Agent tool のデフォルトタイムアウトに依存
  - 応答フォーマット不正（JSON パースエラー等） → 警告表示して既存処理のみで続行
  - 成功 → 結果を既存レビューに統合（重複排除後）

セキュリティ:
  - Codex に渡すコンテキストは計画ファイル/差分/レビュー結果に限定する
  - source code を直接渡す場合（codebase-review）、.gitignore 対象および
    .env, credentials, secrets 等の秘密情報ファイルは target_files から除外する
  - Codex の応答はレビュー結果としてのみ使用し、直接実行しない
```

## ✅ Tests

- [ ] plan-reviewer: Codex エージェントが正常に並行起動され、結果が統合レポートに含まれること
- [ ] plan-reviewer: Codex エージェント失敗時に既存7次元のみで正常完了すること
- [ ] codebase-review: agent-5-codex.json が生成され、レポートに Codex Perspective が含まれること
- [ ] codebase-review: Codex エージェント失敗時に既存4エージェントのみで正常完了すること
- [ ] iterate: Phase 4 で Codex レビュー結果が [Codex] プレフィックスで表示されること
- [ ] brainstorm: 壁打ちセッションの各ターンで Codex の視点が表示されること
- [ ] brainstorm: Codex 接続失敗時に警告表示後、Claude のみで壁打ちが継続すること
- [ ] cycle: plan-reviewer 経由で Codex レビューが自動的に適用されること
- [ ] Codex 応答が不正フォーマット（JSON パースエラー等）の場合に graceful degradation すること
- [ ] CLAUDE.md のスキル説明が Codex 対応を反映していること

## 🔒 Security

- [ ] Codex エージェントに渡すコンテキストに機密情報が含まれないことを確認
  - plan-reviewer / iterate: 計画ファイルと差分のみを渡す（source code は渡さない）
  - codebase-review: target_files から `.env`, `credentials.*`, `*.key`, `*.pem`, `.gitignore` 対象ファイルを除外する
  - brainstorm: 会話テキストのみを渡す（ファイル読み取り結果は渡さない）
- [ ] Codex の結果をそのまま実行しない（レビュー結果としてのみ使用）
- [ ] Codex の応答フォーマット不正時（JSON パースエラー等）は警告表示して既存処理のみで続行する

## 📊 Progress

| Step | Status |
|------|--------|
| Task 1: plan-reviewer Codex 統合 | 🟢 |
| Task 2: codebase-review Codex 統合 | 🟢 |
| Task 3: iterate Codex 統合 | 🟢 |
| Task 4: brainstorm Codex セカンドオピニオン統合 | 🟢 |
| Task 5: cycle ドキュメント更新 | 🟢 |
| Task 6: 共有リファレンス作成 (codex-integration.md) | 🟢 |
| Task 7: CLAUDE.md スキル説明更新 | 🟢 |
| Tests | 🟢 |
| Commit | 🟢 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Write tests → Implement → Commit with `claude-skills:commit` 🚀
