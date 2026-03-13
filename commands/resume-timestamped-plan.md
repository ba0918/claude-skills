---
description: "前セッションのtimestamped-plan作業を引き継ぐ"
---

`timestamped-plan` スキルの **Resume** ワークフローを実行する。

## 手順

1. `docs/status.md` を読み込み、現在のセッション状態を把握する
2. Skillツールで `timestamped-plan` を起動し、resumeワークフローを実行する
3. ユーザーの引数 `$ARGUMENTS` に追加の指示があればそれを反映する
4. 前回の作業状態と次のアクションをユーザーに提示する
