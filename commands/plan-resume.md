---
description: "前セッションの plan 作業を引き継ぐ"
---

Artifact paths follow the [Agent Artifact Store contract](../skills/shared/references/artifact-store.md).

`plan` スキルの **Resume** ワークフローを実行する。

## 手順

1. `.agents/artifacts/status.md` を読み込み、現在のセッション状態を把握する
2. Skillツールで `claude-skills:plan` を起動し、resumeワークフローを実行する
3. ユーザーの引数 `$ARGUMENTS` に追加の指示があればそれを反映する
4. 前回の作業状態と次のアクションをユーザーに提示する
