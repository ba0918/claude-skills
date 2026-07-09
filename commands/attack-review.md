---
description: "コードベースを攻撃者視点で6つの専門エージェント + Codex で並行レビューし、リスクマトリクスで脅威を分類する"
---

`claude-skills:attack-review` スキルを使用して、コードベースを攻撃者視点でレビューする。

## 手順

1. スキル `claude-skills:attack-review` を起動する
2. ユーザーの引数 `$ARGUMENTS` をそのまま渡す
   - 引数なし: テックスタックを自動検出し、full/server/client モードを決定
   - `server`: サーバーサイド攻撃に特化（Injection, AuthN/AuthZ, Data, Infra, Business Logic）
   - `client`: クライアントサイド攻撃に特化（Client Attack, AuthN/AuthZ, Data, Infra, Business Logic）
   - `--diff`: `git diff HEAD` の変更ファイルのみ
   - ディレクトリ名: 指定ディレクトリのみ
3. 6つの専門エージェント + Codex が並行で攻撃レビューを実行する
4. 統合レポートが生成され、リスクマトリクスと攻撃シナリオが表示される
