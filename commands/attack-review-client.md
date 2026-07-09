---
description: "クライアントサイドに特化した攻撃者視点レビュー（Client Attack, AuthN/AuthZ, Data, Infra, Business Logic）"
---

`claude-skills:attack-review` スキルを client モードで起動する。

## 手順

1. スキル `claude-skills:attack-review` を起動する
2. 引数に `client` を先頭に付与し、残りの `$ARGUMENTS` を続けて渡す
   - 例: `client`, `client --diff`, `client src/components/`
3. クライアントサイド攻撃に特化した5つのエージェント + Codex が並行でレビューを実行する
4. Injection Hunter（Agent 1）はスキップされる
