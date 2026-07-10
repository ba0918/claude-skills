---
description: "タイムスタンプ付き実装計画を新規作成する"
---

Artifact paths follow the [Agent Artifact Store contract](../skills/shared/references/artifact-store.md).

`plan` スキルの **Plan作成** ワークフローを実行する。

## 手順

1. Skillツールで `claude-skills:plan` を起動する
2. ユーザーの引数 `$ARGUMENTS` を機能の説明として渡す
3. 引数が空の場合は、何を作りたいかユーザーに質問する
4. 計画作成後、`.agents/artifacts/status.md` が更新されたことを確認する
