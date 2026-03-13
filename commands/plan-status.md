---
description: "plan のステータスと進捗を更新する"
---

`plan` スキルの **Status更新** ワークフローを実行する。

## 手順

1. `docs/status.md` と現在進行中のcycle docを読み込む
2. Skillツールで `plan` を起動し、status更新ワークフローを実行する
3. ユーザーの引数 `$ARGUMENTS` に新しいフェーズや完了報告があればそれを反映する（例: `planning done`, `implementation complete`）
4. 引数が空の場合は、現在の進捗状況をユーザーに確認してから更新する
