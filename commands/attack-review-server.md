---
description: "サーバーサイドに特化した攻撃者視点レビュー（Injection, AuthN/AuthZ, Data, Infra, Business Logic）"
---

`claude-skills:attack-review` スキルを server モードで起動する。

## 手順

1. スキル `claude-skills:attack-review` を起動する
2. 引数に `server` を先頭に付与し、残りの `$ARGUMENTS` を続けて渡す
   - 例: `server`, `server --diff`, `server src/api/`
3. サーバーサイド攻撃に特化した5つのエージェント + Codex が並行でレビューを実行する
4. Client Attack Specialist（Agent 3）はスキップされる
