# Codex Second Opinion Integration

共通リファレンス: 複数スキルが参照する Codex セカンドオピニオンの呼び出しパターン、フォールバック、セキュリティルール。

## 呼び出しパターン

### Agent Tool Parameters

```
subagent_type: "codex:rescue"
mode: bypassPermissions (or default)
```

**並行実行**: 複数の Agent 呼び出しを同一メッセージ内で発行することで実現する。
`run_in_background` は Bash tool のパラメータであり Agent tool には適用されない。

### プロンプト構造

1. **コンテキスト提供** — 計画ファイル / コード / 差分 / 会話テキストを明示的に渡す
2. **指示** — 「設計上の問題点、見落とし、代替案を指摘せよ」
3. **出力フォーマット指定** — JSON or 構造化テキスト（スキルごとに異なる）

## フォールバック

Codex エージェントのタスク結果を確認し、以下のルールで処理する:

| 状態 | アクション |
|------|-----------|
| 成功 | 結果を既存レビューに統合（重複排除後） |
| エラー | 警告表示して既存処理のみで続行 |
| タイムアウト | brainstorm は10秒、他は Agent tool のデフォルトタイムアウトに依存 |
| 応答フォーマット不正（JSON パースエラー等） | 警告表示して既存処理のみで続行 |

### 警告メッセージテンプレート

```
⚠️ Codex second opinion unavailable — proceeding with existing review only.
```

brainstorm で初回失敗時:
```
⚠️ Codex unavailable — proceeding with Claude only
```

## セキュリティ

- Codex に渡すコンテキストは**計画ファイル / 差分 / レビュー結果 / 会話テキスト**に限定する
- source code を直接渡す場合（codebase-review）、以下を `target_files` から除外する:
  - `.gitignore` 対象ファイル
  - `.env`, `credentials.*`, `*.key`, `*.pem` 等の秘密情報ファイル
- Codex の応答は**レビュー結果としてのみ使用**し、直接実行しない

## 結果統合パターン

### レビュー系スキル（plan-reviewer, codebase-review, iterate）

- Codex の指摘を既存レビュー結果に追加する
- 重複排除: 既存レビューと同じファイル・同じ問題を指摘している場合はスキップ
- Codex 固有の指摘には `[Codex]` プレフィックスを付与する

### 壁打ちスキル（brainstorm）

- Codex の意見を `💡 Codex の視点:` セクションとして Claude の応答に追記する
- Codex の応答を踏まえて Claude が統合的な回答を生成する
